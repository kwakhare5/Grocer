# AGENTS.md — Grocer Project Rules

---

## 1. PROJECT IDENTITY
- **Name:** Grocer AI
- **Goal:** Intelligent grocery inventory tracking, depletion forecasting, and automated WhatsApp alert assistant.
- **Status:** In Progress
- **Repo:** https://github.com/kwakhare5/Grocer

---

## 2. TECH STACK
- **Backend:** FastAPI (Python 3.12, Pydantic v2, asyncpg, SQLAlchemy 2.0)
- **ML & Forecasting:** Prophet + TimescaleDB / SQLite
- **Notifications & AI:** Twilio WhatsApp API + Groq / NVIDIA NIM LLM Chatbot + MCP Server
- **Frontend:** Next.js 15 + React 19 + Tailwind CSS v4
- **Testing:** pytest (Backend) + Vitest (Frontend)

---

## 3. DEV COMMANDS
```bash
# Backend
python run_backend.py      # Start FastAPI server on port 8000
pytest                     # Run backend test suite

# Frontend
cd frontend && npm run dev # Start Next.js frontend
cd frontend && npm test    # Run frontend unit tests
```

---

## 4. LOCAL RULES & DESIGN INVARIANTS
1. **Graphify First:** `graphify-out/` is present. Query graph before raw search.
2. **Config Drift Protection:** Every environment variable in `backend/config.py` MUST be documented in `.env.example`.
3. **Twilio Guard:** Check `is_twilio_configured()` before attempting WhatsApp webhook dispatches.
4. **FastAPI Best Practices:** Strict Pydantic v2 models for request/response schemas.

---

## 5. KEY PROJECT PATTERNS
- `backend/main.py` — FastAPI application entrypoint with lifespan event handlers.
- `backend/config.py` — Central Pydantic `Settings` model.
- `backend/ml/` — Prophet forecasting engine for pantry item depletion curves.
- `backend/notifications/` — Twilio WhatsApp notification dispatch and templates.
- `frontend/app/` — Next.js 15 App Router client interface.

---

## 6. MISTAKES TO AVOID
- [2026-08-14] Raw dictionary access on settings raised AttributeError → Always read settings via typed `settings.KEY` attributes.
- [2026-08-15] Hardcoded Twilio credentials caused test suite hangs → Mock `TwilioClient` in all offline pytest fixtures.

---

## 7. SESSION RESUME
**Last session date:** 2026-08-21
- **Current State:** TimescaleDB + Prophet forecasting active, Groq AI chatbot wired, Next.js frontend connected.
- **Immediate next task:** Connect live recipe suggestions based on predicted expiring items.
- **Open blockers:** None.

