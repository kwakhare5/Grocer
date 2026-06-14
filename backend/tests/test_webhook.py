import pytest
import httpx
from backend.main import app

@pytest.mark.asyncio
async def test_webhook_json():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Mock request from sandbox drawer
        response = await client.post(
            "/api/webhook/whatsapp",
            json={"phone": "+919999999999", "message": "YES"}
        )
        assert response.status_code == 200
        assert "response_message" in response.json()

@pytest.mark.asyncio
async def test_webhook_form():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Mock request from Twilio
        response = await client.post(
            "/api/webhook/whatsapp",
            data={"From": "whatsapp:+919999999999", "Body": "YES"}
        )
        assert response.status_code == 200
        assert "Response" in response.text


@pytest.mark.asyncio
async def test_household_sync_and_get_profile():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Rebuild models for a mock user to trigger household creation (no network calls)
        sync_response = await client.post("/api/household/test_user_999/rebuild-models")
        assert sync_response.status_code == 200
        assert "household_id" in sync_response.json()

        # 2. Get the household profile
        profile_response = await client.get("/api/household/test_user_999")
        assert profile_response.status_code == 200
        data = profile_response.json()
        assert data["user_id"] == "test_user_999"
        assert "id" in data

