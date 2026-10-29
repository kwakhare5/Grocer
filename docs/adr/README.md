# ADR Index

ADRs record decisions at a point in time. They are amended with status notes, not rewritten. `STATUS.md` is the current truth; if an ADR and `STATUS.md` disagree, `STATUS.md` wins.

| ADR | Decision | Status 2026-10-27 | Current note |
|---|---|---|---|
| 0001 | Single-turn engine and button router | Amended | 25ms ACK, 50ms button and under-3.5s turn are targets. The webhook is synchronous. |
| 0002 | Live address grounding and price fingerprint | Active | Grounding uses Swiggy's `defaultAddressId`. The fingerprint includes payable paise, so any paise change fails Lock 2. |
| 0003 | Wallet guardrails, bridge payments, rider tracking | Active | Coupon guard works; savings show on receipts and in reorder/switch replies. Tracking calls `track_order` with saved coordinates and falls back to delivery status. |
| 0004 | Vague staples, physical button checkout, parked replay | Amended | Access + 30-day refresh token exists. Park and replay are wired. Vague staples auto-pick with a working Change/swap; discretionary items show choices. |
| 0005 | Cart sync, fast coupons, address grounding, payment buttons | Partial | Receipt buttons are Pay, Keep only new (when the basket had items), Change item (vague staples) and Clear. COD is parked. Address change happens from the address card. |
| 0006 | Safety cap, milestones, DPDP erasure | Partial | ₹1,000 cap stays. Cap-raise reopens the same receipt. The DPDP scrub and delete cascade are built, and app queries run as the non-superuser `grocer_app` role (migration 007). RLS is skipped: `anon`/`authenticated` have zero schema access. |
| 0007 | Lifecycle guardrails | Active | Switch clears and rebuilds the basket. The delete guard is wired. Split orders poll every id. |
| 0008 | Pin onboarding, reorder, bridge payments | Partial | Typed-text address add is built. Reorder is fixture-only until the account has a past order. |
| 0009 | Recipes, fees, destinations, post-order additions | Amended | Recipes are in v1 as a plan-confirm-add flow with a stored 30-minute plan. The fee warning and post-order truth are built (2026-10-28). One-time destination is parked. |
| 0010 | Session lifecycle, JIT auth, onboarding | Active | Refresh first, park only if refresh fails. The callback replays the saved message. |
| 0011 | Single-pass intent and multi-item orchestration | Superseded | Replaced by ADR 0012. No extra classification call; candidate evaluation is one batched call per turn. |
| 0012 | Capability routing, safety classes, LLM selection | Active | Groq is primary and the only adapter. Direct Gemini calls are gone. Amended 2026-10-29: four write verbs. |

The full blocker list is in `STATUS.md` §4–§5.
