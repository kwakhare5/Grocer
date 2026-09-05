# AGENTS.md — Grocer Project Rules

---

## 1. PROJECT IDENTITY
- **Name:** Grocer
- **Goal:** Intelligent grocery inventory tracking, depletion forecasting, and automated WhatsApp alert assistant prototype.
- **Status:** Complete & Self-Contained Next.js Application
- **Repo:** https://github.com/kwakhare5/Grocer

---

## 2. TECH STACK
- **Framework:** Next.js 16 (Turbopack) + React 19 + TypeScript 5
- **Styling & UI:** Tailwind CSS v4 + Framer Motion + Lucide React
- **Simulation Layer:** Pure TypeScript Depletion Math & 5-Node State Machine (`lib/simulationEngine.ts`)
- **Linting & Code Quality:** ESLint 9

---

## 3. DEV COMMANDS
```bash
npm run dev      # Start Next.js development server on port 3000
npm run build    # Build optimized production bundle
npm run lint     # Run ESLint validation
```

---

## 4. LOCAL RULES & DESIGN INVARIANTS
1. **Zero AI Slop:** Direction 1 Swiss Logistics typography (`PP Mori` primary sans, `Geist Mono` tabular telemetry, and strictly upright `PP Editorial New` editorial accents), crisp Lucide icons, no emojis in buttons.
2. **Single-Source of Truth:** All catalog and customer persona definitions live in `lib/mockData.ts`.
3. **Passing Builds:** Always ensure `npm run build` passes with zero errors and zero type regressions.

---

## 5. EXTERNAL DOCS — SWIGGY BUILDERS CLUB
This project integrates Swiggy MCP servers. Before writing Swiggy code, fetch the authoritative docs:
- Index: https://mcp.swiggy.com/builders/llms.txt
- Full text: https://mcp.swiggy.com/builders/llms-full.txt
- Per-page: append `.md` to any https://mcp.swiggy.com/builders/docs/... URL

Use `/docs/reference/{food,instamart,dineout}` for tool schemas and `/docs/operate/errors` for the canonical error taxonomy. Do not invent tool names or parameters.

---

## 6. SESSION RESUME
- **Current State:** Phase 8 Customer Replenishment Workflow & Swiggy MCP Commerce Integration Complete & 100% Verified.
  - **Decoupled Architecture:** Clean `CommercePort` abstraction separating customer-facing grocery reorders from simulated dark-store replenishment.
  - **Dual Adapters:** `MockCommerceAdapter` (deterministic Mumbai dark-store simulation with authentic pricing, fee rules, spinIds, and delivery tracking) and `SwiggyMCPAdapter` (official Swiggy Instamart MCP protocol client with token security and canonical error mapping).
  - **Consequential Action Guard:** Spec §28.3 & §39.15 safety invariant enforced at all layers (domain exceptions, mock adapter, Swiggy adapter, service layer, FastAPI endpoint, and Next.js modal UI) requiring explicit human authorization (`explicit_confirmation: true`) before checkout execution.
  - **Frontend Integration:** Live Commerce Adapter badge (`Simulated Instamart` / `Swiggy MCP Live`), interactive Instamart cart with itemized bill breakdown, Go-To staple quick-add, consequential checkout authorization modal, and real-time express delivery tracking (`Ramesh Kamble`, ETA in mins, live GPS status).
  - **Code Quality & Build:** 281/281 backend pytest tests passing across all phases (Phases 1–8). Frontend `npm run lint` passes (0 errors, 0 warnings); `npm run build` passes in 5.7s. Code graph updated (2,094 nodes, 4,778 edges).
- **Immediate next task:** Production Polish & Swiggy MCP Live Connection Sandbox Testing.
- **Open blockers:** None.
