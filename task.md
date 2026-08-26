# Grocer Refactor & Cleanup Task Checklist

- [x] 1. Flatten directory structure (move `frontend/*` to project root) <!-- id: 1 -->
- [x] 2. Delete Python backend, SQLite databases, alembic, and dead config files <!-- id: 2 -->
- [x] 3. Create unified TypeScript simulation engine & mock data (`lib/simulationEngine.ts`, `lib/mockData.ts`, `lib/types.ts`) <!-- id: 3 -->
- [x] 4. Refactor `hooks/usePhoneDemoEngine.ts` and `components/PhoneMockup.tsx` to use the pure simulation engine <!-- id: 4 -->
- [x] 5. Refactor `GrocerIntegrations.tsx` to use realistic offline simulated responses <!-- id: 5 -->
- [x] 6. Purge dead files, stray images, and unused packages (`axios`, `swr`) <!-- id: 6 -->
- [x] 7. Update root `package.json` and install dependencies <!-- id: 7 -->
- [x] 8. Verify build (`npm run build` & `npm run lint`) <!-- id: 8 -->
- [x] 9. Update documentation (`README.md`, `ARCHITECTURE.md`, `CONTEXT.md`, `.agents/AGENTS.md`, `JOURNAL.md`) <!-- id: 9 -->
