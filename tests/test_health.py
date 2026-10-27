"""Health endpoint status must follow the real database check."""

from backend.main import health_response


def test_health_returns_503_when_database_is_down():
    res = health_response(False)
    assert res.status_code == 503


def test_health_returns_200_when_database_is_up():
    res = health_response(True)
    assert res.status_code == 200
