# Implementation Plan — Markdown Alignment & Codebase Cleanup

Synchronize all documentation files (`README.md`, `CONTEXT.md`, `ARCHITECTURE.md`, `.agents/AGENTS.md`) with our authoritative engineering specification [`PRODUCT_SPEC.md`](file:///d:/PreFill/PRODUCT_SPEC.md), delete outdated vendor pitch documents (`EXECUTIVE_PITCH.md`), and perform a complete codebase audit.

---

## User Review Required

> [!IMPORTANT]
> **Key Cleanup & Synchronization Actions:**
> 1. **Delete Outdated Vendor Pitch Doc:** We are explicitly deleting `EXECUTIVE_PITCH.md`. It contains old vendor sales deck claims ("Target Audience: Engineering Leadership at Blinkit/Zepto", "Kirana Leakage Moat") that contradict our refined `PRODUCT_SPEC.md` ("not a startup pitch, not an SDK for sale").
> 2. **Align All Markdown Documentation:** Update `README.md`, `CONTEXT.md`, `ARCHITECTURE.md`, and `.agents/AGENTS.md` to ensure zero stale sales pitch text exists anywhere in the repository.
> 3. **Validation & Verification:** Run backend unit tests (`pytest backend/tests/ -v`) and Next.js production build (`npm run build`) to guarantee 100% clean compilation.

---

## Proposed Changes

### Documentation Changes & Deletions

#### [DELETE] [`EXECUTIVE_PITCH.md`](file:///d:/PreFill/EXECUTIVE_PITCH.md)
- **Rationale:** Outdated B2B sales pitch deck replaced by the authoritative [`PRODUCT_SPEC.md`](file:///d:/PreFill/PRODUCT_SPEC.md).

---

#### [MODIFY] [`README.md`](file:///d:/PreFill/README.md)
- **Changes:** Ensure project description, real-world benchmarks (MilkBasket, Blinkit 1-tap reorder), system architecture diagram, and honest positioning are 100% in sync with `PRODUCT_SPEC.md`.

#### [MODIFY] [`CONTEXT.md`](file:///d:/PreFill/CONTEXT.md)
- **Changes:** Remove all legacy references to "76% Kirana Leakage" and "82% Retention Floor". Update domain glossary and feature descriptions to reflect cited industry benchmarks and mock dark store boundaries.

#### [MODIFY] [`ARCHITECTURE.md`](file:///d:/PreFill/ARCHITECTURE.md)
- **Changes:** Update Section 1 & Section 6 to reflect the 4-step ML + LangGraph replenishment pipeline, mocked dark store endpoints, and the low-risk Historical Backtest validation protocol.

#### [MODIFY] [`.agents/AGENTS.md`](file:///d:/PreFill/.agents/AGENTS.md)
- **Changes:** Verify Section 1 identity, local rules, and mistakes to avoid (no fake stats, no instant 2h dark store integration claims).

---

## Verification Plan

### Automated Build & Test Verification
1. **Pytest Backend Verification:**
   ```bash
   cd d:\PreFill
   .\venv\Scripts\python.exe -m pytest backend/tests/ -v
   ```
   *Pass criteria:* 16/16 unit & integration tests passing.

2. **Frontend Production Build:**
   ```bash
   cd d:\PreFill\frontend
   npm run build
   ```
   *Pass criteria:* Zero TypeScript errors, zero ESLint warnings.
