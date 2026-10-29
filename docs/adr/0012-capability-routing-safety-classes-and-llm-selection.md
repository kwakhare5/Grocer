# ADR 0012: Capability Routing, Safety Classes, and Measured LLM Selection

> **Status 2026-10-27:** Active. Groq `openai/gpt-oss-120b` is primary for development and tests. The write floors are 0.80/0.85/0.95, not one 0.70 floor. Direct Gemini calls are gone. See `STATUS.md`.

## Context
The conversational layer classified every text into one of four intents: greeting, conversational Q&A, recipe, or grocery list. Anything unrecognised, including a price or stock question, fell into `grocery_list`, which searches and then writes to the basket. With the free Gemini quota exhausted (20 requests/day), every message took that path. A customer asking "how much is milk" could end up with milk in their basket. Adding two more intents would fix two phrasings and leave every unknown wording on the same unsafe path.

## Decision
1. **Capabilities replace intents.** A capability is one thing a customer wants, named after the goal (find item, check price, check stock, list addresses, order history, track order, reorder, add to basket, clear basket, choose payment method, checkout, support). Each capability maps to one or more Swiggy tools. The list is the product surface, not a list of example phrases.
2. **Every capability carries a safety class.**
   - `read`: never writes (search, price, stock, addresses, history, tracking, payment options).
   - `basket`: changes the basket only (add, change quantity, clear).
   - `account`: changes saved account data (add, switch, delete address).
   - `money`: spends money (checkout, confirm).
3. **The LLM never calls Swiggy.** It returns a routing decision: capability, extracted arguments, and a confidence score. Python validates the capability, enforces the safety class, and makes every Swiggy call.
4. **Unknown is not a write.** If the capability is unknown or confidence is below 0.70, Grocer takes the safe path: for a product-like message it runs a read-only search and shows options; otherwise it asks a clarifying question. No capability outside the list may reach a write path.
5. **The LLM provider is swappable and chosen by measurement.** One adapter interface serves Groq (free, used for development), Gemini, and future providers. Selection rule: run the same evaluation set on each provider, score capability accuracy, JSON validity and latency; the highest accuracy wins, ties go to the lower latency. A provider whose free quota cannot serve normal traffic cannot be the production primary without payment.
6. **Evaluation is evidence, not vibes.** At least 40 differently worded requests, mapped to expected capabilities, run manually once per gate and recorded in `JOURNAL.md`.

## Consequences
- Prompts and JSON contracts must stay provider-neutral and use each provider's JSON mode.
- The old four intent names are deleted; there is no compatibility layer.
- Provider quality becomes measurable and can change without touching the router.
- Capability growth follows the Swiggy tool surface, never a phrase list.
- The safe path costs one extra read-only search on unclear messages, never a wrong basket write.

## Amendment 2026-10-28
Item evaluation is **one batched model call per turn**, not one call per item. The batch prompt returns a result per item index; a missing or invalid entry uses the deterministic rules with no extra model call. Reason: a multi-item add on the free Groq tier ran out of tokens. Routing stays one call, so a 4-item add is 2 model calls, not 5.

## Amendment 2026-10-28 (basket state belongs to Python)
The router chooses add / set / remove / clear from the customer's words, never from what is already in the basket. `add_items` always adds the stated amount, even when the line exists; only an explicit "remove" uses `remove_item` and a new total ("make it N") uses `set_item`. Adds and explicit total sets apply immediately with a receipt; remove and clear keep a confirm button. Each item carries `amount` and `unit`; Python turns the amount into whole packs and only accepts a pack that meets it exactly (200 g is not 400 g, 500 g is not 1 kg). A missing item is named in the receipt as "Not added" or becomes a choice; no item is silently dropped. Abuse caps: 20 messages per user per hour (one warning, then silent drops), 10 items per message, quantity 1–99; media gets one honest reply. Reason: the 26-case live eval found the router guessing basket state, dropping the size word, and reporting a partial add as complete.

> **Amendment 2026-10-29:** the write verbs are `add_items`, `set_item`, `remove_item` and `clear_basket`. The `change_action` field is deleted from the schema, the prompt, the parser and the decision log. A change naming more than one item is refused with "one item at a time" instead of being silently turned into an add.
