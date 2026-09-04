import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(client: AsyncClient) -> None:
    """Health endpoint should return 200 with status healthy."""
    response = await client.get('/api/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'healthy'
    assert data['service'] == 'GROCER v2'


@pytest.mark.asyncio
async def test_health_endpoint_reports_db_status(client: AsyncClient) -> None:
    """Health endpoint should report database connectivity."""
    response = await client.get('/api/health')
    data = response.json()
    assert 'database' in data
    assert data['database'] in ('connected', 'disconnected')
