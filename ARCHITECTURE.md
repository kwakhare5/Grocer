# ARCHITECTURE.md — GROCER v2

> **Product Authority:** `GROCER_V2_MASTER_SPEC.md`
> **System Identity:** WhatsApp Consumer Grocery Replenishment Assistant with Intent Preservation
> **Status:** Consolidated architecture; deployment re-verification pending
> **Updated:** 2026-09-15

---

## 1. System Identity & Mission

**GROCER** is a WhatsApp consumer grocery replenishment assistant designed to preserve user shopping intent across dynamic commerce state (stockouts, pack size variations, price fluctuations, and delivery constraints).

* **Core Thesis:** Preserve the user's intended shopping outcome even when live quick-commerce state changes.
* **Separation of Concerns:** GROCER is exclusively consumer-facing. Dark-store operations, warehouse logistics, and store-level optimization belong to the companion repository (`kwakhare5/Dark-store-operator`).

```text
               WhatsApp Consumer UX / Mobile
                             │
                             ▼
                 Inbound Webhook & Auth
                             │
                             ▼
                Grocer Orchestration Core
              (Intent, Verification, Policy)
                             │
                             ▼
                        CommercePort
                       /            \
                      ▼              ▼
              Swiggy MCP Adapter   Mock Adapter (Tests)
                      │
                      ▼
            Live Instamart Commerce
```

---

## 2. End-to-End System Architecture

```text
                           USER / WHATSAPP
                                  │
                                  ▼
                   WhatsAppChannelAdapter (Meta Webhook)
                   • HMAC-SHA256 Signature Verification
                   • Idempotent Message Reservation
                   • Sender Pseudonymization (cust_wa_...)
                                  │
                                  ▼
                          FastAPI Routing
                       (/api/whatsapp/webhook)
                                  │
                                  ▼
                    ConversationInterpreter
          • contextual free-text interpretation
          • validated command, never provider authority
                                  │
                                  ▼
                     GrocerOrchestrator (State Router)
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
  orchestrator_address   items_stage (_resolve)   orchestrator_payment
  (Serviceable Address)    (Catalog Resolution)     (UPI / Cash / Cards)
                                  │
                                  ▼
                            CommercePort
                   (SwiggyMCPAdapter / MockAdapter)
                                  │
                                  ▼
                          Canonical Cart
                                  │
                                  ▼
                           IntentVerifier
            Deterministic verification against IntentContract:
            • Missing items     • Wrong quantity
            • Brand locks       • Budget overrun
            • Dietary tags      • Minimum order threshold
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
                 [ PASS ]                    [ FAIL ]
                    │                           │
                    │                           ▼
                    │                    RecoveryEngine
                    │              (Bounded replanning passes)
                    │              • recovery_strategies
                    │              • recovery_candidates
                    │                           │
                    │             ┌─────────────┴─────────────┐
                    │             ▼                           ▼
                    │        [ RECOVERED ]           [ NEEDS_DECISION ]
                    │             │                           │
                    │             │                           ▼
                    │             │                  orchestrator_choice
                    │             │                  (Options to User)
                    │             │                           │
                    └─────────────┼───────────────────────────┘
                                  ▼
                         AWAITING_CONFIRMATION
                        (Fingerprinted Snapshot)
                                  │
                                  ▼
                        User Confirmation Reply
                                  │
                                  ▼
                        orchestrator_confirm
                     (Server-Side Checkout Guard)
                                  │
                                  ▼
                        CommercePort.checkout()
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
            [ UPI_PENDING ]                 [ ORDERED ]
                    │                           │
                    ▼                           ▼
          orchestrator_tracking         Order Complete
          (Poll UPI / Track Rider)
```

---

## 3. Core Architectural Principles

### 3.1 LLM Interprets & Proposes; Deterministic Code Enforces & Verifies
* **LLM Responsibility:** Natural language parsing, conversational slot extraction, category tagging, friendly user messaging.
* **Deterministic Code Responsibility:** Hard constraint evaluation, budget arithmetic, cart verification, recovery policy enforcement, server-side checkout authorization, state persistence.

### 3.2 Intent is the Immutable Source of Truth
The live cart may drift due to retailer inventory fluctuations. The `IntentContract` represents what the user actually wants. The system reconciles live commerce back to user intent, never silently modifying requirements without policy authorization.

### 3.3 Rule of Precedence
When resolving conflicts between preferences:
```text
Current Explicit Request > Current Session Choice > Stored Soft Preference > System Default
```
Stored memory cannot silently override an explicit instruction in the current conversation turn.

