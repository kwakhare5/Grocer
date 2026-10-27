# ADR Index

ADRs record decisions at a point in time. They are amended with status notes, not rewritten. `STATUS.md` is the current truth; if an ADR and `STATUS.md` disagree, `STATUS.md` wins.

| ADR | Decision | Status 2026-10-27 | Current note |
|---|---|---|---|
| 0001 | Single-turn engine and button router | Amended | 25ms ACK, 50ms button and under-3.5s turn are targets. The webhook is synchronous. |
| 0002 | Live address grounding and price fingerprint | Active with deviation | Grounding uses the first saved address, not the default. The fingerprint includes payable paise. |
| 0003 | Wallet guardrails, bridge payments, rider tracking | Active with gaps | Coupon guard works. Savings message is not sent. Tracking does not call `track_order`. |
| 0004 | Vague staples, physical button checkout, parked replay | Amended | Access + 30-day refresh token exists. Parked replay is broken. |
| 0005 | Cart sync, fast coupons, address grounding, payment buttons | Partial | Current buttons are Pay + Clear. COD, Change Address and Change Items are target. |
| 0006 | Safety cap, milestones, DPDP erasure | Partial | ₹1,000 cap stays. Cap-raise is broken. DPDP is partial. |
| 0007 | Lifecycle guardrails | Partial | Address switch does not rebuild the cart. Delete guard is not wired. Split tracking follows one order. |
| 0008 | Pin onboarding, reorder, bridge payments | Partial | Typed-text address add is missing. Reorder is fixture-only. |
| 0009 | Recipes, fees, destinations, post-order additions | Not implemented | Examples, not v1 scope. Recipes have no tool. Do not describe as live. |
| 0010 | Session lifecycle, JIT auth, onboarding | Amended | Refresh first. Parked status and replay do not match. |
| 0011 | Single-pass intent and multi-item orchestration | Superseded | Replaced by ADR 0012. The legacy second LLM call is removed. |
| 0012 | Capability routing, safety classes, LLM selection | Active | Groq is primary. Legacy direct Gemini calls remain until code item 2. |

The full blocker list is in `STATUS.md` §4–§5.
