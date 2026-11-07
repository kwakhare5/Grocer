"""A button tap must never claim an action that did not happen."""

from __future__ import annotations

import asyncio
import time

import pytest

from backend.channels.button_router import dispatch_button_action


class RecordingWA:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def send_text_message(self, to_wa_id: str, text: str) -> None:
        self.texts.append(text)


class _FakeConn:
    async def fetchval(self, query: str, *args: object) -> str | None:
        if "grocer.users" in query:
            return "user-1"
        if "active_address_id" in query:
            return "addr-1"
        return None


class _FakeAcquire:
    async def __aenter__(self) -> _FakeConn:
        return _FakeConn()

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakePool:
    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire()


@pytest.mark.scripted
async def test_button_dispatch_reaches_auth_without_waiting(monkeypatch) -> None:
    """The Python dispatch path must not wait on Swiggy or a remote DB."""

    async def _no_client(user_id: str) -> None:
        return None

    monkeypatch.setattr(
        "backend.integrations.commerce.token_vault.resolve_user_client", _no_client
    )
    wa = RecordingWA()

    started = time.perf_counter()
    result = await dispatch_button_action(
        "cart:clear", "919999999999", pool=_FakePool(), wa_client=wa
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    await asyncio.sleep(0)

    assert result["status"] == "auth_required"
    assert wa.texts
    assert elapsed_ms < 100


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
