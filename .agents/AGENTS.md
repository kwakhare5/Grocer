# AGENTS.md — Project Rules

# Hard cap: 120 lines. Fill Sections 1-4 at project start.

# AI fills Sections 5-7 automatically during development.

#

# RULES:

# - Global AI rules → auto-loaded by your tool: Freebuff ~/.AGENTS.md · opencode ~/.config/opencode/AGENTS.md · Gemini/antiGravity ~/.gemini/GEMINI.md

# - Domain terms → CONTEXT.md (read every session)

# - Product diary → JOURNAL.md (1 date heading per calendar date, merging session entries)

# - Heavy architecture → ARCHITECTURE.md (load on-demand)

# - Playbook → ~/.agents/playbook.md (Gemini/antiGravity: ~/.gemini/config/playbook.md) — full map in playbook.md §5.1

# - Session end: Ask "Session logged to JOURNAL.md. Draft X post now with /build-in-public?"

---

## 1. PROJECT IDENTITY

**Name:** [Insert Project Name]
**Goal:** [Insert one-sentence goal]
**Status:** In Progress
**Repo:** [GitHub URL]

---

## 2. TECH STACK

- **Frontend:** [e.g. Next.js 15, React 19, Tailwind v4]
- **Backend:** [e.g. FastAPI / Next.js Server Actions]
- **Database:** [e.g. PostgreSQL via Supabase + Drizzle ORM]
- **Auth:** [e.g. Supabase Auth / Clerk]
- **Payments:** [e.g. Stripe]
- **UI Library:** [Run /pick-ui-library to decide — e.g. shadcn/ui, Radix, Ark UI]
- **Language:** [e.g. TypeScript strict + Python strict typing]

---

## 3. DEV COMMANDS

```bash
# Frontend
npm run dev        # start dev server
npm run build      # production build
npm run lint       # ESLint + TypeScript check

# Backend (if using FastAPI)
fastapi dev main.py # start FastAPI server
pytest              # run backend tests
```

_AI runs these automatically when validating changes._

---

## 4. ENGINEERING PRINCIPLES

These apply to every decision in this codebase:

- No backward compatibility. Remove obsolete paths instead of adding compatibility layers, fallbacks, or migrations.
- Simplest implementation that fully meets current requirements. No speculative abstractions, configuration, or indirection.
- Grow in layers. Start from the smallest version that works end to end. Never trade a working product for unfinished complexity.
- Keep components modular. Concerns clearly separated.
- Prefer established, well-maintained libraries when they reduce complexity or improve reliability. Do not reimplement common functionality without a clear reason.
- Lean on existing project dependencies before writing your own implementation or adding packages. Check documentation and types before assuming a library lacks a capability.
- Architectural decisions for the long term. No stopgaps that are "meant to be replaced later."

## 4b. LOCAL RULES

_Project-specific constraints that override generic advice. Add 3-5 max._

1. [e.g. All DB queries must go through /lib/db/ — never inline]
2. [e.g. No custom CSS files — use Tailwind utility classes only]
3. [e.g. All API endpoints require Pydantic validation]
4. [e.g. Always use ~/ path aliases in TypeScript — no ../../]

---

## 5. PROJECT PATTERNS

_AI fills this as the project grows._

### Shared components

<!-- AI appends here as components are built -->

### File structure

```
[AI fills this after /zoom]
```

---

## 6. MISTAKES TO AVOID

_AI appends here after every VERIFY failure. Never repeat these._

<!-- Format: [YYYY-MM-DD] What went wrong → What to do instead -->

---

## 7. SESSION RESUME

_AI fills at END of every session. Read at START of next session._

**Last session date:** [YYYY-MM-DD]

**What we built / changed:**

- [New session]

**Immediate next task:**
[What to pick up next]

**Open blockers:**
[None]

**Files most recently changed:**

- [None]
