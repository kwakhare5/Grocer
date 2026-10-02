# Implementation Plan: Swiggy Builder Club Production & Safety Alignment

This plan addresses all forensic findings in [`Grocer-BuilderClub-Plan.md`](file:///D:/Grocer/Grocer-BuilderClub-Plan.md) based on the decisions finalized during `/grill-me`.

---

## 1. Executive Summary & Design Decisions

During the `/grill-me` session, the following architectural choices were locked:
1. **Execution Order**: **Safety & Security First (Tracks E, F, G)** prior to model/quality tweaks.
2. **Review Mode Behavior**: In `CHECKOUT_MODE=review`, `SwiggyMCPAdapter` halts before calling Swiggy's financial `checkout` tool, returning a verified simulated order result (`status="REVIEW_SIMULATED"`, cart totals preserved) and logging an audit trace.
3. **Token Privacy**: Remove `.vault_tokens.json` plaintext disk writes entirely. In the absence of PostgreSQL, store tokens in RAM only (fail-closed). Strictly isolate customer credentials: eliminate `cust_wa_*` wildcard mapping to the owner's token.
4. **Confirmation & Receipt Delivery**: Reject negations upfront (`"don't confirm"`, `"not now"`). Allow natural affirmations (`"yes"`, `"ok"`, `"confirm"`). For receipts exceeding Meta's 1,024-character interactive limit, send the full receipt as a standard text message (up to 4,096 chars) followed immediately by a short interactive button message.
5. **Deterministic Budget Gate**: Store `budget_inr` in `CustomerSession`. Enforce a deterministic code guard in Python: reject checkout if `cart.grand_total > budget_inr`. Expand product search results to 10 items with pack size and savings metadata.
6. **Model & History Resilience**: Increase conversation history from 4 to 20 turns. Eliminate amnesiac history deletion on Gemini HTTP 400 errors by validating tool call/response pairing.
7. **Adversarial Invariant Verification (TDD)**: Author a dedicated failure-mode test suite (`test_safety_invariants.py`) verifying all 6 safety barriers before marking complete.

---

## 2. Proposed Changes by Subsystem

### Track 1: Financial Protection & Security Boundaries (E, F, G)

#### 1. `backend/integrations/commerce/swiggy_adapter.py`
- Check `settings.CHECKOUT_MODE` in `SwiggyMCPAdapter.checkout()`:
  - If `"review"`, do NOT invoke `_call_mcp_tool("checkout", ...)`.
  - Return a safe `CommerceOrderResult` with `order_id=f"sim_rev_{int(time.time())}"`, `status=OrderStatus.PENDING`, preserved item list and grand total, and a clear disclaimer: `"[REVIEW MODE] Order simulated safely. No financial charge was made."`
  - If `"live"`, proceed with the existing upstream checkout call.

#### 2. `backend/integrations/commerce/token_vault.py`
- Delete `_save_to_disk()` and `_load_from_disk()` that read/write `.vault_tokens.json` in plaintext.
- If PostgreSQL is not configured, hold tokens strictly in-memory (`self._tokens`).
- In `get_entry(customer_id)`:
  - Remove wildcard owner assignment:
    ```python
    # REMOVE: elif settings.SWIGGY_CUSTOMER_ID.isdigit() and customer_id.startswith("cust_wa_"): is_owner = True
    ```
  - Require exact match: `customer_id == settings.SWIGGY_CUSTOMER_ID`.
  - Unauthenticated customers must receive `None`, triggering the OAuth re-auth flow.

#### 3. `backend/agent/guards.py` & `backend/agent/engine.py`
- **Negation-First Confirmation Detection**:
  - Define `_NEGATION_PATTERNS`: `r"(?i)\b(don'?t|do not|never|stop|wait|hold|cancel|not now|not yet|no)\b"`
  - If negation matches incoming text, `user_confirmed` is immediately `False`.
  - Add affirmative phrases to `_EXPLICIT_CONFIRM_PATTERNS`: `r"(?i)\b(yes|ok|okay|sure|confirm|proceed|place order|pay|book it|go ahead)\b"`
  - Bind confirmation to a cart snapshot (`item_count` + `grand_total`). If cart mutates between approval and checkout, invalidate confirmation.

#### 4. `backend/agent/engine.py`
- **Payment Polling Cadence**:
  - Update `interval_seconds` in `_poll_payment_status` from `5.0` to `10.0` (honoring Swiggy's 10s tracking rate limit rule).
  - Adjust `max_attempts` from `12` to `6` (maintaining a 60-second polling ceiling).

#### 5. `backend/channels/whatsapp.py`
- **Two-Message Long Receipt Handling**:
  - If `response.interactive_actions` are present AND `len(response.text) > 1000`:
    - Dispatch message 1: Raw text containing the complete receipt (`response.text`).
    - Dispatch message 2: Short interactive prompt (`"Please review your basket above. Tap Confirm to place order:"`) with the action buttons.
  - Ensures no receipt lines or grand totals are sliced off.

---

### Track 2: Domain Constraints & Catalog Depth (C, D)

#### 6. `backend/agent/session.py` & `backend/agent/engine.py`
- Add `budget_inr: Optional[float] = None` to `CustomerSession`.
- Add prompt guidance and regex extraction for spending limits (e.g. `"under 500"`, `"budget 1000"`).
- In `engine.py` prior to checkout execution:
  - If `session.budget_inr` is set and `current_cart.grand_total > session.budget_inr`:
    - Block checkout with `error="BUDGET_EXCEEDED"`.
    - Inform customer: *"Your basket total (₹{total}) exceeds your budget of ₹{budget}. Would you like to remove an item or increase your budget?"*

#### 7. `backend/agent/tools.py`
- In `search_products`:
  - Increase slice from `products[:6]` to `products[:10]`.
  - Include `pack_size`, `price`, `mrp`, `savings`, and `in_stock`.
  - On failure, return structured error payloads (`item_id`, `reason`, `retryable`).

---

### Track 3: Model & Conversation Memory Resilience (A, B)

#### 8. `backend/agent/engine.py`
- Increase history window in `_prune_history` from `max_user_turns=4` to `max_user_turns=20`.
- Fix Gemini 400 error recovery:
  - Do NOT wipe all previous turns on HTTP 400 (`contents.clear()`).
  - Instead, compact older tool responses (removing duplicate search payloads) while preserving all user/model conversational turns.
- Keep `GEMINI_MODEL` configurable via `.env` (defaulting to `gemini-3.5-flash-lite` or `gemini-2.5-flash`/`gemini-3.8-flash` if available on user key).

---

### Track 4: Documentation & Test Verification (H)

#### 9. `backend/tests/test_safety_invariants.py`
- Author comprehensive failure-mode tests:
  1. `test_checkout_mode_review_blocks_provider_call`: Verifies zero calls to Swiggy MCP checkout tool when `CHECKOUT_MODE=review`.
  2. `test_token_vault_never_writes_plaintext_disk`: Verifies `.vault_tokens.json` is never written.
  3. `test_token_vault_customer_isolation`: Verifies unknown customer or `cust_wa_*` cannot access owner token.
  4. `test_negation_before_confirmation`: Verifies `"don't confirm"`, `"do not place order"` are rejected, while `"yes"`, `"confirm"` are accepted.
  5. `test_tracking_cadence_ten_seconds`: Verifies tracking poller uses >= 10.0s interval.
  6. `test_deterministic_budget_gate`: Verifies checkout is blocked when cart grand total exceeds `session.budget_inr`.

#### 10. Documentation Reconciliation
- `README.md`: Fix line 254 from `pip install -r backend/requirements.txt` to `pip install -r requirements.txt`.
- Update test badge and test counts in `README.md` and `.agents/AGENTS.md` to reflect the actual verified count.
- Update `docs/SWIGGY_MCP_API.md` and `docs/E2E_VERIFICATION_REPORT.md`.

---

## 3. Verification Plan

### Automated Invariant Checks
1. Run `pytest backend/tests/test_safety_invariants.py` (Must pass 6/6).
2. Run full test suite: `pytest backend/tests` (All tests must pass).
3. Run frontend verification:
   ```bash
   npm run lint
   npm run build
   ```
4. Update knowledge graph:
   ```bash
   npx graphify .
   ```

### Manual Verification Checkpoints
- Inspect file system to confirm `.vault_tokens.json` does not exist.
- Verify simulated checkout produces valid receipt without touching live Swiggy API.
