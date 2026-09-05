"""Phase 8: CommercePort and Customer Replenishment Tests (Spec Section 5.1, 28, & 38.9).

Validates:
- Seam 1: CommercePort ABC contract, domain models, and exception taxonomy.
- Seam 2: MockCommerceAdapter deterministic Mumbai dark store simulation.
- Seam 3: SwiggyMCPAdapter protocol compliance, credential safety, and error handling.
- Seam 4: CustomerService household replenishment workflow with CommercePort.
- Seam 5: FastAPI customer commerce endpoints (/addresses, /cart, /checkout, /track).
"""
from __future__ import annotations

import pytest
import uuid
from backend.integrations.commerce.port import CommercePort
from backend.integrations.commerce.models import (
    DeliveryAddress,
    CommerceProductItem,
    ProductVariant,
    CartItemUpdate,
    CommerceCart,
    PaymentOption,
    CommerceOrderResult,
    DeliveryTrackingStatus,
)
from backend.integrations.commerce.exceptions import (
    CommerceError,
    UnconfirmedCheckoutError,
    AddressNotServiceableError,
    ItemOutOfStockError,
    MinOrderNotMetError,
)
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter


@pytest.mark.asyncio
async def test_commerce_port_cannot_be_instantiated():
    with pytest.raises(TypeError):
        CommercePort()


@pytest.mark.asyncio
async def test_mock_adapter_get_addresses():
    adapter = MockCommerceAdapter()
    addresses = await adapter.get_addresses("cust-123")
    assert len(addresses) >= 2
    home = next((a for a in addresses if a.label == "Home"), None)
    assert home is not None
    assert "Mumbai" in home.city
    assert home.is_serviceable is True


@pytest.mark.asyncio
async def test_mock_adapter_search_and_go_to_items():
    adapter = MockCommerceAdapter()
    addresses = await adapter.get_addresses("cust-123")
    home = addresses[0]

    # Go-to items (frequent staples)
    go_to = await adapter.get_go_to_items(home.id)
    assert len(go_to) >= 2
    assert any("Milk" in item.name for item in go_to)
    assert any(len(item.variants) > 0 for item in go_to)

    # Search items
    results = await adapter.search_products(home.id, "bread")
    assert len(results) >= 1
    assert "Bread" in results[0].name
    assert results[0].variants[0].spin_id is not None
    assert results[0].variants[0].price > 0


@pytest.mark.asyncio
async def test_mock_adapter_cart_operations():
    adapter = MockCommerceAdapter()
    addresses = await adapter.get_addresses("cust-123")
    home = addresses[0]
    go_to = await adapter.get_go_to_items(home.id)
    first_variant = go_to[0].variants[0]

    # 1. Update cart
    cart = await adapter.update_cart(
        items=[CartItemUpdate(spin_id=first_variant.spin_id, quantity=2)],
        cart_id="test-cart-1",
    )
    assert cart.cart_id == "test-cart-1"
    assert len(cart.items) == 1
    assert cart.items[0].quantity == 2
    assert cart.item_total == first_variant.price * 2
    assert cart.grand_total > cart.item_total  # includes delivery or packaging fee

    # 2. Fetch cart
    fetched_cart = await adapter.get_cart("test-cart-1")
    assert fetched_cart.cart_id == "test-cart-1"
    assert len(fetched_cart.items) == 1

    # 3. Clear cart
    cleared = await adapter.clear_cart("test-cart-1")
    assert cleared is True
    empty_cart = await adapter.get_cart("test-cart-1")
    assert len(empty_cart.items) == 0
    assert empty_cart.grand_total == 0.0


@pytest.mark.asyncio
async def test_mock_adapter_payment_options():
    adapter = MockCommerceAdapter()
    options = await adapter.get_payment_options("test-cart-1")
    assert len(options) >= 2
    methods = [opt.method for opt in options]
    assert "UPI" in methods
    assert "COD" in methods


