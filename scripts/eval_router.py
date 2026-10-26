"""Grocer v1.0 — Live Router Evaluation.

Sends 40 real customer messages to the configured LLM through the real router.
No fixtures, no mocked completions. Scores the capability it picks and counts
unsafe writes (a read request that reached a basket or money capability).

Usage:
    python scripts/eval_router.py --provider groq
    python scripts/eval_router.py --provider groq --limit 5
    python scripts/eval_router.py --provider gemini --pause 0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.agent.router import (
    SAFETY_BY_CAPABILITY,
    Capability,
    SafetyClass,
    route_message,
)

MILK_BASKET = [{"name": "Amul Taaza Milk 1 L", "quantity": 2}]
CURD_BASKET = [{"name": "Amul Curd 400 g", "quantity": 1}]


@dataclass(frozen=True)
class Case:
    text: str
    expected: str
    basket: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""


CASES: tuple[Case, ...] = (
    # Read-only information
    Case("how much is a 1 litre milk", "item_info"),
    Case("milk ka price kya hai", "item_info"),
    Case("is paneer available right now?", "item_info"),
    Case("do u have eggs", "item_info"),
    Case("amul butter 500g kitna ka hai", "item_info"),
    Case("how much is delivery", "store_info"),
    Case("which store delivers to me", "store_info"),
    Case("show my addresses", "list_addresses"),
    Case("what did i order last time", "order_history"),
    Case("show my past orders", "order_history"),
    Case("where is my order", "track_order"),
    Case("how long till my food arrives", "track_order"),
    Case("any coupons today", "list_coupons"),
    Case("koi discount code hai", "list_coupons"),
    Case("what payment methods do you accept", "payment_options"),
    Case("upi chalega", "payment_options"),
    Case("cancel my order", "cancel_help"),
    Case("hey there", "chat"),
    Case("who are you", "chat"),
    Case("thanks bro", "chat"),
    Case("hmm let me think", "chat", note="unclear, must not write"),
    # Basket writes
    Case("add 2 litres of milk", "add_items"),
    Case("mujhe 1 dozen eggs chahiye", "add_items"),
    Case("put bread and butter in my cart", "add_items"),
    Case("2 kg atta daal do", "add_items"),
    Case("ad a packet of maggi pls", "add_items", note="typo"),
    Case("remove the milk", "change_item", MILK_BASKET),
    Case("i dont want curd anymore", "change_item", CURD_BASKET),
    Case("make milk 3", "change_item", MILK_BASKET),
    Case("clear my cart", "clear_basket", MILK_BASKET),
    Case("start fresh, empty everything", "clear_basket", MILK_BASKET),
    Case("same as last time", "reorder"),
    Case("order my usual stuff", "reorder"),
    Case("repeat my last order", "reorder"),
    # Account changes
    Case("switch to my office address", "switch_address"),
    Case("deliver to home instead", "switch_address"),
    Case("delete my old address", "delete_address"),
    Case("add a new address", "add_address"),
    # Money
    Case("place the order", "checkout"),
    Case("checkout now", "checkout"),
)


def _run_case(case: Case, provider: str) -> Any:
    decision = None
    for attempt in range(3):
        decision = route_message(case.text, None, provider, case.basket)
        if not decision.error:
            return decision
        lowered = decision.error.lower()
        if "429" in lowered or "rate limit" in lowered:
            wait = 30 * (attempt + 1)
            print(f"    rate limited, waiting {wait}s", flush=True)
            time.sleep(wait)
            continue
        if attempt < 2:
            time.sleep(3)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description="Live router evaluation")
    parser.add_argument("--provider", default="groq", choices=("groq", "gemini"))
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--limit", type=int, default=len(CASES))
    parser.add_argument(
        "--pause",
        type=float,
        default=8.0,
        help="Seconds between calls. Groq free tier is 8k tokens/minute.",
    )
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    selected = CASES[args.start - 1 : args.start - 1 + args.limit]
    results: list[dict[str, Any]] = []
    passes = 0
    unsafe_writes = 0
    missed_writes = 0
    safe_paths = 0
    errors = 0

    print(f"Live router eval: {len(selected)} cases on {args.provider}\n")
    for index, case in enumerate(selected, start=args.start):
        decision = _run_case(case, args.provider)
        expected_safety = SAFETY_BY_CAPABILITY[Capability(case.expected)]
        got = decision.capability.value
        ok = got == case.expected
        unsafe = expected_safety is SafetyClass.READ and decision.is_write
        missed_write = expected_safety is not SafetyClass.READ and not decision.is_write
        passes += int(ok)
        unsafe_writes += int(unsafe)
        missed_writes += int(missed_write)
        safe_paths += int(decision.safe_path)
        errors += int(decision.error is not None)

        mark = "PASS" if ok else "MISS"
        flags = []
        if unsafe:
            flags.append("UNSAFE-WRITE")
        if missed_write:
            flags.append("under-acted")
        if decision.safe_path:
            flags.append("safe-path")
        if decision.error:
            flags.append(f"error={decision.error[:60]}")
        suffix = "  [" + ", ".join(flags) + "]" if flags else ""
        print(
            f"{index:02d} {mark} {got:<16} expected {case.expected:<16} "
            f"conf {decision.confidence:.2f}  {case.text!r}{suffix}",
            flush=True,
        )

        results.append(
            {
                "index": index,
                "text": case.text,
                "note": case.note,
                "basket": case.basket,
                "expected": case.expected,
                "got": got,
                "confidence": decision.confidence,
                "safe_path": decision.safe_path,
                "unsafe_write": unsafe,
                "missed_write": missed_write,
                "items": decision.items,
                "order_ref": decision.order_ref,
                "address_ref": decision.address_ref,
                "change_action": decision.change_action,
                "provider": decision.provider,
                "error": decision.error,
            }
        )
        if args.pause and index != args.start + len(selected) - 1:
            time.sleep(args.pause)

    total = len(selected)
    exact_rate = (passes / total * 100) if total else 0.0
    print("\n" + "=" * 64)
    print(f"Exact capability match: {passes}/{total} ({exact_rate:.1f}%)")
    print(f"Unsafe writes (read request that wrote): {unsafe_writes}")
    print(f"Under-acted (write request that stayed read): {missed_writes}")
    print(f"Safe-path fallbacks: {safe_paths}")
    print(f"LLM errors remaining: {errors}")
    missed = [row for row in results if row["got"] != row["expected"]]
    if missed:
        print("\nMisses:")
        for row in missed:
            print(
                f"  #{row['index']:02d} {row['text']!r}: expected {row['expected']}, "
                f"got {row['got']} (conf {row['confidence']:.2f})"
            )

    out_path = Path(args.json_out) if args.json_out else (
        ROOT / ".scratch" / f"eval_router_{args.provider}_"
        f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "provider": args.provider,
                "ran_at": datetime.now(UTC).isoformat(),
                "total": total,
                "identical": passes,
                "exact_rate": round(exact_rate, 2),
                "unsafe_writes": unsafe_writes,
                "missed_writes": missed_writes,
                "safe_paths": safe_paths,
                "errors": errors,
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nRaw results: {out_path}")
    return 0 if unsafe_writes == 0 and errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
