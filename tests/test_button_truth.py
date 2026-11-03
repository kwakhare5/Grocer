"""A button tap must never claim an action that did not happen."""

from __future__ import annotations

import time

import pytest

from backend.channels.button_router import dispatch_button_action


class RecordingWA:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def send_text_message(self, to_wa_id: str, text: str) -> None:
        self.texts.append(text)


async def test_pay_tap_without_database_is_honest() -> None:
    wa = RecordingWA()

    result = await dispatch_button_action(
        "pay:approval-1", "919999999999", pool=None, wa_client=wa
    )

    assert result["status"] == "checkout_unavailable"
    assert wa.texts, "the customer must be told nothing was charged"
    assert "nothing was charged" in wa.texts[-1].lower()


async def test_unknown_button_is_honest() -> None:
    wa = RecordingWA()

    result = await dispatch_button_action(
        "zzz:1", "919999999999", pool=None, wa_client=wa
    )

    assert result["status"] == "unknown_action"
    assert wa.texts, "the customer must be told the button is stale"
    assert "out of date" in wa.texts[-1].lower()


@pytest.mark.parametrize(
    "button_id",
    [
        "cart:clear",
        "plan:add",
        "reorder:last",
        "addr:set:a1",
        "item:change:spin",
        "budget:raise:approval:150000",
    ],
)
async def test_write_tap_without_database_is_honest(button_id: str) -> None:
    wa = RecordingWA()

    result = await dispatch_button_action(
        button_id, "919999999999", pool=None, wa_client=wa
    )

    assert result["status"] == "button_unavailable"
    assert wa.texts, "the customer must be told the tap did nothing"
    assert "nothing changed" in wa.texts[-1].lower()
    assert result["message"] == wa.texts[-1]


@pytest.mark.db
async def test_write_tap_from_unknown_number_is_honest() -> None:
    from backend.database import get_db_pool

    pool = await get_db_pool()
    wa_id = "91" + f"{int(time.time() * 1000) % 10**10:010d}"
    wa = RecordingWA()

    result = await dispatch_button_action(
        "cart:clear", wa_id, pool=pool, wa_client=wa
    )

    assert result["status"] == "unknown_user"
    assert wa.texts, "the customer must be told the tap did nothing"
    assert "couldn't find your account" in wa.texts[-1].lower()
