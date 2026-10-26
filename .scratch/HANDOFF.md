# Grocer v1.0 — Session Handoff

- **Goal:** Gate 2 — capability router with safety classes, replacing the four intents.
- **Current:** LLM adapter live (`backend/agent/llm.py`), Groq key in `.env`, one real JSON completion proven. Docs amended by ADR 0012. Router not written yet.
- **Passing Tests:** `ruff` clean; adapter smoke-tested live. Offline suite unchanged at 38.
- **Next Action:** Write `backend/agent/router.py`: capability list, four safety classes, routing decision model, safe path. Then wire one read capability (item info) into `whatsapp.py` and prove it live without touching the cart.
- **Source of Truth:** `STATUS.md`
