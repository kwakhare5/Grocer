# GROCER live-language root-cause audit

> Read-only audit of the deployed WhatsApp route at `a194809` and the pasted “PERMANENT FIX SPEC.”

## Verdict

The pasted diagnosis is substantially right about the primary failure: the live WhatsApp ShoppingTask route does not call Gemini. It uses regex/rules for free text. That is the main reason the bot cannot handle unpredictable English or context-dependent replies.

The pasted fix must **not** be executed verbatim. Its deletion list would remove live dependencies, and its shortage recovery would overwrite the customer’s intended basket before approval.

## Code proof

- `render.yaml:23-28` enables `swiggy_mcp`, `SHOPPING_TASK_ROUTE=true`, and review mode.
- `backend/api/whatsapp.py:74-90` sends that route to `shopping_task_service.process_message`.
- `backend/main.py:51-60` constructs `ShoppingTaskApplicationService` without a language-model implementation.
- The service therefore creates `MessageUnderstandingService()` (`backend/intent/task_service.py:60-72`) and sends free text to it (`backend/intent/task_service.py:234-249`).
- That interpreter constructs only `RuleBasedExtractor`, returns `source="rules"`, and chooses operations through fixed regexes (`backend/intent/message_understanding.py:19-57,75-177`). It accepts a generic grocery request only if an extracted quantity is explicit (`:174-177`).
- Gemini is inside the legacy `IntentParser` (`backend/intent/parser.py:449-609`), used by the legacy orchestrator, not by the live ShoppingTask service.
- The interpreter receives only the current message, not task state, pending question, basket, or offered options (`message_understanding.py:25`). It therefore cannot reliably interpret “keep,” “that one,” or “make it two” in context.
- Buttons are mapped separately by IDs (`backend/intent/task_service.py:251-283`), so typed equivalents can behave differently.
- Model behavior is not proven by tests: `GeminiIntentExtractor` returns `None` during pytest (`backend/intent/parser.py:460-463`), and active task-service tests use `MockCommerceAdapter` (`backend/tests/test_task_service.py:9,37,97-110`).

## What the pasted spec gets right

- Put a model at the existing `MessageUnderstanding` proposal boundary; keep the deterministic reducer authoritative.
- Give the model bounded conversation context.
- Validate model output into the existing Pydantic schema.
- Use Gemini API-enforced structured output, which Google recommends for extraction/classification/agent workflows: [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).
- `gemini-3.5-flash-lite` is a real current model ID and supports structured output: [Gemini models](https://ai.google.dev/gemini-api/docs/models). Key-specific access still needs a runtime model-list probe.
- Its legacy-size estimate is directionally correct: the named files are 7,186 lines, or 8,062 including `stages/`.

## What is unsafe or unproven

1. The rules-first `confidence >= 0.95` design can preserve confidently wrong regex parses. Exact buttons/bounded controls should stay deterministic; ordinary English should use the context-aware model.
2. The old Gemini extractor cannot simply be reconnected: it emits the old `IntentContract` shape, has no ShoppingTask context, parses prompt-produced JSON rather than API-enforced structured output, and uses synchronous HTTP.
3. “25 of 32 tests exercise dead code” is not established. There are exactly 32 test files, but the spec enumerates 21 delete candidates and 10 keep candidates and omits `test_confirmation_integrity.py`. Classify tests by imports/coverage before deletion.
4. The deletion list breaks live imports: `message_understanding.py:11` imports `RuleBasedExtractor` from `parser.py`; `catalog_resolution.py:10-12` imports live normalization from `semantics.py`; WhatsApp inherits from `channels/base.py`, which imports legacy modules; `main.py:25,92` still mounts `intent_chat`, which imports legacy modules.
5. Reduced-quantity evidence is real, but the spec reads it from the wrong object. `SwiggyMCPAdapter.update_cart` attaches `reducedQuantityItems` to the returned `updated` cart (`backend/integrations/commerce/swiggy_adapter.py:219-229`). `_synchronize` then performs a separate `verified = get_cart(...)` (`backend/intent/task_service.py:349-355`), which may not retain that update metadata. Reconciliation must combine `updated.reduced_quantity_items` with verified read-back quantities.
6. Never rewrite `task.desired_basket` to Swiggy’s capped quantity before the user accepts it. That destroys the authoritative customer intent. Store observed provider drift separately and change intent only after explicit approval.
7. Current Gemini guidance marks older sampling controls such as `temperature` deprecated for current 3.x models; use the current documented request schema rather than copying settings blindly.

## Final repair decision

Keep the durable ShoppingTask, reducer, PostgreSQL inbox/outbox, `CommercePort`, Swiggy adapter, read-back verification, and review-mode checkout gate. Add one async, context-aware Gemini structured-output adapter that returns the existing `MessageUnderstanding`. Keep deterministic handling for interactive IDs and exact state-aware controls. Preserve desired intent separately from observed Swiggy cart drift. Test actual failed transcripts plus paraphrases, then run the complete hosted review-mode phone flow against real MCP. Delete legacy code only after import isolation and that live gate passes.

This will not be a general ChatGPT clone. It can be a robust English grocery agent: flexible language understanding inside a narrow domain, deterministic safety, truthful provider reporting, and explicit confirmation before a chargeable action.

Official provider flow: [Swiggy Instamart reference](https://mcp.swiggy.com/builders/docs/reference/instamart/), [order groceries recipe](https://mcp.swiggy.com/builders/docs/build/recipes/order-groceries/).
