# Tracer Bullets: Codebase Cleanup, Architecture Refactoring & Bloat Purge

- [x] 1. Purge legacy marketing landing page folder `components/grocer/` (6 files) and obsolete hook `hooks/usePantryEngine.ts` <!-- id: 1 -->
- [x] 2. Colocate WhatsApp simulation helper logic into `hooks/usePhoneDemoEngine.ts` and remove non-authoritative `lib/simulationEngine.ts` <!-- id: 2 -->
- [x] 3. Relocate `components/PhoneMockup.tsx` to `components/customer/PhoneMockup.tsx` for proper domain colocation <!-- id: 3 -->
- [x] 4. Streamline `components/customer/CustomerReplenishmentView.tsx`: eliminate bloated `storyboard` and `showcase` modes, focusing on the 3-column interactive Workbench <!-- id: 4 -->
- [x] 5. Refactor `components/navigation/AppGlobalHeader.tsx` and `app/page.tsx` for direct dual-workflow navigation (`operations` & `customer`) <!-- id: 5 -->
- [x] 6. End-to-end verification: execute `npm run lint`, `npm run build`, and `pytest backend/tests` (281 tests) ensuring 0 errors/regressions <!-- id: 6 -->
- [x] 7. Update codebase knowledge graph with `python -m graphify update .` <!-- id: 7 -->

## Remaining Phases Completion (Phases 8 & 10)
- [x] 8. Construct comprehensive Phase 10 test suite (`backend/tests/test_phase10_demo_hardening.py`) verifying primary/secondary demo narratives & invariants <!-- id: 8 -->
- [x] 9. Polish Phase 8 Operations UI & verify live backend sync in `components/operations/OperationsDashboard.tsx` and `lib/apiClient.ts` <!-- id: 9 -->
- [x] 10. Run complete test suites (`pytest backend/tests`, `npm run lint`, `npm run build`) <!-- id: 10 -->
- [x] 11. Update documentation everywhere (`GROCER_V2_MASTER_SPEC.md`, `README.md`, `.agents/AGENTS.md`, `JOURNAL.md`) <!-- id: 11 -->
- [x] 12. Rebuild codebase knowledge graph with `python -m graphify update .` <!-- id: 12 -->








