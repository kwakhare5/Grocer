# Local Deterministic Fallbacks due to API Cost Constraints

We decided to prioritize local, deterministic, and free logic (regex, string matching, templates) over remote LLM API dependencies to guarantee the system can run at zero cost.

## Context
The system was originally designed with multiple integration points to the Claude API (message generation, reply parsing, recipe ingredient extraction). However, running these APIs incurs recurring costs. To accommodate a hard constraint of zero API spend, the system must remain fully functional using local logic, making paid API calls entirely optional or secondary.

## Decision
1. **Fuzzy Item Resolution:** We will use local string similarity matching (using Python's built-in `difflib.get_close_matches` or Jaccard similarity of character n-grams) to map generic recipe ingredients to catalog items instead of neural embeddings.
2. **Deterministic Webhook Parsing:** The WhatsApp reply parser will prioritize keyword and regex matching for standard intents (e.g. YES, NO, CONFIRM, and listing items by index/name) before falling back to any LLM.
3. **Structured Templates:** Message alerts and confirmations will use dynamic template string generation with random variations to keep them friendly, bypassing automated LLM writing by default.

## Consequences
- The application will run entirely for free and can be tested locally without active Anthropic/Twilio subscriptions.
- Conversational flexibility will be slightly reduced (users must use standard keyword patterns or clearly structured names rather than free-form conversational chatter).
