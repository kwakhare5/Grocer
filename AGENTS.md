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

0. **AUDIT & SUB-AGENT DISPATCH:** `list_dir` on target directory, then `grep_search` for existing patterns.
   - **Stack & Skill Check:** Detect tech stack/domain (React, Next.js, Tailwind, FastAPI, Supabase, ORM, UI Design) and mandatorily load/apply designated `SKILL.md` rules.
   - **Dispatch Sub-Agents:** Match intent against the 7 Specialists (Scraper, Tweet Crafter, Code Reviewer, QA Tester, Debugger, Cleanup Auditor, Architect) and print a clean 2-line dispatch notice. Skip sub-agents for 1-file fixes.
1. **ASSUME:** State assumptions + success criterion. One sentence.
2. **PREFACTOR:** Make the change easy, then make the easy change.
3. **CODE:** Vertical slice (schema → API → UI) strictly adhering to skill rules. No horizontal sprawl.
4. **LINT:** `npm run lint` / `fastapi dev` — zero errors. Fix yourself.
5. **SUB-AGENT VERIFY & REVIEW:** Re-read changed files AND run **Code Reviewer** (`code-review`) and **QA Tester** (`qa`/`tdd`) sub-agents on non-trivial diffs. Check for swallowed errors, stub returns, relaxed tests. On fail → update `CLAUDE.md` MISTAKES TO AVOID.
6. **DOCS:** Schema changed? → update `ARCHITECTURE.md`. New domain term? → update `CONTEXT.md`.
7. **STOP:** Stop at 100% pass.

---

## 4. SKILL TIERS & AUTOMATIC ORCHESTRATION

### Tier 1 — Passive (MANDATORY Stack Skills — AI Auto-Loads & Enforces Always)

The AI MUST read and strictly follow these skill rules BEFORE generating code or UI designs whenever the relevant stack or context is present. Zero skipping.

| Skill                          | Auto-loads & Enforces when...            |
| :----------------------------- | :--------------------------------------- |
| `react-best-practices`         | Writing React components                 |
| `nextjs-best-practices`        | Working in Next.js app/pages             |
| `tailwind-v4-shadcn`           | Writing Tailwind classes or shadcn setup |
| `drizzle-orm-expert`           | Writing Drizzle schema or queries        |
| `prisma-expert`                | Writing Prisma schema or queries         |
| `sqlalchemy-expert`            | Writing Python DB queries                |
| `supabase`                     | Working with Supabase auth/DB/storage    |
| `stripe-integration`           | Writing Stripe payment code              |
| `auth-implementation-patterns` | Building any auth flow                   |
| `postgres-best-practices`      | Writing SQL or DB schema                 |
| `fastapi-best-practices`       | Writing Python/FastAPI routes            |
| `zustand-store-ts`             | Writing Zustand state management         |
| `vercel-composition-patterns`  | Composing complex React components       |
| `software-architecture`        | Making architectural or module decisions |
| `performance-optimizer`        | Asked to optimize speed or reduce cost   |
| `frontend-design`              | Designing a new page or UI from scratch  |
| `apple-design`                 | Building gesture-driven or premium UI    |
| `ponytail`                     | User says "simplest", "lazy", "yagni"    |
| `codebase-design`              | Designing module interfaces or APIs      |
| `domain-modeling`              | Pinning down domain terms or ADRs        |

### Tier 2 — Task Skills & Commands (Dual Trigger: `/command` OR Natural Language Intent)

You can explicitly trigger these with `/command`, **OR** just state your goal in plain English. The AI will automatically detect your intent, load the relevant skill, and execute it!

| Trigger Phrase / Intent                            | Skill Loaded         | Command               |
| :------------------------------------------------- | :------------------- | :-------------------- |
| "Grill me on this", "interview me", "test my plan" | `grill-with-docs`    | `/grill`              |
| "Write spec for this", "make a spec"               | `to-spec`            | `/to-spec`            |
| "Break into issues", "make tickets"                | `to-tickets`         | `/to-issues`          |
| "Map this codebase", "wayfinder"                   | `wayfinder`          | `/wayfinder`          |
| "Build test-first", "write TDD tests"              | `tdd`                | `/tdd`                |
| "Implement this feature", "build slice"            | `implement`          | `/implement`          |
| "Debug this", "fix this bug", "diagnose"           | `diagnosing-bugs`    | `/diagnose`           |
| "Review this code", "check PR", "review diff"      | `code-review`        | `/review`             |
| "Review design", "check UI hierarchy"              | `design-review`      | `/design-review`      |
| "Run QA", "test UI in browser"                     | `qa`                 | `/qa`                 |
| "Clean up dead code", "prune bloat"                | `codebase-cleanup`   | `/cleanup`            |
| "Polish UI", "make it bolder/quieter"              | `impeccable`         | `/impeccable`         |
| "Ship PR", "deploy this"                           | `ship`               | `/ship`               |
| "Scrape this site", "extract data"                 | `scrapling-official` | `/scrapling-official` |

### 4.3 Autonomous Sub-Agent Specialist Engine (Strict Need-Based Dispatch)