@pytest.mark.asyncio
async def test_mock_adapter_checkout_requires_explicit_confirmation():
    adapter = MockCommerceAdapter()
    # Add item to cart
    await adapter.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)],
        cart_id="test-cart-guard",
    )

    # Calling checkout without explicit confirmation must raise UnconfirmedCheckoutError!
    with pytest.raises(UnconfirmedCheckoutError) as exc_info:
        await adapter.checkout(
            cart_id="test-cart-guard",
            payment_method="UPI",
            explicit_confirmation=False,
        )
    assert "explicit confirmation" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_mock_adapter_checkout_confirmed_and_tracking():
    adapter = MockCommerceAdapter()
    await adapter.update_cart(
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=2)],
        cart_id="test-cart-exec",
    )

    order = await adapter.checkout(
        cart_id="test-cart-exec",
        payment_method="UPI",
        explicit_confirmation=True,
    )
    assert order.order_id is not None
    assert order.status == "ORDER_CONFIRMED"
    assert len(order.items) == 1
    assert order.grand_total > 0

    # Tracking
    tracking = await adapter.track_order(order.order_id)
    assert tracking.order_id == order.order_id
    assert tracking.status in ["ORDER_CONFIRMED", "PACKING", "OUT_FOR_DELIVERY", "DELIVERED"]
    assert tracking.eta_minutes is not None
    assert tracking.eta_minutes > 0


# ===========================================================================
# Seam 3 Tests: SwiggyMCPAdapter and Adapter Factory
# ===========================================================================
from unittest.mock import AsyncMock, patch, MagicMock
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.integrations.commerce.factory import get_commerce_adapter
from backend.integrations.commerce.exceptions import (
    ProviderAuthError,
    UpstreamTimeoutError,
    ItemOutOfStockError,
    AddressNotServiceableError,
)


@pytest.mark.asyncio
async def test_swiggy_adapter_checkout_requires_explicit_confirmation():
    adapter = SwiggyMCPAdapter(auth_token="secret-token-xyz")
    with pytest.raises(UnconfirmedCheckoutError) as exc_info:
        await adapter.checkout(
            cart_id="swiggy-cart-1",
            payment_method="UPI",
            explicit_confirmation=False,
        )
    assert "explicit confirmation" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_swiggy_adapter_token_never_logged_or_exposed():
    adapter = SwiggyMCPAdapter(auth_token="super-secret-token-12345")
    repr_str = repr(adapter)
    assert "super-secret-token-12345" not in repr_str
    assert "***" in repr_str


