# GROCER — Current State

Last verified: 2026-09-16
Branch: ag/mainline  
Milestone: Intent Integrity, Packaging Formats & Architecture Stabilization  
Readiness: Local regression verified; WhatsApp, Render, Vercel, and Swiggy re-verification pending deployment

## Verified product boundary

GROCER is a WhatsApp-first consumer grocery replenishment assistant. Natural language is interpreted into an explicit `IntentContract` using Google Gemini (`gemini-3.5-flash-lite`) with a deterministic `RuleBasedExtractor` fallback; deterministic code enforces quantity, identity, budget, recovery, confirmation, payment, and order-state rules. Commerce is executed securely through `CommercePort` via `SwiggyMCPAdapter`, authorized by a compliant Swiggy OAuth 2.1 PKCE flow.

## Audited architecture

    Web Frontend (OAuth)    WhatsApp (Chat)
            \                    /
             \                  /
          ConversationInterpreter + ConversationController
            |-- contextual free-text command interpretation
            |-- validates command against active session/options
            '-- delegates only to GrocerOrchestrator
          GrocerOrchestrator (Stateless State Router: 899 lines)
            |-- orchestrator_confirm.py (Snapshot & Checkout Lock: 439 lines)
            |-- orchestrator_choice.py (Clarification Resolution: 357 lines)
            |-- orchestrator_tracking.py (Payment Polling & Live Tracking: 344 lines)
            |-- orchestrator_address.py (Address Matching & Persistence: 193 lines)
            |-- orchestrator_payment.py (Payment Option Matching: 138 lines)
            |-- formatters.py (WhatsApp Presentation Templates: 180 lines)
            |-- RecoveryEngine (Recovery Seams: 487 lines)
            |     |-- recovery_strategies.py (5 Failure Handlers: 605 lines)
            |     '-- recovery_candidates.py (Filtering & Ranking: 198 lines)
            '-- CommercePort
                  |
            SwiggyMCPAdapter (Adapter Boundary: 513 lines)
                  |-- swiggy_parsers.py (Response Parsers: 485 lines)
                  |-- swiggy_normalizers.py (Schema Builders: 354 lines)
                  '-- swiggy_client.py (JSON-RPC 2.0 Transport: 151 lines)

## Implemented and verified features

- **Single Safe Conversation Path:** WhatsApp text and native interactive IDs are interpreted into a bounded command and delegated to `GrocerOrchestrator`. No LLM module can mutate carts or execute checkout directly.

- **Complete God Object Modularization:** Decomposed massive files (>2,000 lines) into focused, single-responsibility modules under clean domain boundaries without breaking any public interfaces.
- **Gemini Natural Language Parsing:** Wired `gemini-3.5-flash-lite` via `httpx` for English multi-item grocery requests and conversational corrections.
- **Universal Intent Interception:** Eliminates address hijacking traps. When a user replies with item modifications ("1 coke can only") during address or payment selection, the system automatically routes to basket mutation, clears pending prompts, and keeps the conversation in `BUILDING`.
- **Packaging Format Slots & Variant Ranking:** First-class support for packaging descriptors (`can`, `bottle`, `tin`, `pouch`, `sachet`, `box`). Variant ranker strictly prioritizes matching container formats (e.g. 300ml Can over 2L multipack) and penalizes bulk multipacks when 1 unit is requested.
- **Hard Empty-Cart Verification Guard:** Explicit `EMPTY_CART` violation code in `verifier.py` blocks advancing to confirmation or checkout if the cart is empty or ₹0.
- **Blackboard Intent Memory Accumulation:** Multi-turn intent merging accumulates items across conversational turns instead of overwriting, with clean preservation across turns.
- **Category Affinity Recovery:** Recovery engine prioritizes active basket categories and staples, eliminating cross-category substitutions (e.g. biscuits for beverages).
- **Customer Identity Hash Parity:** Standardized phone normalization (`digits[-10:]`) across Swiggy OAuth login, status queries, and WhatsApp webhooks.
- **Address Preference Cache:** A chosen delivery address is reused during local sessions; durable encrypted persistence remains a release gate.
- **WhatsApp Interactive UI:** Conversational choices render as native WhatsApp List messages with explicit confirmation buttons before checkout.
- **Review Checkout Guard:** When `CHECKOUT_MODE=review` and the Swiggy adapter is configured, GROCER truthfully stops before a chargeable order. `CHECKOUT_MODE=live` remains an explicit deployment decision.

## Current quality gates

- **Python Tests:** 384 / 384 tests passing (`pytest backend/tests` in 3.40s; the existing pytest cache directory has a Windows permission warning only).
- **Frontend Build:** Vercel Next.js 16 Turbopack production build compiles with zero errors in 5.1s.
- **Frontend Linter:** 0 errors, 0 warnings (`npm run lint`).
- **Knowledge Graph:** AST knowledge graph synchronized via `graphify update .` (2,282 nodes, 6,239 edges, 126 communities).
- **Code Health:** The core commerce path is modularized and locally verified. GitHub Actions now runs backend tests plus frontend lint/build. Deployment durability, live-provider verification, and redacted deployment telemetry remain open gates.

