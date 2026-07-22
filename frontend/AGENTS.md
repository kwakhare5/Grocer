# AGENTS.md — Global AI Rules (Karan Wakhare)
# Applies to EVERY project, EVERY session. Read this first.

---

## CORE BEHAVIOR

- **Caveman:** Zero fluff. Short fragments. Drop pleasantries.
- **Ponytail:** YAGNI. Min code. Existing deps first. No speculative features.
- **Surgical:** Touch only what the request requires.
- **Think first:** State assumptions. Ask if unclear. Never pick silently.

---

## CODING LOOP (every task, no exceptions)

0. **AUDIT** — multi-file or unfamiliar changes only:
   `list_dir` on target directory, then `grep_search` for existing patterns.
   Skip for: questions, analysis, planning, tiny single-file fixes.

1. **State assumptions + success criterion.** One sentence: what does DONE look like?
   Be concrete. _"Done when: user can submit form and see confirmation toast."_

2. **Prefactor first:** Before adding a feature, ask — is there a small refactor
   that makes this feature trivial? Do that first.
   _"Make the change easy, then make the easy change." — Kent Beck_

3. **Write the code.** Vertical slice: schema → API → UI → test.
   One thin path through all layers. No horizontal sprawl.

4. **Run the linter:** `npm run lint` / `tsc --noEmit` / `pytest` — zero errors.
   Done when command exits 0. Fail → fix yourself, loop. Never ask user.

5. **VERIFY** — re-read every changed file. Check all 5:
   - Swallowed errors (catch blocks that silently ignore)
   - Stub returns (hardcoded values instead of real logic)
   - Relaxed tests (test that always passes regardless of behavior)
   - Comment-as-fix (commented out failing code instead of fixing it)
   - Fake renames (renamed file, imports not updated)
   On FAIL: append one line to `MISTAKES TO AVOID` in `CLAUDE.md` before fixing.

6. **POST-TASK DOC CHECK** — silent, only act on YES:
   - Schema/DB changed? → update `ARCHITECTURE.md`
   - New domain term in code? → update `CONTEXT.md`
   - Stack or project rules changed? → update `CLAUDE.md`
   - New skill added, renamed, or deleted? → update `AGENTS.md` commands table
   - New @command or /slash command added? → update `AGENTS.md` commands table
   - Project status changed (shipped, blocked, nuked)? → update `active_project_context.md`
   - Significant session (new system, major feature)? → append to `wiki/log.md` + update `wiki/hot.md`
   If YES to any → do it before ending. If NO to all → say nothing.

7. Stop at 100% pass.

---

## SKILLS

Load skills only when the task matches the skill's trigger. Do not pre-announce skills loaded.

---

## CONFLICT RESOLUTION

- **Loop Precedence:** If a specialized skill like `tdd` or `diagnosing-bugs` is active, follow its loop INSTEAD of steps 3-5 above.
- **Scope of Laziness:** Ponytail (YAGNI/min code) applies to feature scope. `codebase-design` applies to architecture scope.
- **Communication vs. Documentation:** Caveman (zero fluff) applies to chat only. Write documentation and `CONTEXT.md` updates with full articulation.

---

## COMMANDS
_User triggers these explicitly. AI does not suggest them unprompted._

| Command | When to use | Skill Loaded |
|---------|------------|--------------|
| `@ASK-MATT` | Don't know which command/skill to use? Ask the router. | `ask-matt` |
| `@GRILL` | Stress-test a code project plan and build a domain model. | `grill-with-docs` |
| `@GRILL-ME` | Interview me about a non-code plan or design. | `grill-me` |
| `@TO-ISSUES` | Break an agreed-upon plan/spec into tracer-bullet tickets (supports local files, GitHub, Linear). | `to-tickets` |
| `@TO-SPEC` | Turn our conversation into a spec and publish it. | `to-spec` |
| `@TDD` | Red-Green-Refactor to build a feature or fix a bug. | `tdd` |
| `@DIAGNOSE` | Something broken — rigorous bug diagnosis loop. | `diagnosing-bugs` |
| `@ARCHITECTURE-REVIEW` | Scan codebase for deepening opportunities (refactoring). | `improve-codebase-architecture` |
| `@PROTOTYPE` | Throwaway project to answer a UI/state design question. | `prototype` |
| `@HANDOFF` | Compact a long conversation context so a fresh session can pick it up. | `handoff` |
| `@TEACH` | Teach me a new skill or concept statefully over multiple sessions. | `teach` |
| `@TRIAGE` | Move issues through a state machine of triage roles. | `triage` |
| `@SETUP-POCOCK` | Configure issue tracker and triage labels for the current repo. | `setup-matt-pocock-skills` |
| `@SKILL-WRITE` | Reference for writing and editing skills well. | `writing-great-skills` |
| `@SHIP` | Deploy checklist → Vercel → README → tweet | N/A |
| `@ZOOM` | Map codebase before sweeping changes | N/A |
| `@AUDIT` | Scan for dead code, over-engineering | N/A |
| `@WAYFINDER` | Map a huge foggy project as investigation tickets, one decision at a time. | `wayfinder` |
| `@LOOP-ME` | Design automated workflow specs for recurring patterns in your life. | `loop-me` |
| `@WIZARD` | Build an interactive bash script that walks through a manual setup procedure. | `wizard` |
| `@RESEARCH` | Send a background agent to read docs/APIs and file a cited summary. | `research` |
| `@TWEET` | Generate 3 ready-to-post tweets in your voice from current context. | `tweet` |
| `/save` | Save current conversation as a wiki note to vault | `obsidian-vault` |
| `/autoresearch [topic]` | Research loop: search → fetch → synthesize → file in vault | `obsidian-vault` |
| `/canvas` | Create a visual Obsidian canvas from notes | `json-canvas` |

---

## MODEL ROUTING

| Task | Model |
|------|-------|
| Quick fix, simple component | Gemini Flash |
| Standard feature, debug, refactor | Claude Sonnet |
| Architecture, hard bugs, multi-file | Claude Sonnet Thinking / Opus |

---

## LOCAL CONTEXT SYSTEM

Context: `CLAUDE.md` (tech stack) and Obsidian RAG (architecture and state)

**SESSION START** — only if task involves this project's codebase:
1. Read `CLAUDE.md` → tech stack context.
2. Read `CONTEXT.md` → domain terms and ubiquitous language.
3. Read `00_System/active_project_context.md` via Obsidian MCP.

**SAVE WHEN:** code written, decision made, bug fixed, feature dropped, schema changed.
**HOW TO SAVE:** Append atomic facts to `wiki/log.md` at `D:\workflow-main\02_Obsidian_Brain\wiki\log.md` using Obsidian MCP or filesystem write.

**SESSION END** (done/bye/thanks):
1. Append a State Handoff note to `D:\workflow-main\02_Obsidian_Brain\wiki\log.md`.

---

## BOOTSTRAP NEW PROJECT

```powershell
$t="C:\Users\kwakh\.gemini\config\templates"; $d="D:\YourProject"
@("AGENTS.md","CLAUDE.md","ARCHITECTURE.md","CONTEXT.md",".editorconfig",".prettierrc.json") | %{ Copy-Item "$t\$_" "$d\$_" }
```

# AI fills CLAUDE.md and CONTEXT.md — tell it: "bootstrap this project, ask me what you need"
# AI registers project in active_project_context.md automatically
# Keep CLAUDE.md under 200 lines. Schema/decisions go in ARCHITECTURE.md only.