@pytest.mark.asyncio
async def test_swiggy_adapter_get_addresses_success():
    adapter = SwiggyMCPAdapter(auth_token="test-token")
    mock_payload = {
        "success": True,
        "data": [
            {
                "id": "addr-swiggy-1",
                "label": "Home",
                "formattedAddress": "Flat 402, Sea Green, Bandra West, Mumbai 400050",
                "city": "Mumbai",
                "pincode": "400050",
                "serviceable": True,
            }
        ],
    }

    with patch.object(adapter, "_call_mcp_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_payload
        addresses = await adapter.get_addresses("cust-1")
        assert len(addresses) == 1
        assert addresses[0].id == "addr-swiggy-1"
        assert addresses[0].label == "Home"
        assert addresses[0].is_serviceable is True
        mock_call.assert_called_once_with("get_addresses", {})


@pytest.mark.asyncio
async def test_swiggy_adapter_search_products():
    adapter = SwiggyMCPAdapter(auth_token="test-token")
    mock_payload = {
        "success": True,
        "data": {
            "products": [
                {
                    "productId": "sw-p-1",
                    "name": "Amul Taaza Milk",
                    "category": "Dairy",
                    "variants": [
                        {
                            "spinId": "SW-SPIN-MILK",
                            "name": "Amul Taaza 1L",
                            "packSize": "1L",
                            "price": 66.0,
                            "mrp": 68.0,
                            "inStock": True,
                        }
                    ],
                }
            ]
        },
    }

    with patch.object(adapter, "_call_mcp_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_payload
        products = await adapter.search_products(address_id="addr-1", query="milk")
        assert len(products) == 1
        assert products[0].name == "Amul Taaza Milk"
        assert products[0].variants[0].spin_id == "SW-SPIN-MILK"
        mock_call.assert_called_once_with(
            "search_products", {"addressId": "addr-1", "query": "milk"}
        )


@pytest.mark.asyncio
async def test_swiggy_adapter_error_classification():
    adapter = SwiggyMCPAdapter(auth_token="test-token")

    # 1. Out of stock error
    with patch.object(adapter, "_call_mcp_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = {
            "success": False,
            "error": {"message": "Item out of stock at this address"},
        }
        with pytest.raises(ItemOutOfStockError):
            await adapter.update_cart(
                items=[CartItemUpdate(spin_id="SW-SPIN-OOS", quantity=1)],
                address_id="addr-1",
            )

    # 2. Address not serviceable
    with patch.object(adapter, "_call_mcp_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = {
            "success": False,
            "error": {"message": "Address not serviceable for Instamart"},
        }
        with pytest.raises(AddressNotServiceableError):
            await adapter.search_products(address_id="addr-unserviceable", query="bread")


@pytest.mark.asyncio
async def test_commerce_adapter_factory():
    with patch("backend.integrations.commerce.factory.settings") as mock_settings:
        mock_settings.COMMERCE_ADAPTER_TYPE = "mock"
        mock_adapter = get_commerce_adapter()
        assert isinstance(mock_adapter, MockCommerceAdapter)

        mock_settings.COMMERCE_ADAPTER_TYPE = "swiggy_mcp"
        mock_settings.SWIGGY_AUTH_TOKEN = "token-abc"
        swiggy_adapter = get_commerce_adapter()
        assert isinstance(swiggy_adapter, SwiggyMCPAdapter)


# ===========================================================================
# Seam 4 Tests: CustomerService with CommercePort
# ===========================================================================
from backend.services.customer.service import CustomerService
from backend.services.simulation.engine import SimulationEngine
from backend.models.core import Customer, Inventory


@pytest.mark.asyncio
async def test_customer_service_commerce_port_delegation(db_session):
    sim = SimulationEngine(seed=42, historical_days=3)
    await sim.initialize(db_session)
    await db_session.commit()

    service = CustomerService()
    customers = await service.list_customers(db_session)
    assert len(customers) > 0
    cust_id = uuid.UUID(customers[0]["customer_id"])

    # Test address resolution
    addresses = await service.get_customer_addresses(cust_id)
    assert len(addresses) >= 1
    assert addresses[0].is_serviceable is True

    # Test cart update and retrieval
    cart = await service.update_customer_cart(
        cust_id,
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=2)],
    )
    assert len(cart.items) == 1
    assert cart.items[0].quantity == 2

    fetched_cart = await service.get_customer_cart(cust_id)
    assert fetched_cart.grand_total == cart.grand_total


@pytest.mark.asyncio
async def test_customer_service_checkout_explicit_confirmation_guard(db_session):
    service = CustomerService()
    cust_id = uuid.uuid4()

    # Pre-populate cart
    await service.update_customer_cart(
        cust_id,
        items=[CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=1)],
    )

    # Calling checkout without confirmation must raise UnconfirmedCheckoutError
    with pytest.raises(UnconfirmedCheckoutError):
        await service.checkout_customer(
            customer_id=cust_id,
            cart_id=f"cart-{cust_id}",
            payment_method="UPI",
            explicit_confirmation=False,
        )


@pytest.mark.asyncio
async def test_customer_service_checkout_confirmed_and_order_sync(db_session):
    sim = SimulationEngine(seed=42, historical_days=3)
    await sim.initialize(db_session)
    await db_session.commit()

    service = CustomerService()
    customers = await service.list_customers(db_session)
    cust_id = uuid.UUID(customers[0]["customer_id"])

    # 1. Update cart
    cart = await service.update_customer_cart(
        cust_id,
        items=[
            CartItemUpdate(spin_id="SPIN-MILK-1L", quantity=2),
            CartItemUpdate(spin_id="SPIN-BREAD-400G", quantity=1),
        ],
    )
    assert cart.grand_total > 0

    # 2. Checkout with explicit confirmation
    order_res = await service.checkout_customer(
        customer_id=cust_id,
        cart_id=f"cart-{cust_id}",
        payment_method="UPI",
        explicit_confirmation=True,
        db=db_session,
    )
    assert order_res.status == "ORDER_CONFIRMED"
    assert order_res.order_id is not None

    # 3. Track order
    tracking = await service.track_customer_order(order_res.order_id)
    assert tracking.order_id == order_res.order_id
    assert tracking.eta_minutes > 0


