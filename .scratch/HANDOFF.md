# Grocer v1.0 — Session Handoff & Architecture Alignment Blueprint

> **Branch:** `grocer-v1` on `D:\Grocer-v5`  
> **Head Commit:** `7e0e2fc` (in sync with `origin/grocer-v1`)  
> **Source of Truth:** `PRD.md`, `ARCHITECTURE.md` (clean-slate v1.0, 5 layers)  
> **Universal Test Runner:** `powershell -ExecutionPolicy Bypass -File .\verify.ps1` (104/104 passing)  

---

## 1. Executive Summary: What Happened in Live WhatsApp Testing
During live WhatsApp testing on a real phone, sending `"hello"` or `"hi"` resulted in:
> *"Sorry, I couldn't find items matching 'hello' at your local dark store. Could you try a different brand or item name?"*

### Root Cause Analysis (Zero Glaze)
1. **Gemini Brain Was Faked & Bypassed:** In `backend/agent/candidate_evaluator.py` (lines 100–520), the AI was bypassed in favor of hardcoded static dictionaries (`VAGUE_STAPLE_KEYWORDS`, `DISCRETIONARY_CATEGORIES`, `qa_word_triggers`) and static recipe constants (`_CHAI_RECIPE`, `_AGLIO_OLIO_RECIPE`). The Gemini call `_call_gemini_candidate_evaluator` on line 191 was defined but **never called**.
2. **Unconditional Catalog Search on Every Inbound Text:** In `backend/channels/whatsapp.py` line 242, the code unconditionally ran `candidates = search_catalog(msg.text)`. When the user sent `"hello"`, it literally queried the Swiggy Instamart dark store for a grocery SKU named `"hello"`. Swiggy returned 0 items, and line 304 fired the "couldn't find items" message.
3. **Single-Item Cart Assembly Trap:** In `whatsapp.py` lines 260–275, the cart assembly only handles `evaluation.selected_candidate` (one single item). Multi-item lists like `"milk, bread, and eggs"` are searched as a single concatenated search query and fail.
4. **Zero Multi-Turn Context:** `whatsapp.py` reads only `msg.text` in isolation and ignores past messages in `grocer.inbound_messages`.

---

## 2. What Is 100% Real, Working & Live (DO NOT BREAK)
The infrastructure, database, security, and commerce engines are real, verified, and running live in production:
1. **Supabase PostgreSQL Schema:** 6/6 tables active (`users`, `inbound_messages`, `oauth_tokens`, `sessions`, `approvals`, `checkouts`).
2. **Channel Ingestion Shield:** Webhook signature verification (HMAC-SHA256 <25ms), PostgreSQL deduplication (`ON CONFLICT (wa_message_id) DO NOTHING`), per-user advisory locks, and stale message filtering.
3. **Commerce Engine:** `backend/integrations/commerce/swiggy_client.py` running real Swiggy Instamart tools; `CompositeCartManager` running full target cart assembly and `update_cart` reconciliation; `CustomerAdvocate` running bounded coupon trials.
4. **3-Lock Payment Gate:** Lock 1 (physical button authority), Lock 2 (live price drift & ₹1,000 launch safety cap check), Lock 3 (atomic PostgreSQL CAS on `grocer.approvals`), official HTTPS Swiggy `bridgeUrl` CTA URL button.
5. **Meta Outbound WhatsApp Delivery:** `backend/channels/whatsapp_client.py` pushes real WhatsApp interactive receipt cards, quick-reply buttons, and CTA buttons via Meta Graph API.
6. **Live Deployments:**
   - FastAPI Backend on Render: `https://grocer-backend-qwk4.onrender.com` (Health 200 OK, Webhook live).
   - Next.js OAuth Frontend on Vercel: `https://grocerr.vercel.app` (Status 200 OK).

---

## 3. The Immediate Task for the New Chat Session
Align Layer 2 with `ARCHITECTURE.md` by replacing the hardcoded keyword hackery with a real Gemini Conversational Orchestrator.

### Execution Plan (Step-by-Step)
1. **Clean Out Hardcoded Hacks in `backend/agent/candidate_evaluator.py`:**
   - Delete `VAGUE_STAPLE_KEYWORDS`, `DISCRETIONARY_CATEGORIES`, `qa_word_triggers`, and static recipes (`_CHAI_RECIPE`, `_AGLIO_OLIO_RECIPE`).
2. **Implement Real Gemini Intent & Multi-Item Extractor:**
   - Send incoming customer message + last 5 turns of conversation from `grocer.inbound_messages` to Gemini 3.5 Flash (`gemini-2.5-flash`).
   - Classify intent into:
     - `GREETING` / `CONVERSATIONAL_QA`: Gemini generates a friendly, natural reply in plain English/Hinglish (e.g., "Hey! What groceries do you need today?"). Returns directly to WhatsApp without searching Swiggy or touching the cart.
     - `GROCERY_LIST` / `RECIPE`: Gemini extracts a list of individual target items (e.g., `[{"name": "Amul Taaza Milk", "pack": "1L", "quantity": 1}, {"name": "Eggs", "pack": "6 pcs", "quantity": 1}]`).
3. **Wire Multi-Item Processing in `backend/channels/whatsapp.py`:**
   - Route through Gemini orchestrator first.
   - If greeting/QA: send text response immediately via `wa_client.send_text_message`.
   - If grocery items: iterate through the extracted items, run `search_catalog` for each item, assemble the full composite cart via `CompositeCartManager.assemble_and_update_cart`, create approval in `grocer.approvals`, and send the interactive receipt card with `[Pay: ₹X]` and `[Clear Basket]`.
4. **Run Universal Verification & Prove Real Live Chat:**
   - Update `tests/test_catalog_search.py` and `tests/test_whatsapp_live_loop.py` to test real greetings ("hello", "hi") and multi-item requests.
   - Ensure `powershell -ExecutionPolicy Bypass -File .\verify.ps1` exits 0.
   - Commit, push to `grocer-v1`, and verify on Render.

---

## 4. Quick-Start Command for New Chat
Paste this into the prompt of your new chat:
```text
Resume Grocer v1.0 from .scratch/HANDOFF.md. The infrastructure, Swiggy MCP client, Supabase database, and 3-lock checkout are 100% verified and live on Render. 

The immediate problem: In backend/agent/candidate_evaluator.py and backend/channels/whatsapp.py, Gemini was bypassed in favor of hardcoded keyword dictionaries and an unconditional search_catalog call, which broke greetings ('hello' -> 'no items found').

Execute Step 1 through Step 4 of the Handoff Execution Plan: delete the keyword dictionaries, wire real Gemini intent classification/extraction with multi-turn history, support multi-item lists, and prove with .\verify.ps1.
```