### 3.4 Strict Provider Isolation
All Swiggy-specific payloads, JSON-RPC envelopes, and vendor quirks are encapsulated behind `CommercePort`. Business orchestration and recovery engines interact solely with canonical domain models (`CommerceCart`, `CartItem`, `PaymentOption`, `CommerceOrderResult`).

### 3.5 Immutable Snapshotting & Server-Side Checkout Safety
No checkout may execute without:
1. Deterministic verification pass (all hard constraints green).
2. Explicit user confirmation matching a time-limited confirmation nonce.
3. Cryptographic payload fingerprint matching the exact verified cart snapshot.
4. Non-idempotent one-way transition (preventing duplicate charges or double orders).

---

## 4. Subsystems & Module Breakdown

### 4.1 Inbound Channels (`backend/channels/`)
* **`whatsapp.py` (`WhatsAppChannelAdapter`):** Handles Meta WhatsApp Business Cloud API webhooks.
  * Validates webhook verification challenges (`hub.challenge`).
  * Enforces cryptographic request integrity using HMAC-SHA256 via `x-hub-signature-256`.
  * De-duplicates inbound webhooks via in-memory TTL reservation (`reserve_message`).
  * Normalizes outbound responses into WhatsApp interactive buttons or text messages.
* **`models.py` & `base.py`:** Channel-agnostic envelopes and transport-only dispatch. Native WhatsApp IDs and free text both enter the same conversation controller.

### 4.2 Intent Core (`backend/intent/`)
* **`conversation.py`:** Converts contextual free text into a bounded `ConversationCommand`; validates command/state/option bindings before delegating to `GrocerOrchestrator`. It never calls `CommercePort` directly.
* **`parser.py` (`IntentParser`):** Two-stage extractor pipeline:
  * Primary: `GeminiIntentExtractor` for English multi-item requests and implicit quantities.
  * Fallback: `RuleBasedExtractor` for offline/zero-API deterministic regex extraction.
* **`taxonomies.py`:** Centralized packaging descriptors, unit conversion tables, product category keywords, and conversational stop words.
* **`validator.py` (`DeterministicValidator`):** Validates raw extractor output, clamps confidence scores, normalizes constraints, and generates validated `IntentContract` instances.
* **`models.py`:** Canonical domain models including `IntentContract`, `IntentItem`, `BudgetConstraint`, `DietaryConstraint`, `BrandPreference`, and `SubstitutionPolicy`.
* **`semantics.py`:** Quantity normalization, pack size arithmetic, catalog dependency flags, and product head matching.

### 4.3 Orchestration Engine (`backend/intent/`)
Fully modularized single-responsibility coordinators:
* **`orchestrator.py` (`GrocerOrchestrator`):** Main conversation state machine. Routes turns, manages session lifecycle, initiates cart updates, and triggers verification/recovery.
* **`orchestrator_confirm.py`:** Handles the critical checkout transition:
  * Validates confirmation nonce and cart hash fingerprints.
  * Re-verifies live cart before initiating consequential payment actions.
  * Enforces server-side execution locks.
* **`orchestrator_choice.py`:** Handles user ambiguity decisions:
  * Translates recovery outcomes into numbered decision options.
  * Processes user option selections (`handle_choice`).
  * Handles conversational item swaps and item removal requests.
* **`orchestrator_tracking.py`:** Post-order delivery tracking:
  * Polls pending UPI payment confirmations.
  * Fetches real-time delivery status, ETA, and rider GPS coordinates.
* **`orchestrator_address.py`:** Address management:
  * Fetches and matches delivery addresses.
  * Enforces provider-reported delivery-address serviceability.
  * Caches customer address selection across turns.
* **`orchestrator_payment.py`:** Payment method selection:
  * Discovers available payment options (UPI, Cash, Cards, Wallets).
  * Selects preferred payment methods based on stored user preferences.
* **`stages/items_stage.py`:** Item resolution pipeline:
  * Concurrently searches catalog for requested items via `CommercePort`.
  * Ranks candidates by pack size alignment, category, and unit economics.
  * Assigns explicit catalog-dependent `ResolvedMeaning`.
* **`formatters.py`:** Pure presentation layer formatting WhatsApp conversational messages, interactive decision prompts, and order receipts.

### 4.4 Intent Verifier & Recovery Engine (`backend/intent/`)
* **`verifier.py` (`IntentVerifier`):** Deterministic audit comparing active cart against `IntentContract`:
  * Verifies item presence, pack sizes, quantities, and brand restrictions.
  * Checks total cost against max budget and minimum order thresholds.
  * Categorizes discrepancies into hard violations and soft deviations.
* **`recovery.py` (`LoopingRecoveryEngine`):** Bounded replanning engine (max 3 iterations):
  * Coordinates auto-recovery vs user clarification based on user autonomy policy.
