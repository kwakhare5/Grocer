import pytest
import httpx
from backend.main import app

@pytest.mark.asyncio
async def test_get_price_feed():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/prices/feed")
        assert response.status_code == 200
        feed = response.json()
        assert isinstance(feed, list)
        
        # Verify keys exist in the returned commodity structures
        if feed:
            item = feed[0]
            assert "id" in item
            assert "name" in item
            assert "unit" in item
            assert "current" in item
            assert "avg30d" in item
            assert "signal" in item
            assert "history" in item
            assert isinstance(item["history"], list)


@pytest.mark.asyncio
async def test_get_price_alerts():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/prices/alerts")
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        
        # Alerts should only contain spikes or dips
        for alert in data["alerts"]:
            assert alert["signal"] in ["SPIKE", "DIP"]


@pytest.mark.asyncio
async def test_price_agent_tracking():
    from backend.database.connection import AsyncSessionLocal
    from backend.agents.price_agent import track_and_alert_prices
    
    async with AsyncSessionLocal() as db:
        result = await track_and_alert_prices(db)
        assert "prices_recorded" in result
        assert "alerts_triggered" in result
        assert result["prices_recorded"] > 0
        assert isinstance(result["alerts_triggered"], list)
