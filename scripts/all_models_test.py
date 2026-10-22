"""Model evaluation and latency benchmark across all available Gemini models.

Tests 8 real-world grocery scenarios against every text model supporting generateContent:
1. bhai 2 packet milk aur ek dozen anda chahiye
2. something for breakfast
3. paneer butter masala ingredients for 4 people
4. same as last time
5. mujhe kuch meetha chahiye under 200
6. amul butter 500g, brown bread, and 1 coke
7. cancel my order
8. yes

Uses the exact production system instruction and tool schemas with an empty cart.
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.config import settings
from backend.agent.prompts import build_system_instruction
from backend.agent.schemas import RAW_TOOL_DECLARATIONS
from google import genai
from google.genai import types

MESSAGES = [
    "bhai 2 packet milk aur ek dozen anda chahiye",
    "something for breakfast",
    "paneer butter masala ingredients for 4 people",
    "same as last time",
    "mujhe kuch meetha chahiye under 200",
    "amul butter 500g, brown bread, and 1 coke",
    "cancel my order",
    "yes",
]

EXCLUDE_KEYWORDS = [
    "tts", "image", "banana", "lyria", "transcribe", "clip",
    "robotics", "computer-use", "antigravity", "deep-research", "gemma",
    "omni",
]


def is_rate_or_quota_error(exc: Exception) -> bool:
    err = str(exc).lower()
    return any(k in err for k in ["429", "resource_exhausted", "quota", "rate limit", "rate_limit"])


def is_permanent_model_error(exc: Exception) -> bool:
    err = str(exc).lower()
    return any(k in err for k in ["404", "not_found", "no longer available", "not available to new users", "503", "unavailable"])


def format_tool_calls(function_calls):
    formatted = []
    for fc in function_calls:
        args_dict = fc.args or {}
        try:
            args_str = json.dumps(args_dict, ensure_ascii=False)
        except Exception:
            args_str = str(args_dict)
        formatted.append(f"{fc.name}({args_str})")
    return formatted


def get_candidate_models(client: genai.Client) -> list[str]:
    """Step 1: List text models supporting generateContent and function calling."""
    candidates = []
    for m in client.models.list():
        if not m.supported_actions or "generateContent" not in m.supported_actions:
            continue
        raw_name = m.name or ""
        clean_name = raw_name.removeprefix("models/")
        low_name = clean_name.lower()
        if any(kw in low_name for kw in EXCLUDE_KEYWORDS):
            continue
        desc = (m.description or "").lower()
        if any(kw in desc for kw in ["audio", "music generation", "robotics", "image preview", "speech"]):
            continue
        candidates.append(clean_name)
    return candidates


def run_single_turn(
    client: genai.Client,
    model_name: str,
    message: str,
    system_instruction: str,
    tools: list[types.Tool],
):
    """Execute a single fresh turn using thinking_level='low' if accepted, else default."""
    config_low = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=tools,
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
    )

    start = time.perf_counter()
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=message,
            config=config_low,
        )
        elapsed = time.perf_counter() - start
        return response, elapsed, None
    except Exception as exc:
        elapsed = time.perf_counter() - start
        if is_rate_or_quota_error(exc) or is_permanent_model_error(exc):
            return None, elapsed, exc

        print(f"    [Notice: {model_name} rejected thinking_level='low': {exc.__class__.__name__}. Retrying with default thinking...]", flush=True)
        config_default = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=tools,
        )
        start2 = time.perf_counter()
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=message,
                config=config_default,
            )
            elapsed2 = time.perf_counter() - start2
            return response, elapsed2, None
        except Exception as exc2:
            elapsed2 = time.perf_counter() - start2
            return None, elapsed2, exc2


def main():
    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: No GEMINI_API_KEY found.", flush=True)
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    print("=" * 80, flush=True)
    print("STEP 1: DISCOVERING ELIGIBLE TEXT MODELS", flush=True)
    print("=" * 80, flush=True)
    models = get_candidate_models(client)
    print(f"Discovered {len(models)} text model(s) supporting generateContent & function calling:\n", flush=True)
    for idx, m in enumerate(models, 1):
        print(f"  {idx}. {m}", flush=True)

    print("\n" + "=" * 80, flush=True)
    print("STEP 2: RUNNING BENCHMARK (8 MESSAGES PER MODEL, 2S DELAY)", flush=True)
    print("=" * 80, flush=True)

    system_instruction = build_system_instruction(cart=None)
    tools = [types.Tool(function_declarations=RAW_TOOL_DECLARATIONS)]

    results_matrix: dict[str, list[float | None]] = {}

    for model_idx, model_name in enumerate(models, 1):
        print(f"\n{'#' * 80}", flush=True)
        print(f"[{model_idx}/{len(models)}] MODEL: {model_name}", flush=True)
        print(f"{'#' * 80}", flush=True)

        model_times: list[float | None] = []
        skip_model = False

        for msg_idx, message in enumerate(MESSAGES, 1):
            if skip_model:
                model_times.append(None)
                continue

            response, elapsed, exc = run_single_turn(
                client=client,
                model_name=model_name,
                message=message,
                system_instruction=system_instruction,
                tools=tools,
            )

            if exc is not None:
                model_times.append(None)
                print(f"\n--- Model: {model_name} | Message {msg_idx}/8: \"{message}\" ---", flush=True)
                print(f"Time: {elapsed:.3f}s", flush=True)
                print(f"ERROR: {exc.__class__.__name__}: {exc}", flush=True)

                if is_rate_or_quota_error(exc):
                    print(f"--> Rate limit / quota reached. Skipping remainder of {model_name}.", flush=True)
                    skip_model = True
                elif is_permanent_model_error(exc):
                    print(f"--> Model unavailable / not found ({exc.__class__.__name__}). Skipping remainder of {model_name}.", flush=True)
                    skip_model = True
            else:
                model_times.append(elapsed)
                print(f"\n--- Model: {model_name} | Message {msg_idx}/8: \"{message}\" ---", flush=True)
                print(f"Time: {elapsed:.3f}s", flush=True)
                if response.function_calls:
                    calls = format_tool_calls(response.function_calls)
                    print(f"Tool Calls ({len(calls)}):", flush=True)
                    for c in calls:
                        print(f"  * {c}", flush=True)
                else:
                    reply_text = (response.text or "").strip()
                    print(f"Plain Text Reply:\n{reply_text}", flush=True)

            time.sleep(2.0)

        results_matrix[model_name] = model_times

    print("\n" + "=" * 80, flush=True)
    print("STEP 3: SUMMARY TABLE (LATENCY IN SECONDS BY MODEL & MESSAGE)", flush=True)
    print("=" * 80, flush=True)

    header = f"{'Model':<35} | " + " | ".join(f"M{i}" for i in range(1, 9)) + " | Average"
    print(header, flush=True)
    print("-" * len(header), flush=True)

    for model_name, times in results_matrix.items():
        row_cols = []
        valid_times = [t for t in times if t is not None]
        for t in times:
            if t is not None:
                row_cols.append(f"{t:4.2f}s")
            else:
                row_cols.append("  -- ")
        if valid_times:
            avg_str = f"{sum(valid_times) / len(valid_times):5.3f}s ({len(valid_times)}/8)"
        else:
            avg_str = "FAILED"
        print(f"{model_name:<35} | " + " | ".join(row_cols) + f" | {avg_str}", flush=True)

    print("=" * 80, flush=True)


if __name__ == "__main__":
    main()
