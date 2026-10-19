"""Tests for Slice D2f: Gemini structured call with reasons, spacing assertion, and session dedupe invariants."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch
import httpx
import pytest

from backend.agent.claim_check import check_reply_claims_with_reason
from backend.agent.gemini import GeminiClient
from backend.agent.session import CustomerSession


# ============================================================================
# FIX 1: Offline tests for claim_check and GeminiClient structured calls
# ============================================================================

@pytest.mark.asyncio
async def test_claim_check_offline_quota_429():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"code": 429, "message": "Resource exhausted"}})

    client = GeminiClient(api_key="mock-key")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        verdict, reason = await check_reply_claims_with_reason(
            client,
            "Nandini milk is Rs 30.",
            facts_text="Nandini Milk 500ml is Rs 30",
        )
        assert verdict == "unclear"
        assert reason == "quota 429"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_claim_check_offline_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Request timed out", request=request)

    client = GeminiClient(api_key="mock-key")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        verdict, reason = await check_reply_claims_with_reason(
            client,
            "Nandini milk is Rs 30.",
            facts_text="Nandini Milk 500ml is Rs 30",
        )
        assert verdict == "unclear"
        assert reason == "timeout"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_claim_check_offline_bad_json_parse_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "candidates": [{
                "content": {"parts": [{"text": "not-valid-json"}]}
            }]
        })

    client = GeminiClient(api_key="mock-key")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        verdict, reason = await check_reply_claims_with_reason(
            client,
            "Nandini milk is Rs 30.",
            facts_text="Nandini Milk 500ml is Rs 30",
        )
        assert verdict == "unclear"
        assert reason == "parse error"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_claim_check_offline_good_json_gives_verdict():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "candidates": [{
                "content": {"parts": [{"text": json.dumps({"verdict": "supported"})}]}
            }]
        })

    client = GeminiClient(api_key="mock-key")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        verdict, reason = await check_reply_claims_with_reason(
            client,
            "Nandini milk is Rs 30.",
            facts_text="Nandini Milk 500ml is Rs 30",
        )
        assert verdict == "supported"
        assert reason is None
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_claim_check_offline_assert_spacing_path_used():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "candidates": [{
                "content": {"parts": [{"text": json.dumps({"verdict": "supported"})}]}
            }]
        })

    client = GeminiClient(api_key="mock-key")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        # First call sets _last_call_time
        res1, reason1 = await client.generate_structured_with_reason(
            model="gemini-3.5-flash-lite",
            prompt="test",
            response_schema={},
        )
        assert res1 == {"verdict": "supported"}
        assert reason1 is None
        assert client._last_call_time > 0

        # Second immediate call must trigger spacing sleep
        sleep_durations: list[float] = []
        real_sleep = asyncio.sleep

        async def capture_sleep(delay: float, *args, **kwargs):
            sleep_durations.append(delay)
            return await real_sleep(0)

        with patch("asyncio.sleep", side_effect=capture_sleep):
            res2, reason2 = await client.generate_structured_with_reason(
                model="gemini-3.5-flash-lite",
                prompt="test 2",
                response_schema={},
            )
            assert res2 == {"verdict": "supported"}
            assert reason2 is None

        assert len(sleep_durations) >= 1
        assert 0.0 < sleep_durations[0] <= 0.2
    finally:
        await client.close()


# ============================================================================
# FIX 2: Session deduplication tests
# ============================================================================

def test_dedupe_pid_only_then_pid_plus_spin_gives_one_entry():
    session = CustomerSession("cust-dedupe-1")
    # Step 1: fact saved with product_id only
    session.update_product_facts([
        {"product_id": "prod-amul-milk", "name": "Amul Milk", "price": 30.0}
    ])
    assert len(session.recent_product_facts) == 1
    assert session.recent_product_facts[0]["product_id"] == "prod-amul-milk"
    assert session.recent_product_facts[0].get("spin_id") is None

    # Step 2: same product_id later arrives with a spin_id
    session.update_product_facts([
        {"product_id": "prod-amul-milk", "spin_id": "spin-amul-500", "name": "Amul Milk", "price": 30.0}
    ])
    assert len(session.recent_product_facts) == 1
    assert session.recent_product_facts[0]["product_id"] == "prod-amul-milk"
    assert session.recent_product_facts[0]["spin_id"] == "spin-amul-500"


def test_dedupe_same_pid_with_name_spacing_case_change_gives_one_entry():
    session = CustomerSession("cust-dedupe-2")
    session.update_product_facts([
        {"product_id": "prod-butter-1", "name": "  Amul   Butter  ", "price": 50.0}
    ])
    assert len(session.recent_product_facts) == 1

    session.update_product_facts([
        {"product_id": "prod-butter-1", "name": "amul butter", "price": 52.0}
    ])
    assert len(session.recent_product_facts) == 1
    assert session.recent_product_facts[0]["price"] == 52.0
    assert session.recent_product_facts[0]["name"] == "amul butter"


def test_dedupe_two_different_variants_with_different_spin_ids_stay_two():
    session = CustomerSession("cust-dedupe-3")
    session.update_product_facts([
        {"product_id": "prod-bread", "spin_id": "spin-bread-400g", "name": "Wheat Bread 400g", "price": 40.0}
    ])
    assert len(session.recent_product_facts) == 1

    session.update_product_facts([
        {"product_id": "prod-bread", "spin_id": "spin-bread-800g", "name": "Wheat Bread 800g", "price": 75.0}
    ])
    assert len(session.recent_product_facts) == 2
    spin_ids = [p["spin_id"] for p in session.recent_product_facts]
    assert spin_ids == ["spin-bread-400g", "spin-bread-800g"]
