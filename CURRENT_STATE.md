# GROCER — Current State

Last verified: 2026-09-10
Branch: ag/mainline
Milestone: Swiggy Builders Club Live Integration Complete
Readiness: Live end-to-end (WhatsApp, Vercel frontend, Render backend, Swiggy MCP)

## Verified product boundary

GROCER is a WhatsApp-first consumer grocery replenishment assistant. Natural language is interpreted into an explicit IntentContract; deterministic code enforces quantity, identity, budget, recovery, confirmation, payment, and order-state rules. Commerce is executed securely through CommercePort via SwiggyMCPAdapter, authorized by a compliant Swiggy OAuth PKCE flow.

## Audited architecture

    Web Frontend (OAuth)    WhatsApp (Chat)
            \                    /
             \                  /
          Grocer Backend (Orchestrator)
            |-- Swiggy OAuth TokenVault
            |-- Intent parser and contract
            |-- deterministic verifier and policy
            |-- bounded recovery
            '-- basket-bound one-time confirmation
                      |
                 CommercePort
                      |
               Swiggy Instamart MCP

## Implemented and verified live features

- **Swiggy OAuth 2.1 PKCE:** Fully compliant dynamic client registration, token exchange, and persistence.
- **WhatsApp Interactive UI:** Conversational choices (address selection, pack size ambiguity) render as native WhatsApp List messages.
- **Demo Mode Checkout Guard:** End-to-end cart mutation and verification is live, but final Swiggy checkout endpoints are intercepted via DEMO_MODE=true for safe presentations.
- **Intent-Preserving Recovery:** Hard dietary tags, strict pack multiples, and budget caps are deterministically verified against the live Swiggy catalog.

## Current quality gates

- **Python:** 363 tests passed cleanly.
- **Frontend:** Vercel Next.js production build and TypeScript checks pass.
- **Code Health:** Dead web chat UI purged. Full ESLint compliance.
