# Grocer

Grocer is a WhatsApp grocery assistant built around Swiggy Instamart. It helps a customer build and review a basket through conversation. The current target is a **review-only release**: confirmation completes a review without placing or charging for an order.

## Current state

The local code verifies full India E.164 sender identity, binds each Swiggy OAuth connection to a single-use WhatsApp ticket, persists signed webhook intake and task state in PostgreSQL, and binds basket approval to the observed address and complete payable total. Cart quantities, unknown checkout outcomes, and external cart edits have explicit stop paths. These changes have local automated coverage; they have not been validated against this deployment's PostgreSQL schema or real Swiggy and WhatsApp accounts.

The assistant still relies on model judgment for a complete requested-item ledger and ingredient-safe substitution decisions. Stable shopping preferences, payment reconciliation after restart, and reliable retry of uncertain WhatsApp sends are unfinished. Do not advertise or enable live checkout until the gates in [the rollout runbook](docs/RELEASE_RUNBOOK.md) pass.

## Run locally

Use Python 3.12 and Node.js with the checked-in dependency files. Copy `.env.example` to `.env` and supply the required secrets through your local environment or deployment secret manager. A real Swiggy adapter and signed WhatsApp intake require PostgreSQL, encryption, OAuth, and Meta configuration; `CHECKOUT_MODE=review` and `LIVE_CHECKOUT_ENABLED=false` are the safe defaults.

```powershell
python -m pip install -r requirements.txt
npm install
python -m pytest backend/tests -q
npm run lint
npm run build
```

For a fresh database only, create the OAuth schema with `migrations/bootstrap_fresh.sql`, then apply the numbered migrations. Existing databases need a schema audit and backup first. [The runbook](docs/RELEASE_RUNBOOK.md) gives the order and verification queries.

## Code map

| Area | Files |
|---|---|
| Webhook and worker | `backend/api/whatsapp.py`, `backend/channels/message_store.py` |
| Conversation and basket safety | `backend/agent/engine.py`, `backend/agent/approval.py`, `backend/agent/tools.py` |
| Commerce adapter and OAuth | `backend/integrations/commerce/`, `backend/api/oauth.py` |
| Deployment entry points | `backend/main.py`, `app/api/whatsapp/webhook/route.ts`, `render.yaml` |
| Database changes | `migrations/` |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the actual request path and current limitations, and [implementation_plan.md](implementation_plan.md) for the complete repair plan.
