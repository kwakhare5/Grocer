# Task Tracker: Swiggy Builder Club Production Alignment

- [x] **Track 1: Financial & Security Defenses (Plan Items E, F, G)**
  - [x] Write failing invariant tests in `backend/tests/test_safety_invariants.py` <!-- id: 0 -->
  - [x] Implement `CHECKOUT_MODE=review` guard in `backend/integrations/commerce/swiggy_adapter.py` <!-- id: 1 -->
  - [x] Remove plaintext `.vault_tokens.json` writes & enforce strict customer isolation in `token_vault.py` <!-- id: 2 -->
  - [x] Fix confirmation regex (negations first, plain "yes/ok" support, cart snapshot binding) in `guards.py` & `engine.py` <!-- id: 3 -->
  - [x] Set 10-second payment tracking cadence in `engine.py` <!-- id: 4 -->
  - [x] Handle WhatsApp receipt splitting for >1024 char messages in `whatsapp.py` <!-- id: 5 -->
  - [x] Verify Track 1 tests pass green <!-- id: 6 -->

- [x] **Track 2: Domain Constraints & Catalog Depth (Plan Items C, D)**
  - [x] Add `budget_inr` to `CustomerSession` & enforce code-level checkout rejection if total > budget <!-- id: 7 -->
  - [x] Expand catalog search in `tools.py` to 10 items with pack size and savings metadata <!-- id: 8 -->
  - [x] Add structured failure error objects to `tools.py` <!-- id: 9 -->

- [x] **Track 3: Memory Resilience & Media Routes (Plan Items B, Asset Routes)**
  - [x] Increase conversation history window to 20 user turns in `engine.py` <!-- id: 10 -->
  - [x] Replace amnesiac history deletion on Gemini 400 with non-destructive tool response compaction <!-- id: 11 -->
  - [x] Copy `Demo video with audio.mp4` to `public/demo.mp4` to resolve video player 404 <!-- id: 12 -->
  - [x] Clean 6 unused imports and deduplicate phrase sets <!-- id: 13 -->

- [x] **Track 4: Procedural Protocol & Step-Limit Recovery (Plan Items B, D)**
  - [x] Write invariant tests in `backend/tests/test_safety_invariants.py` asserting prompt procedure and step-limit recovery <!-- id: 14 -->
  - [x] Embed 8-step procedural shopping protocol in `backend/agent/prompts.py` <!-- id: 15 -->
  - [x] Embed 4 worked examples (budget cap, dietary exclusion, brand fidelity, quantity correction) in `prompts.py` <!-- id: 16 -->
  - [x] Implement honest 8-step ReAct limit recovery + live basket receipt + action buttons in `backend/agent/engine.py` <!-- id: 17 -->
  - [x] Verify 62/62 tests passing green (100%) <!-- id: 18 -->

- [x] **Track 5: Live Model Benchmarking & Thinking Config (Plan Item A)**
  - [x] Test `gemini-3.8-flash` with thinking level vs `gemini-3.5-flash-lite` on live API key <!-- id: 19 -->
  - [x] Lock the optimal, lowest-latency model configuration (`gemini-3.5-flash-lite` at 1.69s vs 8.09s for 3.8-flash) <!-- id: 20 -->

- [x] **Track 6: 25-Case Synthetic Model Evaluation Suite (Plan Item H)**
  - [x] Author `backend/tests/test_eval_suite.py` with 25 synthetic shopping cases <!-- id: 21 -->
  - [x] Verify constraint satisfaction: budget, diet, brand fidelity, recovery (87/87 tests green) <!-- id: 22 -->

- [x] **Track 7: Swiggy Builder Club Application Package & Demo Walkthrough (Plan Part 5)**
  - [x] Fill all verified application fields for Google Form `https://forms.gle/4vkeKyqm15Qb6fnJA` in `docs/SWIGGY_BUILDER_CLUB_APPLICATION.md` <!-- id: 23 -->
  - [x] Finalize reviewer demo video script & official email to `builders@swiggy.in` <!-- id: 24 -->
