import pytest
import httpx
from backend.main import app

@pytest.mark.asyncio
async def test_get_recipes_list():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # demo_user_001 is seeded in the test database
        response = await client.get("/api/recipes/demo_user_001")
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "recipes" in data
        assert isinstance(data["recipes"], list)


@pytest.mark.asyncio
async def test_parse_recipe_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "recipe": "Sunday Chicken Biryani",
            "servings": 6,
            "household_id": "demo_user_001"
        }
        # Note: This will invoke the LangGraph agent which calls Claude.
        # Since we have the API key configured, it will run the live integration flow.
        response = await client.post("/api/recipes/parse", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert "recipe" in data
        assert "servings" in data
        assert "you_have" in data
        assert "you_need" in data
        assert "cart_items" in data
        assert "estimated_cost" in data
        assert "ready_to_cook" in data


@pytest.mark.asyncio
async def test_pin_recipe_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "household_id": "demo_user_001",
            "recipe_name": "Paneer Butter Masala",
            "servings": 4,
            "ingredients": [
                {"name": "Paneer", "quantity": 400, "unit": "g"},
                {"name": "Butter", "quantity": 100, "unit": "g"}
            ],
            "pinned_for": "2026-06-20T12:00:00Z",
            "cuisine": "North Indian"
        }
        response = await client.post("/api/recipes/pin", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "recipe_id" in data
        assert "pinned_for" in data
