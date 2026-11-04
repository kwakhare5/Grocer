"""Grocer — website-first connect flow.

The website may name a number, but the number must message the bot with the
matching one-time code before any OAuth link is sent.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from test_whatsapp_webhook import RecordingWA, SignedRequest, _message, _new_wa_id

from backend.channels.link_tokens import issue_link_token, verify_link_token
from backend.main import app


@pytest.fixture(autouse=True)
def _clear_start_limits():
    from backend.channels import connect_flow

    connect_flow._attempts.clear()
    yield
    connect_flow._attempts.clear()


async def _post_start(phone: str) -> tuple[int, dict]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/whatsapp/start", json={"phone": phone})
    return resp.status_code, resp.json()


async def test_start_mints_a_short_lived_token_for_the_typed_number():
    status, data = await _post_start("+91 98765 43210")

    assert status == 200
    assert data["expiresIn"] == 600
    assert verify_link_token(data["token"]) == "919876543210"


async def test_start_rejects_numbers_that_are_not_indian_mobiles():
    for phone in ("12345", "5876543210", "+1 415 555 0100"):
        status, data = await _post_start(phone)
        assert status == 422, phone
        assert "10-digit" in data["detail"]


async def test_start_rate_limits_one_client():
    for _ in range(5):
        status, _data = await _post_start("9876543210")
        assert status == 200

    status, data = await _post_start("9876543210")
    assert status == 429
    assert "Too many attempts" in data["detail"]


@pytest.mark.db
@pytest.mark.scripted
async def test_matching_sender_gets_the_oauth_link():
    from backend.channels.whatsapp import handle_webhook

    wa_id = _new_wa_id()
    token = issue_link_token(wa_id, ttl_seconds=600)
    outbound = RecordingWA()

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text=f"connect {token}")),
        wa_client=outbound,
    )

    assert result["status"] == "connect_confirmed"
    assert len(outbound.ctas) == 1
    to_wa_id, _body, _button, url = outbound.ctas[0]
    assert to_wa_id == wa_id
    assert "?t=" in url
    assert verify_link_token(url.split("?t=", 1)[1]) == wa_id


@pytest.mark.db
@pytest.mark.scripted
async def test_a_different_sender_never_gets_the_oauth_link():
    from backend.channels.whatsapp import handle_webhook

    typed_number = _new_wa_id()
    sender = _new_wa_id()
    token = issue_link_token(typed_number, ttl_seconds=600)
    outbound = RecordingWA()

    result = await handle_webhook(
        SignedRequest(_message(sender, text=f"connect {token}")),
        wa_client=outbound,
    )

    assert result["status"] == "connect_mismatch"
    assert outbound.ctas == []
    assert typed_number not in " ".join(text for _to, text in outbound.texts)


@pytest.mark.db
@pytest.mark.scripted
async def test_expired_or_forged_codes_get_an_honest_reply():
    from backend.channels.whatsapp import handle_webhook

    wa_id = _new_wa_id()
    expired = issue_link_token(wa_id, ttl_seconds=-10)
    outbound = RecordingWA()

    result = await handle_webhook(
        SignedRequest(_message(wa_id, text=f"connect {expired}")),
        wa_client=outbound,
    )

    assert result["status"] == "connect_invalid"
    assert outbound.ctas == []
    assert "invalid or expired" in outbound.texts[0][1].lower()

    forged = f"{wa_id}.9999999999.deadbeef"
    outbound = RecordingWA()
    result = await handle_webhook(
        SignedRequest(_message(wa_id, text=f"connect {forged}")),
        wa_client=outbound,
    )
    assert result["status"] == "connect_invalid"
    assert outbound.ctas == []
