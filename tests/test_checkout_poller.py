"""Checkout settlement must not block the event loop with sync Swiggy calls."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from backend.agent.checkout_settlement import check_and_settle_payment


class _FakeConn:
    async def execute(self, *args, **kwargs):
        return None

    async def fetchrow(self, query, *args):
        if "address_coords" in query:
            return {"latitude": 12.9, "longitude": 77.6}
        return None


class _ThreadRecordingClient:
    def __init__(self):
        self.threads: list[str] = []

    def check_payment_status(self, paas_id=None, order_id=None):
        self.threads.append(threading.current_thread().name)
        return SimpleNamespace(
            status="SUCCESS",
            isTerminalSuccess=True,
            confirmed=False,
            orderStatus="PLACED",
        )

    def confirm_order(self, order_id, paas_id=None):
        self.threads.append(threading.current_thread().name)
        return SimpleNamespace(result="success")

    def track_order(self, order_id, lat, lng):
        self.threads.append(threading.current_thread().name)
        return SimpleNamespace(
            status=SimpleNamespace(
                etaText="12 mins",
                etaMinutes=12,
                statusMessage="Packing",
            )
        )


@pytest.mark.scripted
async def test_settlement_swiggy_calls_run_off_the_event_loop_thread():
    client = _ThreadRecordingClient()

    await check_and_settle_payment(
        conn=_FakeConn(),
        swiggy_client=client,
        user_id="user-1",
        approval_id="approval-1",
        order_id="order-1",
        paas_id="paas-1",
    )

    assert len(client.threads) == 3
    assert threading.current_thread().name not in client.threads