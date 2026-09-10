# GROCER — Current State

Last verified: 2026-09-10  
Branch: ag/mainline  
Milestone: Swiggy Builders Club Live Integration & Codebase Modernization  
Readiness: Live end-to-end (WhatsApp, Vercel frontend, Render backend, Swiggy MCP)

## Verified product boundary

GROCER is a WhatsApp-first consumer grocery replenishment assistant. Natural language is interpreted into an explicit `IntentContract` using Google Gemini (`gemini-3.5-flash-lite`) with a deterministic `RuleBasedExtractor` fallback; deterministic code enforces quantity, identity, budget, recovery, confirmation, payment, and order-state rules. Commerce is executed securely through `CommercePort` via `SwiggyMCPAdapter`, authorized by a compliant Swiggy OAuth 2.1 PKCE flow.

## Audited architecture

    Web Frontend (OAuth)    WhatsApp (Chat)
            \                    /
             \                  /
          Grocer Backend (Orchestrator)
            |-- Swiggy OAuth TokenVault (disk-backed JSON)
            |-- Gemini LLM Intent parser & contract
            |-- deterministic verifier & policy
            |-- bounded recovery loop
            '-- basket-bound one-time confirmation
                      |
                 CommercePort
                      |
               Swiggy Instamart MCP

## Implemented and verified live features

- **Gemini Natural Language Parsing:** Wired `gemini-3.5-flash-lite` via `httpx` in `backend/intent/parser.py` for resilient intent extraction across Hinglish, conversational phrases, and multi-item grocery lists.
- **Greeting Detection & Conversational Replies:** Direct greetings ("Hi Grocer!") return friendly guidance without triggering empty cart creation or address prompts.
- **Durable Customer Address Persistence:** Customer's chosen delivery address is durably cached across session boundaries, eliminating repeated address prompts.
- **Swiggy OAuth 2.1 PKCE:** Fully compliant dynamic client registration, token exchange, and disk persistence on Render.
- **WhatsApp Interactive UI:** Conversational choices (address selection, pack size ambiguity) render as native WhatsApp List messages with explicit confirmation buttons before checkout.
- **Demo Mode Checkout Guard:** End-to-end cart mutation and verification is live, but final Swiggy checkout endpoints are intercepted via `DEMO_MODE=true` for safe presentations without financial charges.
- **Intent-Preserving Recovery:** Hard dietary tags, strict pack multiples, and budget caps are deterministically verified against the live Swiggy catalog.
- **Strict Typography Standard:** `Lora` strictly for editorial headlines, `Geist Sans` for UI prose/controls, and `Geist Mono` exclusively for codes, nonces, phone numbers, and currency tags.

## Current quality gates

- **Python Tests:** 360 / 360 tests passed cleanly (`pytest backend/tests` in ~13s).
- **Frontend Build:** Vercel Next.js 16 Turbopack production build compiles in <3s.
- **Frontend Linter:** 0 errors, 0 warnings (`npm run lint`).
- **Code Health:** Dead developer `/debug` route, live inspector drawer, legacy client types, and unused `web.py` channel completely purged (-1,516 lines). Root binary bundle purged (-17.3 MB).
