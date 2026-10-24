# Product Journal — Grocer v1.0 Clean-Slate

A chronological record of project milestones, architectural decisions, and verification proof. This file is append-only.

---

## Log Entries

### [GROCER v5 — Clean-Slate Rebuild & Project Memory Setup] 2026-10-25

#### Work Card: Initialize Isolated Branch and Complete 6-Doc Project Memory
- **Problem**: Legacy codebase suffered from conflicting architectural drafts, 80 fake in-memory mock tests (`MockCommerceAdapter`), broken assumptions about WhatsApp payment deep links, and blind rank-1 product picking.
- **Change**: Switched to clean branch `clean-slate-v5`; established isolated workspace directory `D:\Grocer-v5/`; seeded the 6 core project memory documents (`PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `AGENTS.md`, `TASKS.md`, `JOURNAL.md`) and 6 authoritative ADRs (0001 through 0006) capturing all human decisions from our grilling session.
- **Proof**: Git status confirms branch `clean-slate-v5` active; all 6 core documentation files verified in `D:\Grocer-v5/`; complete roadmap established in `TASKS.md`.
- **Still broken**: None. Ready for Phase 0 (staging fixtures and mock elimination).

### [GROCER v5 — Swiggy Builder Club Documentation Download & Capability Audit] 2026-10-25

#### Work Card: Download Full Swiggy MCP Documentation and Audit Instamart Capabilities
- **Problem**: Need an authoritative local copy of Swiggy's official MCP specifications to verify whether all 10 PRD concierge features are natively supported without third-party mocks.
- **Change**: Downloaded `llms-full.txt` (566 KB) and `llms.txt` (31 KB) from Swiggy Builders Club into `docs/swiggy-mcp/`; audited all 20 Instamart MCP tools against the 10 PRD concierge requirements.
- **Proof**: Local files verified at `docs/swiggy-mcp/llms-full.txt` (566,116 bytes); confirmed 100% native MCP coverage for address management, orders, cart, coupons, bridge payments, and live GPS tracking.
- **Still broken**: None. Ready for user review of PRD alignment.

### [GROCER v5 — PRD Update to Full Instamart Concierge & Workspace Cleanup] 2026-10-25

#### Work Card: Expand PRD to Full Instamart Lifecycle, Delete Duplicate Handoff & Purge Old Paths
- **Problem**: PRD was limited to grocery list shopping; user requested full Instamart account management on WhatsApp (addresses, past orders, 20 tools), duplicate `.scratch/HANDOFF.md` existed, and an old path was present in `AGENTS.md`.
- **Change**: Updated `PRD.md` with full Instamart concierge scope and 20 native MCP tools; permanently deleted duplicate `.scratch/HANDOFF.md` (retaining single root `HANDOFF.md`); purged any old folder paths from `AGENTS.md`, `TASKS.md`, and `JOURNAL.md`.
- **Proof**: `PRD.md` updated at `D:\Grocer-v5\PRD.md`; single `HANDOFF.md` confirmed at root; zero occurrences of old paths remain in repo.
- **Still broken**: None. Ready for `ARCHITECTURE.md` review.

### [GROCER v1 — Project Version Reset to v1.0] 2026-10-25

#### Work Card: Reset Workspace Product Version from v5.0 to v1.0
- **Problem**: Project docs referenced legacy version numbering "v5.0" across headers and roadmaps; user requested clean product naming as Grocer v1.0.
- **Change**: Renamed all occurrences of "v5.0" / "Grocer v5" to "Grocer v1.0" in `PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `AGENTS.md`, `TASKS.md`, `JOURNAL.md`, and `HANDOFF.md`.
- **Proof**: Git diff confirms clean update across all markdown headers; scope verified in `AGENTS.md`.
- **Still broken**: None. Ready for architectural grilling round.

### [GROCER v1 — Domain Glossary Setup & ADR 0007 Instamart Lifecycle Guardrails] 2026-10-25

#### Work Card: Create Domain Glossary and Record ADR 0007 from Round 1 Grilling
- **Problem**: Expanding to full Instamart account lifecycle required formalizing domain terminology and capturing hard guardrails for address switching, split orders, deletion safety, and cancellations.
- **Change**: Created `GLOSSARY.md` defining canonical domain concepts (Customer, Dark Store, Basket, spinId, Bridge URL, Split Order); authored `docs/adr/0007-instamart-lifecycle-guardrails.md` recording all 4 settled Round 1 decisions; updated `HANDOFF.md`.
- **Proof**: `GLOSSARY.md` verified at repo root; ADR 0007 verified in `docs/adr/`; zero conflicting terminology.
- **Still broken**: None. Frontier advancing to Round 2.

### [GROCER v1 — ADR 0008 Pin Onboarding, Go-To Reordering & Bridge Payments] 2026-10-25

#### Work Card: Record ADR 0008 from Round 2 Grilling and Update Domain Glossary
- **Problem**: Need clear architectural decisions for converting WhatsApp GPS pins to complete addresses, 1-tap reordering UX, and avoiding wallet balance payment failures.
- **Change**: Authored `docs/adr/0008-pin-geocoding-reorder-and-bridge-payments.md` capturing Round 2 settled decisions; added `Go-To Items` and `Location Pin Onboarding` to `GLOSSARY.md`; updated `HANDOFF.md`.
- **Proof**: ADR 0008 verified in `docs/adr/`; `GLOSSARY.md` updated with canonical terms; `HANDOFF.md` synchronized.
- **Still broken**: None. PRD and decisions fully locked; ready for `ARCHITECTURE.md` review.

### [GROCER v1 — ADR 0001-0003 Clean-Slate Rewrite & Legacy Purge] 2026-10-25

#### Work Card: Purge Old Codebase Artifacts & Align ADR 1-3 with Official Swiggy MCP Docs
- **Problem**: ADR 0001 referenced old codebase files; ADR 0002 referenced float `.2f` formatting instead of integer paise; ADR 0003 claimed `upi://pay` and 15s polling conflicting with Meta CTA button rules and official Swiggy MCP long-poll specifications.
- **Change**: Rewrote ADR 0001, 0002, and 0003 to be 100% clean-slate Grocer v1.0 specifications; purged all dead file names; locked hashing and math to integer paise (`to_pay_paise`); locked payments to official Swiggy HTTPS `bridgeUrl` with 5-minute durable polling.
- **Proof**: Git diff confirms complete purge of legacy references; verified against Swiggy MCP documentation at `docs/swiggy-mcp/llms-full.txt`.
- **Still broken**: None. Ready for Grilling verification.

### [GROCER v1 — ADR 0009 Product Experience Guardrails & PRD Journeys 6-9] 2026-10-25

#### Work Card: Author ADR 0009 & Expand PRD with Human Experience Journeys
- **Problem**: Need explicit product guardrails for ordering to remote relatives, recipe checklists, post-order additions, and small-order delivery fee shock.
- **Change**: Authored `docs/adr/0009-product-experience-recipes-fees-and-destinations.md`; added `One-Time Destination Order`, `Recipe Checklist`, and `Small-Cart Fee Threshold` to `GLOSSARY.md`; expanded `PRD.md` with Journeys 6 through 9; updated `HANDOFF.md`.
- **Proof**: ADR 0009 verified in `docs/adr/`; `PRD.md` updated with Journeys 6-9; `GLOSSARY.md` synchronized.
- **Still broken**: None. Product exploration complete; ready for `ARCHITECTURE.md` review.

### [GROCER v1 — ADR 0001-0006 Full Product-First Alignment] 2026-10-25

#### Work Card: Rewrite All Early ADRs to Product-First Customer Contracts
- **Problem**: Earlier ADRs (1, 2, 3, 4, 6) were framed around internal technical architecture rather than first-principles product experience and customer trust.
- **Change**: Completely rewrote ADR 0001 (snappy button execution vs warm chat), ADR 0002 (radical price guarantee stopping checkout on price shifts), ADR 0003 (wallet champion coupon promise), ADR 0004 (smart Kirana defaults and physical tap safety), and ADR 0006 (family account safety cap and DPDP privacy).
- **Proof**: All 9 ADRs in `docs/adr/` verified clean-slate, free of legacy file references, and directly tied to human customer promises and official Swiggy MCP documentation.
- **Still broken**: None. PRD and all 9 ADRs 100% locked; ready for `ARCHITECTURE.md`.

### [GROCER v1 — ADR 0010 & Authoritative Clean-Slate ARCHITECTURE.md Sync] 2026-10-25

#### Work Card: Author ADR 0010 & Rebuild ARCHITECTURE.md as a Servant to the PRD
- **Problem**: Need explicit architecture specifications reflecting full Instamart on WhatsApp concierge lifecycle (20 tools, address management, JIT re-auth, session reset, zero-address onboarding).
- **Change**: Authored `docs/adr/0010-session-lifecycle-jit-auth-and-onboarding.md`; added canonical terms to `GLOSSARY.md`; completely rewrote `ARCHITECTURE.md` to cleanly separate Gemini conversational role from Python muscle/vault; synchronized `TASKS.md` and `HANDOFF.md`.
- **Proof**: `ARCHITECTURE.md` verified clean-slate v1.0 at `D:\Grocer-v5\ARCHITECTURE.md`; all 10 ADRs synchronized in `docs/adr/`; `git status` clean and verified.
- **Still broken**: None. Complete project memory locked and ready for Phase 0 review.

### [GROCER v1 — Remote Branch Initialization & GitHub Sync] 2026-10-25

#### Work Card: Create and Push `grocer-v1` Branch to GitHub Repository
- **Problem**: Project memory was local; needed a dedicated remote tracking branch on `https://github.com/kwakhare5/Grocer` to preserve all architectural contracts and ADRs.
- **Change**: Added remote `origin` pointing to `https://github.com/kwakhare5/Grocer.git`; created branch `grocer-v1`; committed `.gitignore`, `PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `GLOSSARY.md`, `TASKS.md`, `HANDOFF.md`, and all 10 ADRs; pushed cleanly to `origin/grocer-v1`.
- **Proof**: `git push -u origin grocer-v1` exited 0; branch tracked at `https://github.com/kwakhare5/Grocer/tree/grocer-v1`; working tree clean.
- **Still broken**: None. Ready for Phase 0 execution.

### [GROCER v1 — Environment Setup & Supabase Database Wipe] 2026-10-25

#### Work Card: Harvest Environment Credentials & Wipe Supabase Database Clean
- **Problem**: Need clean-slate runtime configuration and an empty database ready for Grocer v1.0 schemas, with zero legacy code or stale database tables.
- **Change**: Created `D:\Grocer-v5\.env` with harvested credentials (WhatsApp Cloud API, Supabase connection, Gemini key, AES token encryption key, Swiggy redirect URI); created tracked `.env.example`; ran automated wipe script dropping all 8 legacy tables and `grocer_internal` schema from Supabase PostgreSQL.
- **Proof**: `asyncpg` execution reported 0 remaining user tables; `.gitignore` verified ignoring `.env`; database confirmed 100% clean.
- **Still broken**: None. Ready for Phase 0 schema migration and fixture capture.

