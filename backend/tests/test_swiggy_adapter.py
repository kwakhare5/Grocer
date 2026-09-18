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


def test_adapter_parses_product_variants() -> None:
    adapter = SwiggyMCPAdapter()
    products = adapter._parse_products(
        [
            {
                "productId": "milk",
                "displayName": "Amul Milk",
                "category": "dairy",
                "variations": [
                    {
                        "spinId": "spin-1",
                        "skuId": "sku-1",
                        "displayName": "Amul Milk 1L",
                        "quantityDescription": "1 L",
                        "price": {"offerPrice": 66, "mrp": 68},
                        "isInStockAndAvailable": True,
                    }
                ],
            }
        ]
    )
    assert len(products) == 1
    assert products[0].variants[0].spin_id == "spin-1"
    assert products[0].variants[0].sku_id == "sku-1"
    assert products[0].variants[0].price == 66


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
