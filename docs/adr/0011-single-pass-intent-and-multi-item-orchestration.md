# ADR 0011: Single-Pass Conversational Intent, Multi-Item Extraction, and Partial Disambiguation

> **Superseded by ADR 0012.** The four-intent classifier described here is replaced by capabilities with safety classes. The single-pass turn, dialogue history and multi-item extraction decisions still stand.
>
> **Status 2026-10-27:** The legacy second LLM call still exists in `candidate_evaluator.py`; code item 2 removes it. See `docs/adr/README.md`.

## Context
In early staging, incoming customer messages were routed directly to Swiggy dark-store catalog search before determining intent. This caused greetings (e.g. "hello") to search for a SKU named "hello", return 0 items, and respond with "couldn't find items". In addition, grocery candidate evaluation was faked using static keyword dictionaries, multi-item shopping lists were collapsed into single searches, and dialogue history was ignored.

## Decision
1. **Single-Pass Conversational Brain (<2.0s):** Every incoming non-button text message is processed first by Gemini 3.5 Flash using structured output. Gemini classifies intent (`GREETING`, `CONVERSATIONAL_QA`, `GROCERY_LIST`, `RECIPE_CHECKLIST`, `ZERO_ADDRESS_ONBOARDING`), produces conversational replies for chit-chat, and extracts parsed items (`name`, `quantity`, `constraints`) in a single prompt turn.
2. **Zero Store Search on Greetings/Q&A:** If intent is `GREETING` or `CONVERSATIONAL_QA`, Grocer sends the conversational response immediately via WhatsApp text. Swiggy Instamart catalog search and cart mutation endpoints are never touched.
3. **Dialogue History Context:** Multi-turn dialogue history is persisted in `grocer.sessions.history` (sliding window of 12 turns) and passed to Gemini on every turn to support references, clarifications, and recipe context.
4. **Parallel Dark-Store Catalog Search:** For multi-item grocery lists, dark-store candidate searches (`search_catalog`) run concurrently across all extracted items, cutting turn latency from ~1.5s to ~350ms.
5. **Partial Disambiguation in Mixed Lists:** If a grocery list contains unambiguous items alongside an ambiguous discretionary snack or drink, Grocer adds the clear items to the basket, generates the approval receipt, and asks for clarification on the ambiguous item within the same message.

## Consequences
- Greetings and casual questions receive instant, natural replies without false "out of stock" errors.
- Multi-item shopping lists ("milk, bread, and eggs") are correctly parsed, searched, and added to the basket in one step.
- Latency stays strictly under 3.5 seconds by eliminating multi-stage LLM chains.
- Zero fake keyword dictionaries or hardcoded recipe lists in production code.
