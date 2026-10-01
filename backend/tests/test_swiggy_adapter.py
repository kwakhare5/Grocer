"""Focused tests for the active Swiggy CommercePort adapter boundary."""
from __future__ import annotations

import pytest

from backend.integrations.commerce.exceptions import UnconfirmedCheckoutError
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter


def test_adapter_masks_credentials_in_repr() -> None:
    adapter = SwiggyMCPAdapter(auth_token="secret-token")
    rendered = repr(adapter)
    assert "secret-token" not in rendered
    assert "token=***" in rendered


@pytest.mark.asyncio
async def test_checkout_rejects_missing_explicit_confirmation() -> None:
    adapter = SwiggyMCPAdapter()
    with pytest.raises(UnconfirmedCheckoutError):
        await adapter.checkout(
            cart_id="cart",
            payment_method="COD",
            explicit_confirmation=False,
            address_id="address",
        )
