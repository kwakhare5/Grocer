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

