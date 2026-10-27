# ADR 0001: Customer Experience Speed: Snappy Button Action vs Warm Conversational Concierge

> **Status 2026-10-27:** Amended. The webhook is synchronous today; 25ms ACK, 50ms button and under-3.5s turn are targets, not measured guarantees. See `docs/adr/README.md` and `STATUS.md`.

## Context
When someone shops for groceries on WhatsApp, there are two distinct user interactions:
1. **Conversational Inquiries & Shopping Lists:** When texting groceries (*"doodh, bread, and eggs"*), asking cooking questions, or speaking in Hinglish, the customer expects a warm, intelligent conversational assistant that understands context.
2. **Interactive Button Actions:** When a customer taps an interactive WhatsApp button (such as `[Pay ₹240]`, `[Change Address]`, or `[Clear Basket]`), there is no ambiguous text to decipher. The customer expects immediate app-like execution. In competitor bots, tapping a button triggers a 10-second "Thinking..." pause while an LLM formats chatty filler, destroying mobile conversion and user patience.

## Decision
1. **Snappy Button Execution (<100ms):** Tapping any interactive WhatsApp button triggers direct, deterministic action execution, returning payment links or address selection pickers in under 100ms without waking up the conversational LLM.
2. **Warm Single-Pass Conversational Brain (<3.5s):** Natural text messages, recipe inquiries, and Hinglish grocery lists are handled by Gemini in a single pass with the last 12 turns of dialogue context, providing helpful, natural English responses in under 3.5 seconds.

## Consequences
- Physical button taps feel as responsive as a native mobile app.
- Conversational chat remains warm and intelligent without token bloat or latency delays.
- Clear separation between user action (buttons) and user exploration (text).
