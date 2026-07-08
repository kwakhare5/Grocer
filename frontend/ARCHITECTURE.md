# ARCHITECTURE.md — The Technical Blueprint (Heavy Doc)

# This is the HEAVY file. Load on-demand only.
# CLAUDE.md stays lean (max 200 lines, stack + commands + rules only).
# Everything else lives here: DB schema, file tree, decisions, API contracts.
# The AI reads this when you use @ZOOM or when explicitly told to.


## 1. PROJECT OVERVIEW & BUSINESS LOGIC
_Write the massive business pitch here. Explain why this project exists, what problem it solves, and who the users are. The AI doesn't need this to write a button component, but humans do._

## 2. SYSTEM ARCHITECTURE
_How do the pieces fit together? (Provide a diagram or bullet points)._
- **Frontend:** [e.g., Next.js dashboard talking to REST API]
- **Backend:** [e.g., Python FastAPI orchestrating the ML models]
- **Database:** [e.g., PostgreSQL for primary data, TimescaleDB for metrics]

## 3. DATABASE SCHEMA
_Put your massive SQL tables or Prisma schemas here._
```sql
-- Example:
-- CREATE TABLE users ( id UUID PRIMARY KEY );
```

## 4. API CONTRACTS & INTEGRATIONS
_List third-party APIs (Stripe, Twilio, external MCPs) and what they are used for._

## 5. HISTORICAL DECISIONS (ADRs)
_Why did we do it this way? Log the graveyard of technical choices._
- **[Date]: Why we chose X over Y.** (e.g., "We chose raw SQL over Prisma because we needed complex geospatial queries.")