The AI maintains 7 specialized sub-agent workers organized into a **3-Tier Priority Hierarchy**. **CRITICAL RULE:** The AI MUST ONLY spawn sub-agents that are strictly required by the user's prompt, task intent, or explicit keywords. Never spawn unneeded sub-agents.

**Dual-Trigger Versatility:** Sub-agents spawn seamlessly via **Natural Language Task Prompts** (e.g., *"check my code and run browser tests"*) **OR** explicit **`/commands`** (e.g., `/review`, `/qa`). You do NOT need to manually type slash commands to use sub-agents.

| Priority Tier | Specialist Sub-Agent | Primary Skill | Trigger Condition / Intent |
| :--- | :--- | :--- | :--- |
| **Tier A (Core Dev)** | **1. Code Reviewer** | `code-review` / `design-review` | Task involves non-trivial code edits requiring spec & standards review |
| **Tier A (Core Dev)** | **2. QA & Test Runner** | `qa` / `tdd` | Task includes running unit tests, TDD, or Playwright browser tests |
| **Tier A (Core Dev)** | **3. Debugger & Isolator** | `diagnosing-bugs` | Prompt asks to debug, fix an error, or isolate a performance regression |
| **Tier B (Structure)** | **4. Architecture Specialist** | `software-architecture` / `request-refactor-plan` | Task requires multi-module architectural refactoring or ADR planning |
| **Tier B (Structure)** | **5. Cleanup & Bloat Auditor** | `codebase-cleanup` / `ponytail-audit` | Prompt asks to prune dead code, audit exports, or simplify bloat |
| **Tier C (Utility)** | **6. Web Scraper** | `scrapling-official` | Prompt requests scraping, crawling, or pulling data from a URL |
| **Tier C (Utility)** | **7. Tweet Crafter** | `tweet-crafter` | Prompt asks to draft a tweet, post update, or build in public post |

#### Sub-Agent Dispatch Protocol:
1. **Analyze Intent:** Match prompt (natural language or `/command`) against the 7 Specialists. Select ONLY the sub-agents directly needed.
2. **Announce Dispatch:** Print a clean 2-line dispatch notice before execution:
   ```text
   🤖 Spawning Required Sub-Agents:
   - [Tier A: Code Reviewer] Dedicated task description
   - [Tier A: QA Tester] Dedicated task description
   ```
3. **Execute & Synthesize:** Launch background sub-agents concurrently, silently monitor logs, and report a unified summary when complete.
4. **Bypass for Tiny Edits:** Single-file fixes or quick Q&A execute directly in the main turn without spawning sub-agents.

---



## 5. COMMAND REFERENCE

_Note: The actual skill execution files live in `C:\Users\kwakh\.gemini\config\skills\`_

| Command               | Skill                | When to use                                  |
| :-------------------- | :------------------- | :------------------------------------------- |
| `/office-hours`       | `office-hours`       | Adversarial YC feedback before a major pivot |
| `/grill`              | `grill-with-docs`    | Before ANY non-trivial feature — every time  |
| `/to-spec`            | `to-spec`            | Write a feature spec                         |
| `/to-issues`          | `to-tickets`         | Break an agreed plan into GitHub issues      |
| `/zoom`               | list_dir + audit     | Before sweeping structural changes           |
| `/wayfinder`          | `wayfinder`          | Map a huge foggy project                     |
| `/tdd`                | `tdd`                | Building complex logic test-first            |
| `/implement`          | `implement`          | Execute spec/tickets slice-by-slice          |
| `/diagnose`           | `diagnosing-bugs`    | Something is broken, throwing, or slow       |
| `/review`             | `code-review`        | Review code changes against spec             |
| `/design-review`      | `design-review`      | Review UI/UX design decisions (GStack)       |
| `/qa`                 | `qa`                 | Run automated Playwright browser tests       |
| `/careful`            | `careful`            | Lock down folders from AI modification       |
| `/cleanup`            | `codebase-cleanup`   | Purge dead code, unreferenced exports, bloat |
| `/impeccable audit`   | `impeccable`         | Full UI quality check (typography, layout)   |
| `/emil-design-eng`    | `emil-design-eng`    | Apple-tier interaction and motion consulting |
| `/prototype`          | `prototype`          | Throwaway UI exploration                     |
| `/ship`               | `ship`               | Fast PR creation and deployments             |
| `/retro`              | `retro`              | Structured project retrospective             |
| `/canary`             | `canary`             | Deploy and monitor for errors                |
| `/scrapling-official` | `scrapling-official` | Heavy web scraping and data extraction       |
| `/tweet-crafter`      | `tweet-crafter`      | Draft, refine, or brainstorm X/Twitter posts |
| `/handoff`            | `handoff`            | Compress session context when > 20 messages  |
| `/pick-ui-library`    | `pick-ui-library`    | Decide which UI component library to use     |
| `/ponytail-audit`     | `ponytail-audit`     | Audit whole codebase for over-engineering    |

---

## 6. MODEL ROUTING

| Task                                | Model                  |
| :---------------------------------- | :--------------------- |
| Quick question, simple fix          | Gemini Flash           |
| Standard feature, debug, refactor   | Claude Sonnet          |
| Architecture, hard bugs, multi-file | Claude Sonnet Thinking |
