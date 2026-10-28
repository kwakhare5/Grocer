# Grocer

A grocery concierge on WhatsApp, backed by Swiggy Instamart. You text in plain
language; Grocer answers questions, builds a basket, and walks you to a payment
button. Chat is the front door to every Instamart capability the Swiggy MCP
exposes.

Independent project. Not affiliated with or endorsed by Swiggy.

## What you can ask

- Shopping: "1 litre milk and 6 eggs", "make pizza for 5 people" (plan first, then add)
- Price, stock, coupons, store and delivery questions
- Saved addresses: list, add by text or GPS pin, switch, delete
- Orders: history, live status, bills, reorder, support reports
- Basket: view, change, clear, keep
- Payments: UPI only; the bot never charges anything by itself

Recipes are planned, priced, and shown before any write. Nothing is added until
you confirm.

## How it works

```
WhatsApp Cloud API -> FastAPI webhook -> Python capability router
                                            |            |
                                       Swiggy MCP    PostgreSQL
                                       (your token)  (Supabase)
```

- Python owns money, stock checks, safety classes, cart fingerprints, and the
  checkout locks. The LLM only handles language and candidate evaluation.
- Every message routes to a capability with a safety class (`read`, `basket`,
  `account`, `money`). A read capability can never reach a write path.
- The app connects to PostgreSQL as a DML-only role; migrations run separately
  as the owner and the migration ledger is read-only for the app.

## Safety rules that never move

- An order can only be placed by a physical WhatsApp button tap. Text "yes"
  never places an order.
- The default cart cap is ₹1,000. Raises need an explicit tap.
- `LIVE_CHECKOUT_ENABLED=false` by default, enforced in code.
- Out of stock, a closed store, or a failed API call is reported honestly. No
  silent omissions.
- The best valid coupon is applied only when the payable total does not go up.

## Privacy

- Addresses, order snapshots, and plan coordinates are deleted after 24 hours.
- "delete my data" removes messages and geocodes, clears the plan and
  onboarding state, and anonymizes the user row.

## Status

| Area | State |
|---|---|
| Chat, basket, addresses, coupons, orders, tracking, privacy | Live (non-payment) |
| Recipe plans, reactions, support reports | Code-complete; handset proofs open |
| Checkout and payment | Never live-tested; no order has been placed |

The only current truth is [STATUS.md](STATUS.md). Product target is in
[PRD.md](PRD.md); behavior and gaps are in [ARCHITECTURE.md](ARCHITECTURE.md);
WhatsApp UI is in [DESIGN.md](DESIGN.md); decisions are in `docs/adr/`.

## Run it

Python 3.12 and Node.js 20+.

```bash
pip install -r requirements.txt
npm ci
python scripts/migrate.py
uvicorn backend.main:app --port 8000
```

Set these environment variables before starting (see `.env.example`):

```
WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_BUSINESS_ACCOUNT_ID, WHATSAPP_ACCESS_TOKEN,
WHATSAPP_APP_SECRET, WHATSAPP_VERIFY_TOKEN, DATABASE_URL, DATA_ENCRYPTION_KEY,
TEST_DATABASE_URL, GROQ_API_KEY
```

For the landing page, `NEXT_PUBLIC_WHATSAPP_NUMBER` supplies the real chat link.
Without it the page shows the placeholder number and disables the button.

## Tests

```powershell
.\verify.ps1        # offline: schema, lint, unit tests, web build
.\verify.ps1 -Db    # adds the database suite on grocer_test
```

`pytest -m live` calls real external services and is excluded by default.
Database tests refuse to run unless `TEST_DATABASE_URL` names the separate
`grocer_test` database. Tests never write production data.

GitHub Actions runs ruff, every non-live test on a throwaway Postgres, and the
Next build on each push to `main`.

## Layout

```
backend/          FastAPI app, WhatsApp channel, agent, Swiggy adapter
migrations/       PostgreSQL migrations 001-010
tests/            offline, database, and live-marked suites
scripts/          migrations, database checks, live driver, router eval
app/              Next.js landing page and Swiggy OAuth bridge
docs/adr/         architecture decisions
```
