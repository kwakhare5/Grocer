"""Health endpoint status must follow the real database check."""

import os
import subprocess
import sys
from pathlib import Path

from backend.main import health_response

ROOT = Path(__file__).resolve().parent.parent


def test_health_returns_503_when_database_is_down():
    res = health_response(False)
    assert res.status_code == 503


def test_health_returns_200_when_database_is_up():
    res = health_response(True)
    assert res.status_code == 200


def test_app_starts_even_when_database_is_unreachable():
    """A dead DB must not stop the API from booting; /health reports it."""
    env = os.environ.copy()
    env.pop("PYTEST_CURRENT_TEST", None)
    env["DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:1/postgres"
    code = (
        "import asyncio\n"
        "from backend.database import resolve_database_url\n"
        "from backend.main import app\n"
        "assert '127.0.0.1:1' in resolve_database_url(), resolve_database_url()\n"
        "async def main():\n"
        "    async with app.router.lifespan_context(app):\n"
        "        print('alive')\n"
        "asyncio.run(main())\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "alive" in result.stdout
