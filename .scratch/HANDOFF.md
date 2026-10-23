# Session Handoff: Ready for Layer 4 (Product Policy, Safety Interceptor & Gated Checkout)

- **Goal**: Implement Layer 4 (Product Policy & Physical Gated Checkout) according to `docs/TARGET_ARCHITECTURE_V1.md`, eliminate the `product_policy.py` regex, and normalize line-ending spacing bloat.
- **Current State**:
  - Layers 1, 2, and 3 are 100% complete, demodularized, and passing.
  - All 77 unit & integration tests exit 0 in 2.63s (`pytest --ignore=backend/tests/test_whatsapp_postgres_e2e.py`).
  - `npm run lint` exits 0.
  - Active branch: `feat/architecture-v1`.
- **Layer 4 Full Scope (Target Architecture Subsystem 4 & 5)**:
  1. **Line Ending Normalization**: Clean up corrupted `\r\r\n` line bloat in `backend/agent/preflight_handler.py`, `backend/agent/react_coordinator.py`, `backend/agent/formatters.py`, and `backend/integrations/commerce/order_parsers.py` (shrinking `preflight_handler.py` from 3,954 lines down to ~500 clean lines).
  2. **Product Policy & Safety Gate (`backend/agent/product_policy.py`)**:
     - Remove fragile 7-drug regex (`_MEDICAL_NAME`) and symptom keyword dictionary (`_SYMPTOM`, `_NEGATED_SYMPTOM`, `_EXPLICIT_ADD`).
     - Ground restricted checks strictly in Swiggy catalog metadata (`category == "Pharmacy"` / `"Prescription"`).
     - Permit daily OTC first aid (Band-Aids, ORS, cotton, lozenges).
     - Let Gemini handle conversational symptom advice (recommending soothing groceries like honey, ginger, soup) without regex interception.
  3. **Physical Checkout Gatekeeper (`backend/agent/checkout_executor.py`)**:
     - Enforce the 5 hard conditions before Swiggy checkout can execute:
       a) State is `AWAITING_CONFIRMATION`.
       b) Explicit Dual Confirmation passed (Track 1 Button Token `confirm_order:<token>` or Track 2 Text Intent).
       c) Grand total <= customer's session `budget_limit`.
       d) Live Swiggy cart matches approved `cart_fingerprint` (zero price drift or OOS silent changes).
       e) Zero restricted medical products in basket.
     - Automatically supply `paymentMethod: "UPI"` and `generateUPIQR: true` with direct `upi://pay` deep links.
  4. **Verification**:
     - Run existing 77 tests + add Layer 4 checkout gate test suite proving all 5 conditions hold.
- **Rules to Remember**:
  - Bro style (human-to-human, 8th-grade reading level, zero buzzwords).
  - Strict Plan Gate: wait for user approval before modifying files.
  - Zero project code mocks.
