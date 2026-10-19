"""Tests for Slice D2g: strict claim check branches, robust deduplication, and model constants."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock
import pytest

from backend.agent.claim_check import check_reply_claims_with_reason
from backend.agent.config import BRAIN_MODEL, SMALL_CHECK_MODEL, BRAIN_FALLBACK_MODEL
from backend.agent.session import CustomerSession


# ============================================================================
# FIX 1: Strict two-branch claim check with no fall-through
# ============================================================================

@pytest.mark.asyncio
async def test_claim_check_with_reason_returns_none_is_called_once_and_gives_unclear_other():
    """A fake client whose with_reason returns None is called exactly once and gives (unclear, other)."""
    fake_client = AsyncMock()
    fake_client.api_key = "test-api-key"
    fake_client.generate_structured_with_reason = AsyncMock(return_value=None)
    fake_client.generate_structured = AsyncMock()

    verdict, reason = await check_reply_claims_with_reason(
        fake_client,
        "Nandini milk is Rs 30.",
        facts_text="Nandini Milk 500ml is Rs 30",
    )

    assert verdict == "unclear"
    assert reason == "other"
    assert fake_client.generate_structured_with_reason.call_count == 1
    assert fake_client.generate_structured.call_count == 0


# ============================================================================
# FIX 2: Deduplication with pack size equality & order-independent matching
# ============================================================================

def test_dedupe_no_pid_pack_mismatch_stays_two():
    """'Milk' (no pack) and 'Milk 1L' stay two."""
    session = CustomerSession("cust-pack-mismatch")
    session.update_product_facts([
        {"name": "Milk", "price": 30.0}
    ])
    session.update_product_facts([
        {"name": "Milk", "pack_size": "1L", "price": 60.0}
    ])
    assert len(session.recent_product_facts) == 2
    assert session.recent_product_facts[0].get("pack_size") is None
    assert session.recent_product_facts[1].get("pack_size") == "1L"


def test_dedupe_spin_fact_then_pid_only_fact_gives_one_entry_same_as_reverse():
    """spin fact then pid-only fact gives one entry, same as the reverse order."""
    # Order A: spin fact then pid-only fact
    session_a = CustomerSession("cust-order-a")
    session_a.update_product_facts([
        {"product_id": "p-milk-1", "spin_id": "spin-milk-500", "name": "Nandini Milk", "price": 28.0}
    ])
    session_a.update_product_facts([
        {"product_id": "p-milk-1", "name": "Nandini Milk", "price": 30.0}
    ])
    assert len(session_a.recent_product_facts) == 1
    assert session_a.recent_product_facts[0]["product_id"] == "p-milk-1"
    assert session_a.recent_product_facts[0]["spin_id"] == "spin-milk-500"
    assert session_a.recent_product_facts[0]["price"] == 30.0

    # Order B: pid-only fact then spin fact
    session_b = CustomerSession("cust-order-b")
    session_b.update_product_facts([
        {"product_id": "p-milk-1", "name": "Nandini Milk", "price": 28.0}
    ])
    session_b.update_product_facts([
        {"product_id": "p-milk-1", "spin_id": "spin-milk-500", "name": "Nandini Milk", "price": 30.0}
    ])
    assert len(session_b.recent_product_facts) == 1
    assert session_b.recent_product_facts[0]["product_id"] == "p-milk-1"
    assert session_b.recent_product_facts[0]["spin_id"] == "spin-milk-500"
    assert session_b.recent_product_facts[0]["price"] == 30.0


def test_dedupe_production_shape_spin_then_pid_only_and_reverse():
    """All 6 keys present, empty ones None or '':
    spin fact then pid-only fact keeps spin_id, pack_size and price;
    pid-only then spin fact keeps both."""
    # 1. Spin fact then pid-only fact
    session_1 = CustomerSession("cust-prod-shape-1")
    spin_fact = {
        "product_id": "pid-milk-100",
        "spin_id": "spin-milk-500",
        "sku_id": "sku-milk-500",
        "name": "Amul Taaza Fresh Toned Milk",
        "pack_size": "500 ml",
        "price": 28.0,
    }
    pid_only_fact = {
        "product_id": "pid-milk-100",
        "spin_id": None,
        "sku_id": "",
        "name": "Amul Taaza Fresh Toned Milk",
        "pack_size": None,
        "price": None,
    }
    session_1.update_product_facts([spin_fact])
    session_1.update_product_facts([pid_only_fact])

    assert len(session_1.recent_product_facts) == 1
    f1 = session_1.recent_product_facts[0]
    assert f1["product_id"] == "pid-milk-100"
    assert f1["spin_id"] == "spin-milk-500"
    assert f1["sku_id"] == "sku-milk-500"
    assert f1["name"] == "Amul Taaza Fresh Toned Milk"
    assert f1["pack_size"] == "500 ml"
    assert f1["price"] == 28.0

    # 2. Pid-only fact then spin fact
    session_2 = CustomerSession("cust-prod-shape-2")
    session_2.update_product_facts([pid_only_fact])
    session_2.update_product_facts([spin_fact])

    assert len(session_2.recent_product_facts) == 1
    f2 = session_2.recent_product_facts[0]
    assert f2["product_id"] == "pid-milk-100"
    assert f2["spin_id"] == "spin-milk-500"
    assert f2["sku_id"] == "sku-milk-500"
    assert f2["name"] == "Amul Taaza Fresh Toned Milk"
    assert f2["pack_size"] == "500 ml"
    assert f2["price"] == 28.0


# ============================================================================
# FIX 3: Settings defaults and backend-wide model scan test
# ============================================================================

def test_settings_defaults_match_locked_decisions(monkeypatch):
    """Settings defaults match the locked decisions with GROCER_* and GEMINI_* env vars cleared via monkeypatch."""
    import os
    for k in list(os.environ.keys()):
        if k.startswith("GROCER_") or k.startswith("GEMINI_"):
            monkeypatch.delenv(k, raising=False)

    from backend.config import Settings
    s = Settings(_env_file=None)
    assert s.GEMINI_MODEL == "gemini-3.5-flash"
    assert s.GEMINI_SMALL_CHECK_MODEL == "gemini-3.5-flash-lite"
    assert s.GEMINI_FALLBACK_MODEL == "gemini-3-flash-preview"

    from backend.agent.config import BRAIN_MODEL, SMALL_CHECK_MODEL, BRAIN_FALLBACK_MODEL
    assert BRAIN_MODEL == "gemini-3.5-flash"
    assert SMALL_CHECK_MODEL == "gemini-3.5-flash-lite"
    assert BRAIN_FALLBACK_MODEL == "gemini-3-flash-preview"


def test_no_hardcoded_model_name_strings():
    """Scan every .py file under backend/ except backend/config.py and tests, for all three model strings."""
    backend_dir = Path(__file__).resolve().parent.parent
    config_file = backend_dir / "config.py"
    model_strings = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]

    scanned = 0
    for file_path in backend_dir.rglob("*.py"):
        if file_path.resolve() == config_file.resolve():
            continue
        if "tests" in file_path.parts or "experiments" in file_path.parts:
            continue
        scanned += 1
        content = file_path.read_text(encoding="utf-8")
        for model in model_strings:
            assert model not in content, f"Found hardcoded '{model}' in {file_path}"
    assert scanned > 0
