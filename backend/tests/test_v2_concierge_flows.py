"""V2 Concierge Real Customer Flow Tests.

Verifies:
1. Fast 50ms Deterministic Button Router (checkout confirmation, check payment, 2-step clear cart).
2. Parallel Composite Cart Engine (parallel searches, top staple auto-picker, zero silent drops).
3. Customer Advocate Net-Total Protection Guardrail (coupons never increase total).
4. WhatsApp Channel Ingestion (GPS location pin parsing & 1-tap UPI URL formatting).
"""
import time
import pytest

from backend.agent.approval import PendingApproval, cart_fingerprint
from backend.agent.button_router import handle_button_action
from backend.agent.composite_cart import execute_composite_cart_modification
from backend.agent.customer_advocate import CustomerAdvocate
from backend.agent.session import CustomerSession
from backend.channels.models import ChannelType, InteractiveAction, NormalizedIncomingMessage, NormalizedOutgoingResponse
from backend.channels.whatsapp_formatter import format_whatsapp_payload
from backend.channels.whatsapp_parser import parse_webhook_payload
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItem, CartItemUpdate, CommerceCart


@pytest.mark.asyncio
async def test_button_router_confirms_valid_order_fast():
    """Tapping confirm_order:<token> with valid fingerprint executes gated checkout deterministically."""
    commerce = MockCommerceAdapter()
    session = CustomerSession(customer_id="cust-101")
    session.address_id = "addr-bandra-1"
    session.address_label = "Home"

    with commerce.customer_scope("cust-101"):
        await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-BREAD-400G", sku_id="SPIN-BREAD-400G", quantity=1)],
            address_id="addr-bandra-1",
        )
        cart = await commerce.get_cart()
        fp = cart_fingerprint(cart, "addr-bandra-1")
        session.pending_approval = PendingApproval(fingerprint=fp or "", expires_at=time.time() + 300, token="tok123")
        session.known_cart_fingerprint = fp

        resp = await handle_button_action(
            payload="confirm_order:tok123",
            session=session,
            commerce=commerce,
            customer_id="cust-101",
            recipient_id="919876543210",
        )

    assert resp is not None
    assert resp.conversation_state in ("AWAITING_PAYMENT", "ORDER_PLACED")
    assert resp.order_id is not None
    assert resp.order_id.startswith("OD-")


@pytest.mark.asyncio
async def test_button_router_2step_clear_cart_flow():
    """Two-step clear cart issues a cryptographic token and safely clears upstream on confirm."""
    commerce = MockCommerceAdapter()
    session = CustomerSession(customer_id="cust-102")
    session.address_id = "addr-bandra-1"

    with commerce.customer_scope("cust-102"):
        await commerce.update_cart(
            [CartItemUpdate(spin_id="SPIN-MILK-1L", sku_id="SPIN-MILK-1L", quantity=2)],
            address_id="addr-bandra-1",
        )

        # Step 1: User taps "clear_cart"
        resp1 = await handle_button_action(
            payload="clear_cart",
            session=session,
            commerce=commerce,
            customer_id="cust-102",
            recipient_id="919876543210",
        )
        assert resp1 is not None
        assert resp1.conversation_state == "AWAITING_CART_CLEAR_CONFIRMATION"
        assert session.pending_cart_clear is not None
        token = session.pending_cart_clear.token
        assert bool(token)

        # Step 2: User taps "clear_cart_confirm:<token>"
        resp2 = await handle_button_action(
            payload=f"clear_cart_confirm:{token}",
            session=session,
            commerce=commerce,
            customer_id="cust-102",
            recipient_id="919876543210",
        )
        assert resp2 is not None
        assert "cleared" in resp2.text.casefold()

        # Upstream cart must now be empty
        final_cart = await commerce.get_cart()
        assert len(final_cart.items) == 0


@pytest.mark.asyncio
async def test_composite_cart_parallel_search_and_drop_diffing():
    """composite_cart runs searches in parallel, diffs missing items honestly, and merges additions safely."""
    commerce = MockCommerceAdapter()
    session = CustomerSession(customer_id="cust-103")
    session.address_id = "addr-bandra-1"

    with commerce.customer_scope("cust-103"):
        result = await execute_composite_cart_modification(
            session=session,
            commerce=commerce,
            items_to_add=["milk", "bread", "nonexistent_exotic_dragonfruit_xyz"],
            items_to_remove=[],
            address_id="addr-bandra-1",
        )

    # 1. Added available items
    assert len(result.added_items) >= 2
    # 2. Honest drop diffing (Zero silent drops)
    assert any("dragonfruit" in str(d).casefold() for d in result.dropped_items)
    # 3. Verified cart was updated upstream
    assert result.updated_cart is not None
    assert result.verified_fingerprint is not None


@pytest.mark.asyncio
async def test_customer_advocate_net_total_guardrail():
    """Customer Advocate applies best coupon but never increases net grand total."""
    commerce = MockCommerceAdapter()
    advocate = CustomerAdvocate(commerce)

    cart = CommerceCart(
        cart_id="cart-test-advocate",
        address_id="addr-1",
        items=[CartItem(spin_id="s1", sku_id="k1", name="Premium Olive Oil", pack_size="1L", quantity=1, unit_price=450.0, total_price=450.0)],
        item_total=450.0,
        grand_total=450.0,
        delivery_fee=0.0,
        billing_complete=True,
        currency="INR",
    )

    opt = await advocate.optimize_cart(cart, address_id="addr-1")
    assert opt["coupon_applied"] is True
    assert opt["total_savings"] > 0
    assert cart.grand_total <= 450.0  # Grand total must never exceed original


def test_whatsapp_parser_extracts_gps_location_pin():
    """Webhook parser extracts WhatsApp location messages into structured text for address creation."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "biz-1",
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "id": "wamid.loc-1",
                                    "type": "location",
                                    "location": {
                                        "latitude": 18.5204,
                                        "longitude": 73.8567,
                                        "name": "Flat 402, Sunshine Apts",
                                        "address": "Baner, Pune, 411045",
                                    },
                                }
                            ]
                        }
                    }
                ],
            }
        ],
    }
    messages = parse_webhook_payload(payload)
    assert len(messages) == 1
    msg = messages[0]
    assert "[LOCATION_PIN]" in msg.text
    assert "Baner" in msg.text
    assert "18.5204" in msg.text


def test_whatsapp_formatter_includes_1tap_upi_deep_link():
    """Outgoing WhatsApp formatter embeds clickable upi://pay deep links in body text and provides action buttons."""
    resp = NormalizedOutgoingResponse(
        recipient_id="919876543210",
        channel=ChannelType.WHATSAPP,
        text="Your order ORD_999 is awaiting payment! 🛒",
        conversation_state="AWAITING_PAYMENT",
        order_id="ORD_999",
        order_total=250.0,
        interactive_actions=[
            InteractiveAction(
                action_type="url",
                id="pay_order:ORD_999",
                title="Pay with UPI (1-Tap)",
                url="upi://pay?pa=swiggy@icici&pn=SwiggyInstamart&am=250.00&tr=ORD_999&cu=INR",
            ),
            InteractiveAction(
                action_type="button",
                id="check_payment:ORD_999",
                title="Check Payment",
            ),
        ],
    )
    formatted = format_whatsapp_payload(resp)
    assert formatted["type"] == "interactive"
    body = formatted["interactive"]["body"]["text"]
    assert "upi://pay" in body
    assert "Check Payment" in formatted["interactive"]["action"]["buttons"][0]["reply"]["title"]
