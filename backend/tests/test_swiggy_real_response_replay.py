"""Sanitized, structural replays for live Swiggy Instamart provider behavior."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.integrations.commerce.exceptions import CommerceError
from backend.integrations.commerce.models import CartItemUpdate, CommerceCart
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter


_FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "swiggy"


def _fixture(name: str) -> dict[str, object]:
    """Load a sanitized structural provider response fixture."""
    return json.loads((_FIXTURE_DIRECTORY / name).read_text(encoding="utf-8"))


def _response(adapter: SwiggyMCPAdapter, fixture_name: str) -> httpx.Response:
    """Build a mocked MCP HTTP response from a sanitized fixture."""
    return httpx.Response(
        status_code=200,
        json=_fixture(fixture_name),
        request=httpx.Request("POST", adapter.base_url),
    )


@pytest.mark.asyncio
async def test_replay_get_cart_uses_empty_arguments_and_preserves_unknown_fields() -> None:
    """Omitted optional facts stay unknown and get_cart never sends cartId."""
    adapter = SwiggyMCPAdapter()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _response(adapter, "cart_omitted_optional_fields.json")
        cart = await adapter.get_cart("legacy-cart-reference")

    assert mock_post.call_args.kwargs["json"]["params"]["arguments"] == {}
    assert cart.cart_id is None
    assert cart.is_serviceable is None
    assert cart.items[0].max_quantity == 1


@pytest.mark.asyncio
async def test_replay_update_cart_reconciles_against_canonical_cart() -> None:
    """A provider acknowledgement is not enough: refetch the canonical cart."""
    adapter = SwiggyMCPAdapter()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            _response(adapter, "update_cart_reduced_quantity.json"),
            _response(adapter, "cart_omitted_optional_fields.json"),
        ]
        cart = await adapter.update_cart(
            items=[
                CartItemUpdate(
                    spin_id="spin-snack-100g",
                    quantity=3,
                    sku_id="sku-snack-100g",
                )
            ],
            cart_id="legacy-cart-reference",
            address_id="address-from-provider",
        )

    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0].kwargs["json"]["params"]["arguments"] == {
        "selectedAddressId": "address-from-provider",
        "items": [{"spinId": "spin-snack-100g", "skuId": "sku-snack-100g", "quantity": 3}],
    }
    assert mock_post.call_args_list[1].kwargs["json"]["params"]["arguments"] == {}
    assert cart.items[0].quantity == 1
    assert cart.reduced_quantity_items == [
        {
            "spinId": "spin-snack-100g",
            "itemName": "Plain snack",
            "requestedQuantity": 3,
            "cappedQuantity": 1,
            "reason": "Limited to 1",
        }
    ]


@pytest.mark.asyncio
async def test_replay_update_cart_requires_catalog_sku_id() -> None:
    """The adapter refuses an incomplete documented SKU-level mutation."""
    adapter = SwiggyMCPAdapter()

    with pytest.raises(CommerceError, match="SKU ID"):
        await adapter.update_cart(
            items=[CartItemUpdate(spin_id="spin-snack-100g", quantity=1)],
            address_id="address-from-provider",
        )


@pytest.mark.asyncio
async def test_replay_search_rejects_empty_query() -> None:
    """A live search must use a non-empty failed-intent query."""
    adapter = SwiggyMCPAdapter(auth_token="sanitized-test-token")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _response(adapter, "search_packaged_variants.json")
        with pytest.raises(CommerceError, match="non-empty"):
            await adapter.search_products("address-from-provider", "  ")

    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_replay_search_preserves_catalog_pack_and_cap_evidence() -> None:
    """Catalog evidence stays available to the quantity resolver."""
    adapter = SwiggyMCPAdapter()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _response(adapter, "search_packaged_variants.json")
        products = await adapter.search_products("address-from-provider", "plain snack")

    assert mock_post.call_args.kwargs["json"]["params"]["arguments"] == {
        "addressId": "address-from-provider",
        "query": "plain snack",
        "offset": 0,
    }
    assert products[0].variants[0].pack_size == "100 g"
    assert products[0].variants[0].max_quantity == 1


@pytest.mark.asyncio
async def test_replay_omitted_stock_and_availability_stay_unknown() -> None:
    """Omitted isInStockAndAvailable never coerces to False (or True)."""
    adapter = SwiggyMCPAdapter()

    async def _fake_post(self, *args, **kwargs):
        del args, kwargs
        return httpx.Response(
            status_code=200,
            json={
                "success": True,
                "data": {
                    "products": [
                        {
                            "productId": "product-plain",
                            "displayName": "Plain item",
                            "variations": [
                                {
                                    "spinId": "spin-plain",
                                    "skuId": "sku-plain",
                                    "displayName": "Plain item",
                                    "quantityDescription": "100 g",
                                    "price": {"mrp": 20, "offerPrice": 18},
                                }
                            ],
                        }
                    ]
                },
            },
            request=httpx.Request("POST", adapter.base_url),
        )

    with patch.object(httpx.AsyncClient, "post", new=_fake_post):
        products = await adapter.search_products("address-from-provider", "plain item")

    assert products[0].variants[0].in_stock is None

    cart = CommerceCart(cart_id=None, items=[], is_serviceable=None)
    assert cart.is_serviceable is None
