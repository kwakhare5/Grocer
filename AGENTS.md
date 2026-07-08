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

0. **AUDIT** (mandatory before touching ANY file):
   `list_dir` on target directory → `grep_search` for existing patterns →
   print `[AUDIT: found X files, pattern Y exists]`.
   Done when you can name every file you will touch. No exceptions.

1. **State assumptions + success criterion.** One sentence: what does DONE look like for this specific task? Be concrete. _"Done when: user can submit form and see confirmation toast."_

2. **Prefactor first:** Before adding a feature, ask — is there a small refactor
   that makes this feature trivial? Do that first.
   _"Make the change easy, then make the easy change." — Kent Beck_

3. **Write the code.** Vertical slice: schema → API → UI → test.
   One thin path through all layers. No horizontal sprawl.

4. **Run the linter:** `npm run lint` / `tsc --noEmit` / `pytest` — zero errors.
   Done when command exits 0. Fail → fix yourself, loop. Never ask user.

5. **VERIFY** — re-read every changed file. Explicitly check all 5:
   - Swallowed errors (catch blocks that silently ignore)
   - Stub returns (hardcoded values instead of real logic)
   - Relaxed tests (test that always passes regardless of behavior)
   - Comment-as-fix (commented out failing code instead of fixing it)
   - Fake renames (renamed file, imports not updated)
   Print: `[VERIFY: PASS]` or `[VERIFY: FAIL — reason]`. Never skip.
   On FAIL: append one line to `MISTAKES TO AVOID` in `CLAUDE.md` before fixing.

6. **TEACH LOOP** (significant features only):
   Print `[TEACH LOOP]` block explaining what was built and why in plain English.
   Save to brain project file.

7. Stop at 100% pass.

---

## SKILLS

Path: `C:\Users\kwakh\.gemini\config\skills\`
Load 2-3 matching skills per task. Begin every response: `[SKILLS ACTIVE: x, y]`

---

## COMMANDS
_User triggers these explicitly. AI does not suggest them unprompted._

| Command | When to use |
|---------|------------|
| `@HELP` | Don't know which command to use |
| `@SPEC` | Before building anything new — interview → spec.md |
| `@IMPLEMENT` | Have a spec.md, ready to build — TDD → commit |
| `@TDD` | Red-Green-Refactor. One test at a time. |
| `@GRILL` | Stress-test a plan before touching code |
| `@DIAGNOSE` | Something broken — feedback loop → hypotheses → fix |
| `@ZOOM` | Map codebase before sweeping changes |
| `@AUDIT` | Scan for dead code, over-engineering |
| `@PROTOTYPE` | Throwaway to answer a design question |
| `@TO-ISSUES` | Break feature into tracer-bullet tasks |
| `@TO-PRD` | Turn conversation into a PRD |
| `@SHIP` | Deploy checklist → Vercel → README → tweet |
| `@HANDOFF` | Compact long context → fresh session picks up |
| `@BRAIN-AUDIT` | Check brain files for stale/wrong entries |
| `@BRAIN-FIX "X"` | Find X in brain → fix or delete → confirm |

---

## MODEL ROUTING

| Task | Model |
|------|-------|
| Quick fix, simple component | Gemini Flash |
| Standard feature, debug, refactor | Claude Sonnet |
| Architecture, hard bugs, multi-file | Claude Sonnet Thinking / Opus |

---

## SECOND BRAIN

Brain: `D:\workflow-main\Obsidian brain\` | MCP: `obsidian-vault`

**SESSION START:**
1. `obsidian_get_file_contents("CLAUDE.md")` → read profile
2. `obsidian_get_file_contents("Projects/X.md")` → read project brain
3. Print: `[🧠 BRAIN READ] CLAUDE.md + Projects/X.md → last: Y`
4. MCP fail → `[🧠 BRAIN OFFLINE]`, continue

**SAVE WHEN:** code written · decision made · bug fixed · feature dropped · schema changed · dep changed
**DON'T SAVE:** explained something · answered a question · trivial fix

**SESSION END (done/bye/thanks):**
1. `obsidian_patch_content("Projects/X.md")` → overwrite CURRENT STATE
2. Print: `[🧠 BRAIN UPDATED] → X decisions, next: Y`

---

## BOOTSTRAP NEW PROJECT

```powershell
$t="D:\workflow-main\templates"; $d="D:\YourProject"
@("AGENTS.md","CLAUDE.md","ARCHITECTURE.md",".editorconfig",".prettierrc.json") | %{ Copy-Item "$t\$_" "$d\$_" }

# Fill CLAUDE.md using: D:\workflow-main\resources\claude-ai-project-start-prompt.md
# Keep CLAUDE.md under 200 lines. Schema/decisions go in ARCHITECTURE.md only.
```

**New brain file:** Copy `D:\workflow-main\Obsidian brain\Projects\_TEMPLATE.md` → rename to project name.
