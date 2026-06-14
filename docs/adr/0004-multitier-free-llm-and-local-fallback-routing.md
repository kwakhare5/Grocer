# 0004-multitier-free-llm-and-local-fallback-routing

We have chosen to implement a multi-tier API client chain (Anthropic -> Groq -> NVIDIA NIM) coupled with a state-retaining, rule-based Python keyword parser for the restock chatbot. This architecture guarantees 100% functionality in zero-budget environments by falling back to free cloud Llama endpoints or completely local offline processing while keeping the stateful, multi-turn LangGraph conversation structure intact.
