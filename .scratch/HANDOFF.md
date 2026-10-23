# Grocer v5.0 Session Handoff & Continuity Brief

> **Target Workspace:** D:\Grocer-v5
> **Branch:** main
> **Status:** Architecture & Project Memory Complete. Ready for Phase 0.

## 1. Goal
Build Grocer v5.0 from scratch as a production-grade WhatsApp Swiggy Instamart grocery concierge. Operates on real dark-store data, zero fake mocks, radical truth, customer wallet advocacy, and deterministic Python 3-lock checkout.

## 2. Settled Non-Negotiables & Decisions (ADR 0001 - 0006)
1. **Real Data & Zero Mocks**: MockCommerceAdapter is permanently eliminated. Contract tests use recorded real Swiggy staging fixtures in 	ests/fixtures/.
2. **Brain vs Muscle Separation**: Gemini handles multi-turn conversation and candidate evaluation. Python enforces math in integer paise, cart diffing, and the 3-lock checkout gate.
3. **No Blind Rank-1 Picking**: Search (search_catalog) is separated from basket modification (modify_basket). Gemini evaluates Swiggy's candidates against user constraints before adding.
4. **Physical Button Checkout (Lock 1)**: Money is ONLY confirmed via physical WhatsApp button tap (pay:<approval_id>:<option>). Natural language text ("yes", "proceed") is strictly rejected.
5. **WhatsApp Payment Links**: Delivered via Swiggy HTTPS ridgeUrl in CTA URL buttons (Meta rejects upi:// schemes).
6. **5-Day Token Expiry**: Parked message replay in PostgreSQL. When an expired user texts a list, the list is parked, login button sent, and list replayed on callback.
7. **Address Grounding**: Auto-grounds to primary Home address on turn 1 with a 1-tap [Change Address] WhatsApp list picker.
8. **Fast Coupons**: Bounded to top 2 applicable coupons (<4s turn latency).
9. **Launch Safety Cap**: ?1,000 maximum order limit.
10. **DPDP Compliance**: 24-hour cleanup of personal addresses and line items.

## 3. Project Memory Documents (Authoritative)
- PRD.md: Complete customer requirements and non-negotiables.
- ARCHITECTURE.md: Clean-slate v5.0 technical architecture and 5-layer design.
- DESIGN.md: WhatsApp interaction typography and 3-button layouts.
- AGENTS.md: Working rules, voice, and pair programming constraints.
- TASKS.md: Phased roadmap from Phase 0 to Phase 5.
- JOURNAL.md: Proof log of all architectural decisions.
- docs/adr/: ADR 0001 through 0006.

## 4. Immediate Next Action
Proceed with **Phase 0** in TASKS.md:
1. Set up 	ests/fixtures/ directory.
2. Capture raw JSON staging responses for all 19 Instamart MCP tools.
3. Lock contract parsers to real fixtures.