* **`recovery_strategies.py`:** Concrete recovery handlers:
  * `handle_transient_error`: Safe exponential backoff for network/provider hiccups.
  * `handle_min_order_failure`: Automatically appends staple items from user history to cross threshold.
  * `handle_budget_drift`: Replaces expensive variants with budget-friendly alternatives.
  * `handle_item_or_brand_unavailable`: Discovers alternative pack sizes or permitted substitute brands.
* **`recovery_candidates.py`:** Variant scoring, multi-factor ranking, and hard-constraint filtering for candidate replacements.

### 4.5 Commerce Layer (`backend/integrations/commerce/`)
* **`port.py` (`CommercePort`):** Abstract provider interface defining contracts for:
  * `get_addresses()`, `search_products()`, `get_go_to_items()`
  * `get_cart()`, `update_cart()`, `clear_cart()`
  * `get_payment_options()`, `checkout()`
  * `get_delivery_tracking()`, `get_order_details()`
* **`swiggy_adapter.py` (`SwiggyMCPAdapter`):** Production quick-commerce adapter:
  * Scopes calls to authenticated customer context (`customer_id`).
  * Enforces non-idempotent checkout guards.
* **`swiggy_client.py`:** High-performance JSON-RPC 2.0 transport over HTTPX:
  * Integrates with `SwiggyTokenVault` for bearer token injection.
  * Normalizes upstream HTTP / JSON-RPC error codes into typed `CommerceError` hierarchy.
* **`swiggy_parsers.py`:** Provider payload parsing (addresses, items, bills, tracking payloads).
* **`swiggy_normalizers.py`:** Builds canonical `CommerceCart` and `CommerceOrderResult` instances from provider responses.
* **`mock_adapter.py`:** Deterministic local adapter supporting controllable failure injection for test suites.

### 4.6 Authentication & Identity (`backend/integrations/commerce/` & `backend/api/`)
* **OAuth 2.1 with PKCE (`oauth.py`):** Compliant RFC 7636 authorization code flow:
  * High-entropy `code_verifier` and SHA-256 `code_challenge`.
  * Secure callback handling and exchange with Swiggy auth servers.
* **`token_vault.py` (`SwiggyTokenVault`):** Development token cache pending durable encrypted storage:
  * Masks credentials in memory and logs.
  * Uses local disk only for development continuity; it is not deployment durability.
* **Pseudonymous Identity Mapping:** WhatsApp phone numbers are hashed using HMAC-SHA256 with `WHATSAPP_APP_SECRET` to produce stable, privacy-preserving `cust_wa_...` customer keys.

---

## 5. State Model & Conversation Lifecycle

```text
[ INITIAL / READY ]
        │
        ▼ (User sends message: "milk and eggs")
[ CART_BUILDING ]
        │
        ▼ (Items resolved & added to cart)
[ VERIFYING ]
        ├── Pass ──► [ AWAITING_CONFIRMATION ]
        └── Fail ──► [ RECOVERING ]
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
    [ Auto-Recovered ]             [ NEEDS_DECISION ]
            │                               │
            ▼ (Verify again)                ▼ (User picks option)
   [ AWAITING_CONFIRMATION ]◄───────────────┘
            │
            ▼ (User confirms: "yes order it")
   [ CHECKOUT_LOCKED ]
            │
            ▼ (Server-side checkout call)
   [ ORDERED / PAYMENT_PENDING ]
            │
            ▼ (Track delivery / Rider)
   [ COMPLETED ]
```

---

## 6. Safety & Security Invariants

1. **Zero Credential Exposure:** Bearer tokens, secrets, and auth headers are never logged or returned to frontend/chat surfaces.
2. **Server-Side Authorization Boundary:** No LLM prompt or UI action can bypass server-side checkout validation.
3. **No Unverified Success Claims:** An order is reported as placed only when confirmed by the commerce provider with an authoritative order ID.
4. **No Empty or Sub-Zero Checkouts:** Zero-item carts and invalid totals are blocked before provider transmission.
5. **Bounded Execution:** Recovery loops are strictly limited to prevent infinite replanning cycles.

---

## 7. Technology Stack

* **Backend Framework:** FastAPI / Python 3.12 (Pydantic v2, HTTPX, Pytest)
* **Frontend Surface:** Next.js 16 (React 19, Tailwind CSS v4, TypeScript)
* **Commerce Protocol:** Model Context Protocol (MCP) JSON-RPC 2.0 / HTTP
* **Messaging Surface:** Meta WhatsApp Business Cloud API Webhooks
* **AI / Reasoning:** Google Gemini API (Structured Output Extraction)
