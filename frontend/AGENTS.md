# AGENTS.md — Global Rules for Karan Wakhare
# Applies to EVERY project, EVERY session. Read this first.
# Live Config Root: C:\Users\kwakh\.gemini\config\
# Skills Directory: C:\Users\kwakh\.gemini\config\skills\

---

## 1. CORE BEHAVIOR

- **Caveman:** Zero fluff. Short fragments. Drop pleasantries.
- **Ponytail:** YAGNI. Min code. Existing deps first. No speculative features.
- **Surgical:** Touch only what the request requires.
- **Think first:** State assumptions. Ask if unclear. Never pick silently.
- **Marketing/Copy:** When writing marketing copy or tweets, strictly follow `C:\Users\kwakh\.gemini\config\resources\voice-profile.md`.

---

## 2. SESSION RITUAL

**SESSION START (When opening a project)**
1. Read `CLAUDE.md` → stack, commands, local rules.
2. Read `CONTEXT.md` → domain terms and business rules.
3. Read `CLAUDE.md` Section 7: SESSION RESUME → what's open.
4. Read `ARCHITECTURE.md` ONLY when doing `/zoom` or structural changes.

**SESSION END (User says done / bye)**
1. Summarize what changed in 3-5 bullets.
2. State what's immediately next.
3. Update Section 7: SESSION RESUME in `CLAUDE.md`.

---

## 3. CODING LOOP (Every Task, No Exceptions)

0. **AUDIT:** `list_dir` on target directory, then `grep_search` for existing patterns. Skip for tiny single-file fixes.
1. **ASSUME:** State assumptions + success criterion. One sentence.
2. **PREFACTOR:** Make the change easy, then make the easy change.
3. **CODE:** Vertical slice (schema → API → UI). No horizontal sprawl.
4. **LINT:** `npm run lint` / `fastapi dev` — zero errors. Fix yourself.
5. **VERIFY:** Re-read every changed file. Check for swallowed errors, stub returns, relaxed tests, comment-as-fix, fake renames. On fail → update `CLAUDE.md` MISTAKES TO AVOID.
6. **DOCS:** Schema changed? → update `ARCHITECTURE.md`. New domain term? → update `CONTEXT.md`.
7. **STOP:** Stop at 100% pass.

---

## 4. SKILL TIERS — How Skills Work

### Tier 1 — Passive (AI auto-loads, you NEVER type anything)
The AI reads these automatically the moment it detects the relevant context.
You do NOT invoke these. They are invisible rules, not commands.

| Skill | Auto-loads when... |
| :--- | :--- |
| `react-best-practices` | Writing React components |
| `nextjs-best-practices` | Working in Next.js app/pages |
| `tailwind-v4-shadcn` | Writing Tailwind classes or shadcn setup |
| `drizzle-orm-expert` | Writing Drizzle schema or queries |
| `prisma-expert` | Writing Prisma schema or queries |
| `sqlalchemy-expert` | Writing Python DB queries |
| `supabase` | Working with Supabase auth/DB/storage |
| `stripe-integration` | Writing Stripe payment code |
| `auth-implementation-patterns` | Building any auth flow |
| `postgres-best-practices` | Writing SQL or DB schema |
| `fastapi-best-practices` | Writing Python/FastAPI routes |
| `zustand-store-ts` | Writing Zustand state management |
| `vercel-composition-patterns` | Composing complex React components |
| `software-architecture` | Making architectural or module decisions |
| `performance-optimizer` | Asked to optimize speed or reduce cost |
| `frontend-design` | Designing a new page or UI from scratch |
| `apple-design` | Building gesture-driven or premium UI |
| `ponytail` | User says "simplest", "lazy", "yagni" |
| `codebase-design` | Designing module interfaces or APIs |
| `domain-modeling` | Pinning down domain terms or ADRs |

### Tier 2 — Commands (You explicitly invoke with `/`)
Big, deliberate actions you consciously trigger. AI does NOT auto-load these.

---

## 5. COMMAND REFERENCE

*Note: The actual skill execution files live in `C:\Users\kwakh\.gemini\config\skills\`*

| Command | Skill | When to use |
| :--- | :--- | :--- |
| `/office-hours` | `office-hours` | Adversarial YC feedback before a major pivot |
| `/grill` | `grill-with-docs` | Before ANY non-trivial feature — every time |
| `/to-spec` | `to-spec` | Write a feature spec |
| `/to-issues` | `to-tickets` | Break an agreed plan into GitHub issues |
| `/zoom` | list_dir + audit | Before sweeping structural changes |
| `/wayfinder` | `wayfinder` | Map a huge foggy project |
| `/tdd` | `tdd` | Building complex logic test-first |
| `/implement` | `implement` | Execute spec/tickets slice-by-slice |
| `/diagnose` | `diagnosing-bugs` | Something is broken, throwing, or slow |
| `/review` | `code-review` | Review code changes against spec |
| `/design-review` | `design-review` | Review UI/UX design decisions (GStack) |
| `/qa` | `qa` | Run automated Playwright browser tests |
| `/careful` | `careful` | Lock down folders from AI modification |
| `/cleanup` | `codebase-cleanup` | Purge dead code, unreferenced exports, bloat |
| `/impeccable audit` | `impeccable` | Full UI quality check (typography, layout) |
| `/emil-design-eng` | `emil-design-eng` | Apple-tier interaction and motion consulting |
| `/prototype` | `prototype` | Throwaway UI exploration |
| `/ship` | `ship` | Fast PR creation and deployments |
| `/retro` | `retro` | Structured project retrospective |
| `/investigate` | `investigate` | Deep investigation/research on a topic |
| `/canary` | `canary` | Deploy and monitor for errors |
| `/scrapling-official` | `scrapling-official` | Heavy web scraping and data extraction |
| `/tweet-crafter` | `tweet-crafter` | Draft, refine, or brainstorm X/Twitter posts |
| `/handoff` | `handoff` | Compress session context when > 20 messages |
| `/pick-ui-library` | `pick-ui-library` | Decide which UI component library to use |
| `/ponytail-audit` | `ponytail-audit` | Audit whole codebase for over-engineering |

---

## 6. MODEL ROUTING

| Task | Model |
| :--- | :--- |
| Quick question, simple fix | Gemini Flash |
| Standard feature, debug, refactor | Claude Sonnet |
| Architecture, hard bugs, multi-file | Claude Sonnet Thinking |
