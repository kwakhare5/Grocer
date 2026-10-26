"""Grocer v1.0 — Global Pytest Fixtures.

Database-backed tests are marked `db` and only run when TEST_DATABASE_URL
points at a dedicated test database. They never touch DATABASE_URL.
"""

# Ensure repository root is on sys.path
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import settings


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "db: needs PostgreSQL; requires TEST_DATABASE_URL"
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if settings.TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(
        reason="TEST_DATABASE_URL not set; refusing to use the production database"
    )
    for item in items:
        if item.get_closest_marker("db"):
            item.add_marker(skip)


@pytest.fixture(autouse=True)
async def _prepare_test_database(request: pytest.FixtureRequest) -> None:
    """Build the test schema lazily for marked tests in an isolated database."""
    if request.node.get_closest_marker("db") is None:
        return
    if not settings.TEST_DATABASE_URL:
        return
    from backend.database import apply_migrations, get_db_pool

    await get_db_pool()
    await apply_migrations()


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Path to committed real staging fixtures."""
    return Path(__file__).resolve().parent / "fixtures"
