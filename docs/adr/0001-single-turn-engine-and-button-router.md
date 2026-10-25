# Single-Turn Brain with 50ms Fast Button Router over Multi-Model Bouncers

We replaced the legacy multi-model defensive pipeline (`react_coordinator.py`, `claim_check.py`, `item_drop_guard.py`, `preflight_handler.py`, `response_synthesizer.py`) with a single-turn Gemini 3.5 Flash engine coupled with a deterministic Python button router (`button_router.py`) and parallel composite cart manager (`composite_cart.py`).

The legacy approach added 20–30 seconds of conversational latency per turn and burned excessive tokens by running secondary LLMs to check the primary LLM's outputs. The new architecture delegates fuzzy natural language parsing and customer conversation to Gemini in a single pass, while Python deterministically executes WhatsApp button actions in under 50ms, searches Swiggy dark stores concurrently via `asyncio.gather`, diffs dropped items without silent omissions, enforces the 3-lock cryptographic checkout latch, and guarantees receipt math balancing.
