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
- **Current State:** Phase 6 LangGraph Execution Agent Complete & 100% Verified.
  - **Pipeline Hardened:** Full end-to-end autonomous chain implemented (Phase 1 Authority → Phase 2 Simulator → Phase 3 Forecasting → Phase 4 Risk → Phase 5 Decision → Phase 6 LangGraph Execution).
  - **Batch-Aware Mutations:** FIFO deduction across inter-store transfers with matching destination batch creation and shelf-life aware supplier PO batches.
  - **State Machine & Invariants:** 5-node LangGraph execution flow (`validate -> execute -> verify -> finalize/recover`) with strict DB invariant assertions and Level-2 human-in-the-loop authorization enforcement.
  - **Failure Recovery:** Programmatic rollback and alternative generation triggering `recalculate_options` upon stale inventory or network simulation errors.
  - **Code Quality & Build:** 75/75 backend pytest tests passing across Phases 1–6. Frontend `npm run lint` passes (0 errors, 0 warnings); `npm run build` passes in 5.2s. Code graph updated (1,885 nodes, 4,158 edges).
- **Immediate next task:** Phase 7 — Operations Frontend Integration (Interactive execution controls, live agent run inspector, and decision stream UI).
- **Open blockers:** None.
