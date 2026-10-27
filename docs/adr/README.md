# ADR Index

ADRs record decisions at a point in time. They are amended with status notes, not rewritten. `STATUS.md` is the current truth; if an ADR and `STATUS.md` disagree, `STATUS.md` wins.

| ADR | Decision | Status 2026-10-27 | Current note |
|---|---|---|---|
| 0001 | Single-turn engine and button router | Amended | 25ms ACK, 50ms button and under-3.5s turn are targets. The webhook is synchronous. |
| 0002 | Live address grounding and price fingerprint | Active | Grounding uses Swiggy's `defaultAddressId`. The fingerprint includes payable paise, so any paise change fails Lock 2. |
| 0003 | Wallet guardrails, bridge payments, rider tracking | Active with gaps | Coupon guard works. The savings line is not sent. Tracking calls `track_order` with saved coordinates and falls back to delivery status. |
| 0004 | Vague staples, physical button checkout, parked replay | Amended | Access + 30-day refresh token exists. Park and replay are wired. Vague-item behavior is not deterministic yet (Phase 7). |
| 0005 | Cart sync, fast coupons, address grounding, payment buttons | Partial | Current buttons are Pay + Clear. COD, Change Address and Change Items are target. |
| 0006 | Safety cap, milestones, DPDP erasure | Partial | ₹1,000 cap stays. Cap-raise reopens the same receipt. DPDP is partial (Phase 6). |
| 0007 | Lifecycle guardrails | Active | Switch clears and rebuilds the basket. The delete guard is wired. Split orders poll every id. |
| 0008 | Pin onboarding, reorder, bridge payments | Partial | Typed-text address add is built. Reorder is fixture-only until the account has a past order. |
| 0009 | Recipes, fees, destinations, post-order additions | Amended | Recipes are in v1 as a plan-confirm-add flow. Fee warning and post-order truth are Phase 7. One-time destination is parked. |
| 0010 | Session lifecycle, JIT auth, onboarding | Active | Refresh first, park only if refresh fails. The callback replays the saved message. |
| 0011 | Single-pass intent and multi-item orchestration | Superseded | Replaced by ADR 0012. No extra classification call; candidate evaluation is one call per item and is intentional. |
| 0012 | Capability routing, safety classes, LLM selection | Active | Groq is primary and the only adapter. Direct Gemini calls are gone. |

The full blocker list is in `STATUS.md` §4–§5.