# ===========================================================================
# Seam 5 Tests: Customer Commerce API Endpoints
# ===========================================================================
from backend.main import create_app
from backend.database import get_db
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_api_adapter_info(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/customers/adapter-info")
        assert resp.status_code == 200
        data = resp.json()
        assert "adapter_type" in data
        assert data["adapter_type"] in ["mock", "swiggy_mcp"]


@pytest.mark.asyncio
async def test_api_customer_addresses_and_go_to_items(db_session):
    sim = SimulationEngine(seed=42, historical_days=3)
    await sim.initialize(db_session)
    await db_session.commit()

    service = CustomerService()
    customers = await service.list_customers(db_session)
    cust_id = customers[0]["customer_id"]

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Addresses
        addr_resp = await client.get(f"/api/customers/{cust_id}/addresses")
        assert addr_resp.status_code == 200
        addresses = addr_resp.json()
        assert len(addresses) >= 1
        assert addresses[0]["is_serviceable"] is True

        # 2. Go-to items
        go_to_resp = await client.get(f"/api/customers/{cust_id}/go-to-items")
        assert go_to_resp.status_code == 200
        go_to = go_to_resp.json()
        assert len(go_to) >= 2


@pytest.mark.asyncio
async def test_api_cart_crud_operations(db_session):
    sim = SimulationEngine(seed=42, historical_days=3)
    await sim.initialize(db_session)
    await db_session.commit()

    service = CustomerService()
    customers = await service.list_customers(db_session)
    cust_id = customers[0]["customer_id"]

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Update cart
        payload = {"items": [{"spin_id": "SPIN-MILK-1L", "quantity": 2}]}
        upd_resp = await client.post(f"/api/customers/{cust_id}/cart", json=payload)
        assert upd_resp.status_code == 200
        cart = upd_resp.json()
        assert len(cart["items"]) == 1
        assert cart["items"][0]["quantity"] == 2
        assert cart["grand_total"] > 0

        # Get cart
        get_resp = await client.get(f"/api/customers/{cust_id}/cart")
        assert get_resp.status_code == 200
        assert get_resp.json()["cart_id"] == cart["cart_id"]

        # Clear cart
        del_resp = await client.delete(f"/api/customers/{cust_id}/cart")
        assert del_resp.status_code == 200
        empty_resp = await client.get(f"/api/customers/{cust_id}/cart")
        assert len(empty_resp.json()["items"]) == 0


@pytest.mark.asyncio
async def test_api_checkout_unconfirmed_rejected(db_session):
    cust_id = str(uuid.uuid4())
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pre-fill cart
        await client.post(
            f"/api/customers/{cust_id}/cart",
            json={"items": [{"spin_id": "SPIN-MILK-1L", "quantity": 1}]},
        )

        # Unconfirmed checkout must return 400
        resp = await client.post(
            f"/api/customers/{cust_id}/checkout",
            json={"payment_method": "UPI", "explicit_confirmation": False},
        )
        assert resp.status_code == 400
        assert "explicit confirmation" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_checkout_confirmed_and_tracking(db_session):
    sim = SimulationEngine(seed=42, historical_days=3)
    await sim.initialize(db_session)
    await db_session.commit()

    service = CustomerService()
    customers = await service.list_customers(db_session)
    cust_id = customers[0]["customer_id"]

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pre-fill cart
        await client.post(
            f"/api/customers/{cust_id}/cart",
            json={"items": [{"spin_id": "SPIN-MILK-1L", "quantity": 2}]},
        )

        # Confirmed checkout
        resp = await client.post(
            f"/api/customers/{cust_id}/checkout",
            json={"payment_method": "UPI", "explicit_confirmation": True},
        )
        assert resp.status_code == 200
        order_data = resp.json()
        assert "order_id" in order_data
        assert order_data["status"] == "ORDER_CONFIRMED"

        # Track order
        order_id = order_data["order_id"]
        track_resp = await client.get(f"/api/customers/{cust_id}/orders/{order_id}/track")
        assert track_resp.status_code == 200
        track_data = track_resp.json()
        assert track_data["order_id"] == order_id
        assert track_data["eta_minutes"] > 0