"""Consented, encrypted household purchase cadence for WhatsApp suggestions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from statistics import median
import re
from typing import Any

from backend.agent.product_policy import is_restricted_medical_product
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.exceptions import ProviderAuthError
from backend.integrations.commerce.token_vault import EncryptedPayloadCodec


_OPT_IN = re.compile(
    r"^(?:turn on|enable|start) (?:grocery |replenishment )?reminders? "
    r"(daily|weekly) at (1[0-2]|0?[1-9])(?:\s*:\s*([0-5][0-9]))?\s*(am|pm)$",
    re.I,
)
_CHANGE = re.compile(
    r"^change reminder frequency to (daily|weekly) at (1[0-2]|0?[1-9])"
    r"(?:\s*:\s*([0-5][0-9]))?\s*(am|pm)$", re.I,
)
_STOCK_LEFT = re.compile(
    r"^(?:i (?:still )?have|i have enough) (.+?) for ([1-9]|[1-5][0-9]|60)"
    r" (?:more )?days?$", re.I,
)
_RAN_OUT = re.compile(r"^(.+?) ran out(?: today)?$", re.I)
_STOP = {"pause reminders", "pause grocery reminders", "stop reminders", "stop grocery reminders"}
_RESUME = {"resume reminders", "resume grocery reminders"}
_DELETE = {"delete my reminder history", "delete my replenishment history"}
_CHECK = {"what might be running low", "what might be running low?", "what am i running low on", "check my groceries"}
_STATUS = {"reminder settings", "show reminder settings", "my reminder settings"}
_INDIA_TIME = timezone(timedelta(hours=5, minutes=30))
logger = logging.getLogger("grocer.agent.replenishment")


class PostgresReplenishmentStore:
    def __init__(self, pool: Any, encryption_key: str) -> None:
        self.pool = pool
        self.codec = EncryptedPayloadCodec(encryption_key)

    async def _load(self, customer_id: str) -> dict[str, Any] | None:
        row = await self.pool.fetchrow(
            "SELECT ciphertext FROM grocer_internal.replenishment WHERE customer_id=$1",
            customer_id,
        )
        return self.codec.decrypt(row["ciphertext"]) if row else None

    async def _change(self, customer_id: str, **changes: Any) -> bool:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT ciphertext FROM grocer_internal.replenishment WHERE customer_id=$1 FOR UPDATE",
                    customer_id,
                )
                if row is None:
                    return False
                state = self.codec.decrypt(row["ciphertext"])
                if "corrections" in changes:
                    state.setdefault("corrections", {}).update(changes.pop("corrections"))
                state.update(changes)
                if "paused" in changes:
                    await conn.execute(
                        """UPDATE grocer_internal.replenishment
                           SET ciphertext=$2, next_sync_at=$3, paused=$4, updated_at=now() WHERE customer_id=$1""",
                        customer_id, self.codec.encrypt(state),
                        None if changes["paused"] else datetime.now(timezone.utc),
                        changes["paused"],
                    )
                else:
                    await conn.execute(
                        "UPDATE grocer_internal.replenishment SET ciphertext=$2, updated_at=now() WHERE customer_id=$1",
                        customer_id, self.codec.encrypt(state),
                    )
                return True

    async def delete(self, customer_id: str) -> None:
        await self.pool.execute(
            "DELETE FROM grocer_internal.replenishment WHERE customer_id=$1", customer_id,
        )

    async def reply(self, customer_id: str, text: str, commerce: CommercePort) -> str | None:
        command = text.strip().casefold()
        match = _OPT_IN.fullmatch(text.strip()) or _CHANGE.fullmatch(text.strip())
        if match:
            changing = bool(_CHANGE.fullmatch(text.strip()))
            frequency, hour_text, minute_text, period = match.groups()
            hour = int(hour_text) % 12 + (12 if period.casefold() == "pm" else 0)
            minute = int(minute_text or 0)
            if changing and await self._load(customer_id) is None:
                return "Reminders are not on. To opt in, say 'turn on grocery reminders daily at 9 am'."
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        "SELECT ciphertext FROM grocer_internal.replenishment WHERE customer_id=$1 FOR UPDATE",
                        customer_id,
                    )
                    state = self.codec.decrypt(row["ciphertext"]) if row else {"orders": {}, "corrections": {}}
                    state.update(frequency=frequency.casefold(), hour=hour, minute=minute, paused=False)
                    if row:
                        await conn.execute(
                            """UPDATE grocer_internal.replenishment
                               SET ciphertext=$2, paused=false, next_sync_at=now(), updated_at=now() WHERE customer_id=$1""",
                            customer_id, self.codec.encrypt(state),
                        )
                    else:
                        await conn.execute(
                            "INSERT INTO grocer_internal.replenishment (customer_id, ciphertext) VALUES ($1, $2)",
                            customer_id, self.codec.encrypt(state),
                        )
            return (f"Grocery reminders are set for {frequency.casefold()} at "
                    f"{int(hour_text)}:{minute:02d} {period.upper()} (India time). "
                    "I can estimate what may be running low when you ask. "
                    "Automatic WhatsApp reminders are awaiting message-template approval.")
        if command in _DELETE:
            await self.delete(customer_id)
            return "Your reminder settings and learned purchase history have been deleted."
        if command in _STOP:
            if not await self._change(customer_id, paused=True):
                return "Reminders are not on. To opt in, say 'turn on grocery reminders daily at 9 am'."
            return "Grocery reminders are paused. Your purchase estimates remain saved until you delete them."
        if command in _RESUME:
            if not await self._change(customer_id, paused=False):
                return "Reminders are not on. To opt in, say 'turn on grocery reminders daily at 9 am'."
            return "Grocery reminders are resumed. Automatic WhatsApp alerts still await template approval."
        if command in _STATUS:
            state = await self._load(customer_id)
            if state is None:
                return "Reminders are off. To opt in, say 'turn on grocery reminders daily at 9 am'."
            hour = state["hour"] % 12 or 12
            period = "PM" if state["hour"] >= 12 else "AM"
            status = "paused" if state["paused"] else "on"
            return (f"Reminders are {status}, {state['frequency']} at "
                    f"{hour}:{state['minute']:02d} {period} (India time). "
                    "Say 'pause grocery reminders' or 'delete my reminder history' to change this.")
        stock_left = _STOCK_LEFT.fullmatch(text.strip())
        ran_out = _RAN_OUT.fullmatch(text.strip())
        if stock_left or ran_out:
            state = await self._load(customer_id)
            if state is None:
                return "To save stock corrections, opt in first: 'turn on grocery reminders daily at 9 am'."
            item = (stock_left or ran_out).group(1).strip()
            if is_restricted_medical_product(item):
                return "I can track grocery essentials, but not medical products here."
            tracked = {
                " ".join(name.casefold().split())
                for order in state["orders"].values() for name in order["items"]
            }
            key = " ".join(item.casefold().split())
            matches = [name for name in tracked if key in name or name in key]
            if len(matches) > 1:
                return "I found several matching items. Please name the exact pack you mean."
            if len(matches) == 1:
                key = matches[0]
            days = int(stock_left.group(2)) if stock_left else 0
            until = (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()
            corrections = state.get("corrections", {})
            corrections[key] = until
            if not await self._change(customer_id, corrections=corrections):
                return "Your reminder history changed. Please try again."
            return (f"Got it. I'll estimate that {item} may last {days} days longer. "
                    "This changes the reminder estimate, not your basket."
                    if stock_left else
                    f"Got it. I'll count {item} as possibly out now. I haven't added anything to your basket.")
        if command in _CHECK:
            state = await self._load(customer_id)
            if state is None:
                return "To use purchase history, opt in first: 'turn on grocery reminders daily at 9 am'."
            try:
                complete = await self._sync_orders(customer_id, commerce)
            except ProviderAuthError:
                raise
            except Exception:
                return "I couldn't refresh your Swiggy purchases right now. Please try again later."
            state = await self._load(customer_id)
            if state is None:
                return "Your reminder history was deleted; I won't use those purchases."
            suggestions = self._due_items(state)
            if not suggestions:
                if not complete:
                    return "I couldn't verify the items in some Swiggy orders, so the estimate is incomplete. Please try again later."
                return ("I don't have enough repeated delivered purchases to estimate what is running low yet. "
                        "I cannot see what is actually left at home.")
            return ("Based on past purchases, you may be running low on "
                    + ", ".join(suggestions[:5])
                    + ". Is any of that actually needed? I won't add anything without you asking."
                    + (" Some order details could not be checked." if not complete else ""))
        if "remind" in command or "running low" in command:
            return ("For estimates, say 'what might be running low?'. "
                    "To opt in, say 'turn on grocery reminders daily at 9 am'. "
                    "You can choose daily or weekly and another time.")
        return None

    async def refresh_due(self, commerce: CommercePort) -> int:
        """Claim one consented household for a bounded background history refresh."""
        row = await self.pool.fetchrow(
            """WITH due AS (
                   SELECT customer_id FROM grocer_internal.replenishment
                   WHERE paused=false AND next_sync_at <= now() ORDER BY next_sync_at LIMIT 1
                   FOR UPDATE SKIP LOCKED
               )
               UPDATE grocer_internal.replenishment r
               SET next_sync_at=now()+interval '15 minutes'
               FROM due WHERE r.customer_id=due.customer_id
               RETURNING r.customer_id, r.next_sync_at, r.ciphertext"""
        )
        if row is None:
            return 0
        state = self.codec.decrypt(row["ciphertext"])
        try:
            with commerce.customer_scope(row["customer_id"]):
                complete = await self._sync_orders(row["customer_id"], commerce)
        except Exception as exc:
            logger.warning("Consented order-history refresh will retry after %s", type(exc).__name__)
            next_sync = datetime.now(timezone.utc) + timedelta(hours=1)
        else:
            if not complete:
                next_sync = datetime.now(timezone.utc) + timedelta(hours=1)
            else:
                local_next = datetime.now(_INDIA_TIME) + timedelta(
                    days=1 if state["frequency"] == "daily" else 7,
                )
                next_sync = local_next.replace(
                    hour=state["hour"], minute=state["minute"], second=0, microsecond=0,
                ).astimezone(timezone.utc)
        await self.pool.execute(
            """UPDATE grocer_internal.replenishment SET next_sync_at=$3, updated_at=now()
               WHERE customer_id=$1 AND next_sync_at=$2""",
            row["customer_id"], row["next_sync_at"], next_sync,
        )
        return 1

    async def _sync_orders(self, customer_id: str, commerce: CommercePort) -> bool:
        # Only called after a stored opt-in was checked by reply().
        orders = await commerce.get_orders(count=20, active_only=False)
        observed: dict[str, dict[str, Any]] = {}
        complete = True
        for order in orders:
            if order.normalized_status != "DELIVERED" or not order.created_at:
                continue
            try:
                when = datetime.fromisoformat(order.created_at.replace("Z", "+00:00"))
                if when.tzinfo is None or when > datetime.now(timezone.utc):
                    continue
            except ValueError:
                continue
            items = order.items
            if not items:
                try:
                    details = await commerce.get_order_details(order.order_id)
                    items = details.items
                except Exception:
                    complete = False
                    continue
            names = [item.name.strip() for item in items
                     if item.quantity > 0 and not item.removed and item.name.strip()
                     and not is_restricted_medical_product(item.name)]
            if names:
                observed[order.order_id] = {"day": when.date().isoformat(), "items": names}
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT ciphertext FROM grocer_internal.replenishment WHERE customer_id=$1 FOR UPDATE",
                    customer_id,
                )
                if row is None:
                    return False
                state = self.codec.decrypt(row["ciphertext"])
                state["orders"].update(observed)
                # Keep a bounded, derived purchase record rather than provider responses.
                ordered = sorted(state["orders"].items(), key=lambda pair: pair[1]["day"])
                state["orders"] = dict(ordered[-100:])
                await conn.execute(
                    "UPDATE grocer_internal.replenishment SET ciphertext=$2, updated_at=now() WHERE customer_id=$1",
                    customer_id, self.codec.encrypt(state),
                )
        return complete

    @staticmethod
    def _due_items(state: dict[str, Any]) -> list[str]:
        purchases: dict[str, list[datetime]] = {}
        labels: dict[str, str] = {}
        for order in state["orders"].values():
            day = datetime.fromisoformat(order["day"]).replace(tzinfo=timezone.utc)
            for name in set(order["items"]):
                key = " ".join(name.casefold().split())
                purchases.setdefault(key, []).append(day)
                labels[key] = name
        due = []
        today = datetime.now(timezone.utc)
        for key, dates in purchases.items():
            correction = state.get("corrections", {}).get(key)
            if correction:
                if datetime.fromisoformat(correction).date() <= datetime.now(timezone.utc).date():
                    due.append(labels[key])
                continue
            dates = sorted(set(dates))
            if len(dates) < 2:
                continue
            intervals = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
            intervals = [days for days in intervals if 1 <= days <= 60]
            if intervals and today >= dates[-1] + timedelta(days=median(intervals)):
                due.append(labels[key])
        return sorted(due)
