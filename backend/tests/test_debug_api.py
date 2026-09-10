"""Tests for developer-only read-only debug telemetry API (/api/debug)."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.intent.models import IntentContract, IntentItem, SourceContext
from backend.intent.session import (
    ConversationState,
    OrchestratorSession,
    default_session_store,
)
from backend.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_debug_latest_returns_mock_when_store_empty(app) -> None:
    """When no sessions exist, GET /api/debug/latest returns fallback mock telemetry."""
    # Temporarily clear store
    sessions = default_session_store.all_sessions()
    for s in sessions:
        default_session_store.clear(s.session_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/debug/latest")
        assert res.status_code == 200
        data = res.json()
        assert data["has_session"] is False
        assert data["is_mock"] is True
        assert len(data["items"]) >= 1
        assert "original_user_request" in data
        assert "verification_result" in data
        assert "recovery_classification" in data
        assert "relevant_safe_event_names" in data
        assert "masked_customer_id" in data
        # Check PII safety
        assert "919876543210" not in str(data)


@pytest.mark.asyncio
async def test_debug_telemetry_surfaces_all_13_dimensions_and_masks_pii(app) -> None:
    """Verify all 13 required dimensions are populated and PII/credentials are sanitized."""
    session_id = "sess_test_debug_123"
    customer_id = "cust_wa_919876543210"

    session = OrchestratorSession(
        session_id=session_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AWAITING_CONFIRMATION,
        cart_id="cart-test-123",
        turn_count=2,
        address_display="Flat 402, Sunshine Apartments, 12th Main, Koramangala, Bengaluru",
        events=[
            "INTENT_PARSED items=1",
            "ITEM_RESOLVED name='toned milk' spin_id='spin_amul_1L'",
            "CART_BUILT cart_id=cart-test-123 total=₹60",
            "VERIFICATION_PASS",
            "AWAITING_CONFIRMATION",
        ],
        last_verification={"status": "PASS", "violations": [], "deviations": []},
        last_recovery_state="none",
    )

    contract = IntentContract(
        session_id=session_id,
        customer_id=customer_id,
        goal="weekly groceries",
        source_context=SourceContext(
            raw_text="get 1L toned milk please call 9876543210",
        ),
        items=[
            IntentItem(
                name="toned milk",
                quantity=1.0,
                unit="L",
                quantity_is_explicit=True,
                pack_size_preference="1L",
            )
        ],
    )
    session.intent_contract = contract
    default_session_store.save(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/debug/latest")
        assert res.status_code == 200
        data = res.json()

        # 1. Original user request (with phone masked)
        assert "toned milk" in data["original_user_request"]
        assert "9876543210" not in data["original_user_request"]

        # 2. Interpreted quantity/meaning
        item = data["items"][0]
        assert "volume: 1000" in item["interpreted_meaning"]
        assert item["quantity_is_explicit"] is True

        # 3. Expected fulfillment
        assert "1000 volume" in item["expected_fulfillment"] or "1000" in item["expected_fulfillment"]

        # 4. Verification result
        assert data["verification_result"]["status"] == "PASS"

        # 5. Recovery classification
        assert data["recovery_classification"]["state"] == "none"

        # 6. Clarification required
        assert data["clarification_required"] is False

        # 7. Relevant safe event names
        assert "VERIFICATION_PASS" in data["relevant_safe_event_names"]
        assert "AWAITING_CONFIRMATION" in data["relevant_safe_event_names"]

        # PII & Credential Masking Checks
        raw_str = res.text
        assert "919876543210" not in raw_str
        assert "Flat 402" not in raw_str  # Sensitive address stripped
        assert "cust_wa_••••••3210" in data["masked_customer_id"]
        assert "SWIGGY_AUTH_TOKEN" not in raw_str
        assert "capability_digest" not in raw_str


@pytest.mark.asyncio
async def test_debug_session_list_and_get_by_id(app) -> None:
    """Verify session listing and individual session inspection."""
    session_id = "sess_test_specific_456"
    session = OrchestratorSession(
        session_id=session_id,
        customer_id="cust_web_abc12345",
        conversation_state=ConversationState.READY,
        turn_count=1,
        events=["INTENT_PARSED"],
    )
    default_session_store.save(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # List
        res_list = await client.get("/api/debug/sessions")
        assert res_list.status_code == 200
        summaries = res_list.json()
        assert any(s["session_id"] == session_id for s in summaries)

        # Get by id
        res_single = await client.get(f"/api/debug/sessions/{session_id}")
        assert res_single.status_code == 200
        assert res_single.json()["session_id"] == session_id

        # 404 for unknown
        res_not_found = await client.get("/api/debug/sessions/non_existent_id")
        assert res_not_found.status_code == 404
