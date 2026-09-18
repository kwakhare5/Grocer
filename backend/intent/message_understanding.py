"""Single natural-language boundary for shopping-task operations.

Rules handle high-certainty conversational forms.  A model may improve coverage,
but its result is still only a proposal validated by the task reducer and live
catalogue resolution.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Protocol

from backend.intent.task_model import (
    DesiredBasketItem,
    MessageUnderstanding,
    TaskOperation,
)

_QUANTITY_WORDS = {"a": 1.0, "an": 1.0, "one": 1.0, "two": 2.0, "three": 3.0}
_UNITS = {
    "l": "L",
    "ltr": "L",
    "litre": "L",
    "litres": "L",
    "liter": "L",
    "liters": "L",
    "kg": "kg",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "pack": "pack",
    "packs": "pack",
}
_VAGUE_REQUESTS = {"do the usual thing maybe", "something for tonight"}


class UnderstandingModel(Protocol):
    """Optional model boundary; model output remains a non-authoritative proposal."""

    async def interpret(
        self, message: str, *, context: Mapping[str, Any] | None = None
    ) -> MessageUnderstanding | None: ...


class MessageUnderstandingService:
    """Interpret English free text without letting it perform commerce actions."""

    def __init__(self, model: UnderstandingModel | None = None) -> None:
        self._model = model

    async def interpret(
        self, message: str, *, context: Mapping[str, Any] | None = None
    ) -> MessageUnderstanding:
        if self._model is not None:
            proposal = await self._model.interpret(message, context=context)
            if proposal is not None:
                return proposal
        return self._rules_interpret(message)

    def _rules_interpret(self, message: str) -> MessageUnderstanding:
        """Safe fallback when model understanding is unavailable."""
        normalized = " ".join(message.casefold().split())
        operation, item_text, target_item, quantity, selection_value = (
            self._operation_and_item_text(normalized)
        )
        items = self._items(item_text)
        missing_details: list[str] = []
        confidence = 0.95

        if operation in {
            TaskOperation.START_TASK,
            TaskOperation.START_FRESH_CART,
            TaskOperation.ADD_ITEMS,
            TaskOperation.KEEP_ONLY_ITEMS,
            TaskOperation.REMOVE_ITEMS,
        } and not items:
            confidence = 0.2
            missing_details.append("which grocery items you mean")

        if operation == TaskOperation.CLARIFY:
            confidence = 0.0
            missing_details.append("what you would like me to do")

        return MessageUnderstanding(
            operation=operation,
            items=items,
            target_item=target_item,
            quantity=quantity,
            selection_value=selection_value,
            confidence=confidence,
            missing_details=missing_details,
            source="rules",
        )

    def from_interactive(
        self,
        *,
        operation: TaskOperation,
        selection_value: str,
        target_item: str | None = None,
    ) -> MessageUnderstanding:
        """Normalize a button/list selection into the same shape as typed text."""
        return MessageUnderstanding(
            operation=operation,
            target_item=target_item,
            selection_value=selection_value,
            confidence=1,
            source="interactive",
        )

    def _operation_and_item_text(
        self, message: str
    ) -> tuple[TaskOperation, str, str | None, float | None, str | None]:
        if re.fullmatch(r"(?:help|what can you do|how does this work)[?!.]*", message):
            return TaskOperation.ASK_FOR_HELP, "", None, None, None

        if re.search(r"\b(?:track|where is|status of)\b.*\border\b", message):
            return TaskOperation.TRACK_ORDER, "", None, None, None

        if re.fullmatch(
            r"(?:cancel|stop)(?: my| this)? (?:order|task)[?!.]*", message
        ):
            return TaskOperation.CANCEL_TASK, "", None, None, None

        if re.search(r"\b(?:change|choose|select|switch)(?: my| the)? address\b", message):
            return TaskOperation.CHANGE_ADDRESS, "", None, None, None

        address = re.fullmatch(r"(?:use|select|choose) address (.+)", message)
        if address:
            return TaskOperation.SELECT_ADDRESS, "", None, None, address.group(1).strip()

        if re.search(
            r"\b(?:change|choose|select|switch)(?: my| the)? payment(?: method)?\b",
            message,
        ):
            return TaskOperation.CHANGE_PAYMENT, "", None, None, None

        payment = re.fullmatch(
            r"(?:pay (?:by|with)|use) (cod|cash on delivery|upi)", message
        )
        if payment:
            selected = "cod" if payment.group(1) == "cash on delivery" else payment.group(1)
            return TaskOperation.SELECT_PAYMENT, "", None, None, selected

        quantity = re.fullmatch(
            r"(?:make|set|change) (?:the quantity of )?(.+?) (?:to )?(\d+(?:\.\d+)?)",
            message,
        )
        if quantity:
            return (
                TaskOperation.SET_QUANTITY,
                "",
                quantity.group(1).strip(),
                float(quantity.group(2)),
                None,
            )
        keep_only = re.match(
            r"^(?:cancel|remove|delete|drop|omit|forget)\s+(?:all\s+)?(?:the\s+rest|other(?:\s+items?)?|everything)\s*(?:,|and)?\s*(?:just|only)\s+(?:keep|have|leave)\s+(.+)$",
            message,
        )
        if keep_only:
            return TaskOperation.KEEP_ONLY_ITEMS, keep_only.group(1), None, None, None

        keep_only = re.match(r"^(?:just|only)\s+(?:keep|have|leave)\s+(.+)$", message)
        if keep_only:
            return TaskOperation.KEEP_ONLY_ITEMS, keep_only.group(1), None, None, None

        except_items = re.match(
            r"^(?:cancel|remove|delete|drop|forget)\s+(?:all|everything|the rest)\s+(?:except|but)\s+(.+)$",
            message,
        )
        if except_items:
            return TaskOperation.KEEP_ONLY_ITEMS, except_items.group(1), None, None, None

        if re.match(
            r"^(?:actually\s+)?(?:cancel|stop|leave it|never mind|nevermind)"
            r"(?:\s+(?:this|that|it))?[.!]?$",
            message,
        ):
            return TaskOperation.CANCEL_PENDING_STEP, "", None, None, None

        if re.search(r"\b(?:start fresh|start over|new order|new basket|fresh basket)\b", message):
            return TaskOperation.START_FRESH_CART, _without_prefixes(message), None, None, None

        replacement = re.match(
            r"^(?:replace|swap|change)\s+(.+?)\s+(?:with|to|for)\s+(.+)$",
            message,
        )
        if replacement:
            return (
                TaskOperation.REPLACE_ITEM,
                replacement.group(2),
                replacement.group(1),
                None,
                None,
            )

        remove = re.match(r"^(?:remove|drop|delete|omit|exclude)\s+(?:the\s+)?(.+)$", message)
        if remove:
            return TaskOperation.REMOVE_ITEMS, remove.group(1), None, None, None

        add = re.match(r"^(?:add|also add|plus|include)\s+(.+)$", message)
        if add:
            return TaskOperation.ADD_ITEMS, add.group(1), None, None, None

        add = re.match(r"^(?:one|another)\s+more\s+(.+)$", message)
        if add:
            return TaskOperation.ADD_ITEMS, f"1 {add.group(1)}", None, None, None

        items = self._items(message)
        if items:
            return TaskOperation.START_TASK, message, None, None, None
        return TaskOperation.CLARIFY, "", None, None, None

    def _items(self, text: str) -> list[DesiredBasketItem]:
        """Conservative fallback extraction used only when the model is unavailable."""
        if " ".join(text.casefold().split()) in _VAGUE_REQUESTS:
            return []
        items: list[DesiredBasketItem] = []
        for part in re.split(r"\s*(?:,|\band\b)\s*", text.strip(), flags=re.I):
            candidate = re.sub(
                r"^(?:i\s+)?(?:need|want|would like|get|buy|please)\s+",
                "",
                part.strip(),
                flags=re.I,
            )
            if not candidate:
                continue
            match = re.fullmatch(
                r"(?:(\d+(?:\.\d+)?)|(a|an|one|two|three))?\s*"
                r"(litres|liters|litre|liter|ltr|packs|pack|grams|gram|kg|g|l)?\s*"
                r"(.+)",
                candidate,
                flags=re.I,
            )
            if match is None:
                continue
            numeric, word, unit_text, name = match.groups()
            quantity_is_explicit = numeric is not None or word is not None
            quantity = (
                float(numeric)
                if numeric is not None
                else _QUANTITY_WORDS.get((word or "").casefold(), 1.0)
            )
            clean_name = name.strip(" .!?")
            if not clean_name:
                continue
            items.append(
                DesiredBasketItem(
                    name=clean_name,
                    quantity=quantity,
                    unit=_UNITS.get((unit_text or "").casefold(), "units"),
                    preference_source="explicit",
                    quantity_is_explicit=quantity_is_explicit,
                )
            )
        return items


def _without_prefixes(message: str) -> str:
    return re.sub(
        r"^(?:start fresh|start over|new order|new basket|fresh basket)\s*(?:and|with)?\s*",
        "",
        message,
    ).strip()
