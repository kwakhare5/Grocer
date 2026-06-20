# Project Domain Context (Glossary)

This file defines the specific business language and component mapping for this project. **Agents MUST update this file** inline whenever a new term is introduced or a major decision is made.

### Domain Glossary
- **Restock Alert**: A notification sent to a household listing items predicted to deplete soon. _Avoid_: stock warning, low-stock notification.
- **Cart**: The active list of selected items and quantities ready for checkout. _Avoid_: basket, shopping list, order items.
- **Checkout**: The final step where a user confirms the cart to create and place an order. _Avoid_: transaction, checkout completion, purchase.

### Architectural Decisions (ADRs)
- **2026-06-20 - Global Rules Setup**: Transferred local project rules and commands to the central `~/.gemini/GEMINI.md` standard.
- **2026-06-20 - Time-Series Storage**: Chose TimescaleDB hypertable `price_history` for storing commodity price tracks to support price fluctuation analyses.
