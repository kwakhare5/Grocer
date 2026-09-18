"""Browser intent API session-capability and ownership regressions."""

from __future__ import annotations

import uuid

import pytest

from backend.intent.session import OrchestratorSessionStore
from backend.intent.storage import default_intent_store


async def _create_session(client):  # type: ignore[no-untyped-def]
    response = await client.post("/api/intent/sessions", json={})
    assert response.status_code == 201
    data = response.json()
    return data["session_id"], data["session_capability"], data["customer_id"]


@pytest.mark.asyncio
async def test_server_issues_opaque_session_and_capability(client) -> None:
    session_id, capability, customer_id = await _create_session(client)

    assert session_id.startswith("sess_")
    assert customer_id.startswith("cust_web_")
    assert len(session_id) >= 30
    assert len(capability) >= 32


@pytest.mark.asyncio
async def test_caller_cannot_select_browser_customer_identity(client) -> None:
    response = await client.post(
        "/api/intent/sessions",
        json={"customer_id": f"victim-{uuid.uuid4()}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unauthenticated_swiggy_oauth_api_is_not_exposed(client) -> None:
    response = await client.get(
        "/api/swiggy/status", params={"customer_id": "victim-customer"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_and_read_require_matching_session_capability(client) -> None:
    session_id, capability, _customer_id = await _create_session(client)

    no_capability = await client.post(
        "/api/intent/chat",
        json={"session_id": session_id, "message": "get 1L milk"},
    )
    wrong_capability = await client.get(
        f"/api/intent/sessions/{session_id}",
        headers={"X-Grocer-Session-Capability": "wrong-capability"},
    )
    valid = await client.post(
        "/api/intent/chat",
        json={"session_id": session_id, "message": "get 1L milk"},
        headers={"X-Grocer-Session-Capability": capability},
    )

    assert no_capability.status_code == 403
    assert wrong_capability.status_code == 403
    assert valid.status_code == 200


@pytest.mark.asyncio
async def test_capability_cannot_access_another_session(client) -> None:
    first_id, first_capability, _ = await _create_session(client)
    second_id, _second_capability, _ = await _create_session(client)

    response = await client.delete(
        f"/api/intent/sessions/{second_id}",
        headers={"X-Grocer-Session-Capability": first_capability},
    )

    assert first_id != second_id
    assert response.status_code == 403


def test_store_rejects_cross_customer_session_reuse() -> None:
    store = OrchestratorSessionStore()
    store.get_or_create("same-session", "customer-a")

    with pytest.raises(ValueError, match="belongs to a different customer"):
        store.get_or_create("same-session", "customer-b")


@pytest.mark.asyncio
async def test_delete_clears_session_and_intent_history(client) -> None:
    session_id, capability, _ = await _create_session(client)
    headers = {"X-Grocer-Session-Capability": capability}
    chat = await client.post(
        "/api/intent/chat",
        json={"session_id": session_id, "message": "get 1L milk"},
        headers=headers,
    )
    assert chat.status_code == 200
    assert default_intent_store.get_active(session_id) is not None

    deleted = await client.delete(f"/api/intent/sessions/{session_id}", headers=headers)

    assert deleted.status_code == 200
    assert default_intent_store.get_active(session_id) is None
