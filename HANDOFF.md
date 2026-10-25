# Grocer v1.0 Session Handoff & Continuity Brief

> **Target Workspace:** D:\Grocer-v5
> **Branch:** main
> **Status:** Architecture & Project Memory Complete. Ready for Phase 0.

## 1. Goal
Build Grocer v1.0 from scratch as a production-grade WhatsApp Swiggy Instamart grocery concierge and account manager. Operates on real dark-store data across all 20 native MCP tools, zero fake mocks, radical truth, customer wallet advocacy, and deterministic Python 3-lock checkout.

## 2. Settled Non-Negotiables & Decisions (ADR 0001 - 0010)
1. **Real Data & Zero Mocks**: All 20 Swiggy Instamart MCP tools run against live endpoints. Contract tests use recorded real staging fixtures in `tests/fixtures/`.
2. **Brain vs Muscle Separation**: Gemini handles multi-turn conversation and candidate evaluation. Python enforces math in integer paise, 50ms button bypass, and the 3-lock checkout gate.
3. **Full Instamart Lifecycle**: Address management (view, switch, add via pin, delete), 1-tap reordering (`your_go_to_items`), and order history (`get_orders`).
4. **Radical Price Guarantee**: Aborts checkout if store price shifts by even ₹1 between receipt generation and payment click.
5. **Physical Button Checkout (Lock 1)**: Money is ONLY confirmed via physical WhatsApp button tap (`pay:<approval_id>:<option>`). Natural language text ("yes", "proceed") is strictly rejected.
6. **WhatsApp Payment Links**: Delivered via Swiggy HTTPS `bridgeUrl` in CTA URL buttons (Meta rejects `upi://` schemes).
7. **Wallet Champion Engine**: Tests top 2 coupons; never applies a coupon if the final payable bill increases. Warns on small-cart fees > 35%.
8. **5-Day Token Expiry & JIT Re-Auth**: Parked message replay in PostgreSQL resumes checkout instantly upon login.
9. **Respectful GPS Tracking**: 3 milestone-only notifications with live tracking map link; cancellations routed to Swiggy Care (`080-67466729`).
10. **DPDP Compliance**: 24-hour cleanup of personal addresses and line items. Dedicated "delete my data" command.

## 3. Project Memory Documents (Authoritative)
- PRD.md: Complete customer requirements and non-negotiables.
- ARCHITECTURE.md: Clean-slate v1.0 technical architecture and 5-layer design.
- DESIGN.md: WhatsApp interaction typography and 3-button layouts.
- AGENTS.md: Working rules, voice, and pair programming constraints.
- TASKS.md: Phased roadmap from Phase 0 to Phase 5.
- JOURNAL.md: Proof log of all architectural decisions.
- GLOSSARY.md: Canonical domain language.
- docs/adr/: ADR 0001 through 0010.
- docs/swiggy-mcp/: Official Swiggy Builders Club documentation.

## 4. Immediate Next Action
Proceed with **Phase 0** in TASKS.md:
1. Set up tests/fixtures/ directory.
2. Capture raw JSON staging responses for all 20 Instamart MCP tools.
3. Lock contract parsers to real fixtures.
