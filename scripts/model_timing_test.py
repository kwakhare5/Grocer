"""Timing benchmark for Gemini models across thinking configurations.

Tests 3 settings, 5 runs each, with a Hinglish grocery prompt and a search_products tool:
1. gemini-3.6-flash, thinking_level: low
2. gemini-3.6-flash, default thinking
3. gemini-3.5-flash-lite, thinking_level: minimal
"""
import os
import re
import sys
import time
import traceback
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.config import settings
from google import genai
from google.genai import types

PROMPT = "bhai 2 packet milk aur ek dozen anda chahiye"

SEARCH_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="search_products",
            description="Search products in grocery catalog by keyword query",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="Product search query",
                    ),
                },
                required=["query"],
            ),
        ),
    ]
)

SETTINGS = [
    {
        "name": "gemini-3.6-flash | thinking_level: low",
        "model": "gemini-3.6-flash",
        "config": types.GenerateContentConfig(
            tools=[SEARCH_TOOL],
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        ),
    },
    {
        "name": "gemini-3.6-flash | default thinking",
        "model": "gemini-3.6-flash",
        "config": types.GenerateContentConfig(
            tools=[SEARCH_TOOL],
        ),
    },
    {
        "name": "gemini-3.5-flash-lite | thinking_level: minimal",
        "model": "gemini-3.5-flash-lite",
        "config": types.GenerateContentConfig(
            tools=[SEARCH_TOOL],
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
        ),
    },
]


def run_benchmark():
    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: No GEMINI_API_KEY found in settings or environment.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    print("=" * 70)
    print("GEMINI MODEL TIMING BENCHMARK")
    print(f"Prompt: '{PROMPT}'")
    print("Settings: 3 | Runs per setting: 5")
    print("Rules: no temperature/top_p/top_k, no prefilled turn, no orders")
    print("=" * 70)

    summary = []

    for setting_idx, s in enumerate(SETTINGS, 1):
        print(f"\n--- Setting {setting_idx}: {s['name']} (Model: {s['model']}) ---")
        run_times = []
        function_calls_received = 0

        for run_idx in range(1, 6):
            start = time.perf_counter()
            try:
                response = client.models.generate_content(
                    model=s["model"],
                    contents=PROMPT,
                    config=s["config"],
                )
                elapsed = time.perf_counter() - start
                run_times.append(elapsed)

                has_fc = bool(response.function_calls)
                if has_fc:
                    function_calls_received += 1
                fc_names = [fc.name for fc in response.function_calls] if response.function_calls else []
                model_name = getattr(response, "model_version", None) or s["model"]

                print(
                    f"  Run {run_idx}/5: {elapsed:.3f}s | "
                    f"Function call: {has_fc} {fc_names if has_fc else ''} | "
                    f"Reported model: {model_name}"
                )
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait_sec = 25.0
                    match = re.search(r"retry in ([\d\.]+)s", err_str)
                    if match:
                        wait_sec = float(match.group(1)) + 1.0
                    print(f"  [Rate limit hit on run {run_idx}/5, waiting {wait_sec:.1f}s to retry...]")
                    time.sleep(wait_sec)
                    try:
                        start = time.perf_counter()
                        response = client.models.generate_content(
                            model=s["model"],
                            contents=PROMPT,
                            config=s["config"],
                        )
                        elapsed = time.perf_counter() - start
                        run_times.append(elapsed)

                        has_fc = bool(response.function_calls)
                        if has_fc:
                            function_calls_received += 1
                        fc_names = [fc.name for fc in response.function_calls] if response.function_calls else []
                        model_name = getattr(response, "model_version", None) or s["model"]

                        print(
                            f"  Run {run_idx}/5: {elapsed:.3f}s | "
                            f"Function call: {has_fc} {fc_names if has_fc else ''} | "
                            f"Reported model: {model_name}"
                        )
                        continue
                    except Exception:
                        pass

                elapsed = time.perf_counter() - start
                print(f"  Run {run_idx}/5: ERROR after {elapsed:.3f}s")
                traceback.print_exc()

            time.sleep(1.0)

        if run_times:
            avg_time = sum(run_times) / len(run_times)
            print(f"  --> Average: {avg_time:.3f}s over {len(run_times)} successful run(s)")
            summary.append((s["name"], avg_time, len(run_times), function_calls_received))
        else:
            print("  --> All runs failed for this setting.")
            summary.append((s["name"], None, 0, 0))

    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    for name, avg, count, fcs in summary:
        if avg is not None:
            print(f"  - {name}: Avg = {avg:.3f}s ({count}/5 runs succeeded, {fcs}/5 returned function calls)")
        else:
            print(f"  - {name}: FAILED (0/5 runs succeeded)")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
