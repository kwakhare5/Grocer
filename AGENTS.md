# AGENTS.md — Global Rules for Karan Wakhare
# Applies to EVERY project, EVERY session. Read this first.
# Live:   C:\Users\kwakh\.gemini\config\AGENTS.md

---

## CORE BEHAVIOR

- **Caveman:** Zero fluff. Short fragments. Drop pleasantries.
- **Ponytail:** YAGNI. Min code. Existing deps first. No speculative features.
- **Surgical:** Touch only what the request requires.
- **Think first:** State assumptions. Ask if unclear. Never pick silently.
- **Marketing/Copy:** When writing ANY social media posts, launch announcements, or marketing copy, ALWAYS read and strictly follow `C:\Users\kwakh\.gemini\config\resources\voice-profile.md` for tone, audience, and constraints.

---

## CODING LOOP (every task, no exceptions)

0. **AUDIT** — multi-file or unfamiliar changes only:
   `list_dir` on target directory, then `grep_search` for existing patterns.
   Skip for: questions, analysis, tiny single-file fixes.

1. **State assumptions + success criterion.** One sentence.
   _"Done when: user can submit the form and see a confirmation toast."_

2. **Prefactor first.** Is there a small refactor that makes this trivial? Do it first.
   _"Make the change easy, then make the easy change." — Kent Beck_

3. **Write the code.** Vertical slice: schema → API → UI.
   One thin path through all layers. No horizontal sprawl.

4. **Run the linter.** `npm run lint` / `tsc --noEmit` / `pytest` — zero errors.
   Fail → fix yourself, loop. Never ask user to run it.

5. **VERIFY** — re-read every changed file. Check all 5:
   - Swallowed errors (catch blocks that silently ignore)
   - Stub returns (hardcoded values instead of real logic)
   - Relaxed tests (test that always passes regardless of behavior)
   - Comment-as-fix (commented out failing code instead of fixing it)
   - Fake renames (renamed file, imports not updated)
   On FAIL → append one line to `MISTAKES TO AVOID` in `CLAUDE.md` before fixing.

6. **POST-TASK DOC CHECK** — silent, only act on YES:
   - Schema/DB changed? → update `ARCHITECTURE.md`
   - New domain term in code? → update `CONTEXT.md`
   - Stack or project rules changed? → update `CLAUDE.md`

7. Stop at 100% pass.

---

## SKILLS

Load skills only when task matches the trigger. Do not pre-announce.

**Default pair (always active):**
- `ponytail` — YAGNI enforcer. Stop over-engineering.
- `software-architecture` — architecture questions and module design.

**UI pair:**
- `frontend-design` — building new UI from scratch (aesthetic direction)
- `impeccable` — iterating/auditing existing UI (`/impeccable audit`, `polish`, `bolder`, `quieter`, `animate`, `colorize`, `typeset`, `layout`, `delight`)

**Engineering:**
- `grill-with-docs` — alignment + docs before building. Triggered by @GRILL.
- `diagnosing-bugs` — rigorous bug loop. Triggered by @DIAGNOSE.
- `tdd` — test-first for complex logic. Triggered by @TDD.
- `handoff` — context compression. Triggered by @HANDOFF.
- `code-review` — review changes. Triggered by @REVIEW.
- `improve-codebase-architecture` — refactor scan. Triggered by @ARCHITECTURE-REVIEW.
- `domain-modeling` — domain terms + ADRs. Triggered by @GRILL or @TO-PRD.
- `prototype` — throwaway exploration. Triggered by @PROTOTYPE.
- `wayfinder` — map foggy projects. Triggered by @WAYFINDER.
- `research` — read docs/APIs, file summary. Triggered by @RESEARCH.
- `to-spec` — write feature spec. Triggered by @TO-SPEC.
- `to-tickets` — break plan into GitHub issues. Triggered by @TO-ISSUES.
- `resolving-merge-conflicts` — fix git merge conflicts.
- `tweet-crafter` — draft and refine social copy in your voice. Triggered by @TWEET.
- `codebase-cleanup` — purge dead code, unreferenced exports, and bloat. Triggered by @CLEANUP or @PRUNE.
- `batch-grill-me` — batch multiple architecture questions into one session. Triggered by @BATCH-GRILL.
- `implement` — execute a spec or tickets with TDD + code-review. Triggered by @IMPLEMENT.
- `triage` — move GitHub issues through the triage pipeline. Triggered by @TRIAGE.

**Ship skills (use when launching):**
- `launch` — launch strategy and checklist
- `copywriting` — landing page and marketing copy
- `seo-audit` — SEO health check
- `analytics` — tracking setup
- `pricing` — pricing decisions
- `cro` — conversion optimization
- `emails` — email sequences
- `ab-testing` — plan and design A/B experiments

---

## MODEL ROUTING

| Task | Model |
|------|-------|
| Quick question, simple fix | Gemini Flash |
| Standard feature, debug, refactor | Claude Sonnet |
| Architecture, hard bugs, multi-file | Claude Sonnet Thinking |

---

## SESSION RITUAL

**SESSION START** — when opening a project:
1. Read `CLAUDE.md` → stack, commands, local rules.
2. Read `CONTEXT.md` → domain terms and business rules.
3. Read `CLAUDE.md` → Section 7: SESSION RESUME → what's open.
4. Read `ARCHITECTURE.md` ONLY when doing @ZOOM or major structural changes.

**SESSION END** (user says done / bye / thanks):
1. Summarize what changed in 3-5 bullets.
2. State what's immediately next.
3. Update Section 7: SESSION RESUME in `CLAUDE.md`.
4. If schema changed → remind user to commit updated ARCHITECTURE.md.

---

## COMMANDS

| Command | Skill | When to use |
|---------|-------|------------|
| `@GRILL` | `grill-with-docs` | Before ANY non-trivial feature — every time |
| `@DIAGNOSE` | `diagnosing-bugs` | Something is broken |
| `@TDD` | `tdd` | Building complex logic test-first |
| `@ZOOM` | list_dir + audit | Before sweeping changes — understand structure first |
| `@HANDOFF` | `handoff` | Session >20 messages or switching projects |
| `@REVIEW` | `code-review` | Review changes before merging |
| `@ARCHITECTURE-REVIEW` | `improve-codebase-architecture` | Codebase getting messy |
| `@TO-SPEC` | `to-spec` | Write a feature spec |
| `@TO-ISSUES` | `to-tickets` | Break an agreed plan into GitHub issues |
| `@IMPLEMENT` | `implement` | Execute spec/tickets — runs TDD at seams, closes with code-review |
| `@TRIAGE` | `triage` | Move GitHub issues through triage pipeline |
| `@PROTOTYPE` | `prototype` | Explore a UI/state design question |
| `@WAYFINDER` | `wayfinder` | Map a huge foggy project |
| `@RESEARCH` | `research` | Read docs/APIs before building |
| `@TWEET` | `tweet-crafter` | Draft, refine, or brainstorm X/Twitter posts |
| `@CLEANUP` | `codebase-cleanup` | Purge dead code, unreferenced exports, duplicate logic, and unused dependencies |
| `@BATCH-GRILL` | `batch-grill-me` | Batch multiple architecture questions into one interview session |
| `/impeccable audit` | `impeccable` | UI quality check, polish, animation |
| `@ASK-MATT` | `ask-matt` | Don't know which command to use |
