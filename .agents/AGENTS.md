# AGENTS.md — Global Rules for Karan Wakhare
# Applies to every project. Read first.

## 1. CORE BEHAVIOR
- **Caveman:** Zero fluff. Short fragments. No pleasantries.
- **Ponytail:** YAGNI. Minimum code. Prefer existing deps. No speculative features.
- **Surgical:** Touch only what the request requires.
- **Think first:** State assumptions. Ask if unclear. Never decide silently.
- **Graphify First:** If `graphify-out/graph.json` or `GRAPH_REPORT.md` exists in project root, MUST check `graphify-out/graph.json` or query `graphify` BEFORE doing raw file reads or greps.

## 2. SESSION RITUAL
### Session Start (automatic)
1. Read project `.agents/AGENTS.md` (stack, commands, local rules, SESSION RESUME).
2. Read project `CONTEXT.md` (domain terms/ADRs).
3. Print one-line summary: `📂 [Project] | Stack: [X] | Resuming: [last]`
4. Ask: "Ready. What are we working on?"

### Session End (conditional on significant changes)
1. Summarize what changed in 3–5 bullets.
2. Update Section 7: SESSION RESUME in `.agents/AGENTS.md`.
3. Prepend or merge a dated entry under ## Log Entries in `JOURNAL.md` (strictly ONE date heading `### [Project — Summary] YYYY-MM-DD` per calendar date, merging commit hashes, shipped bullets, and vibe).
4. Ask: "Session logged to JOURNAL.md. Draft X post now with /build-in-public?"

## 3. CODING LOOP (SIMPLIFIED MATT POCOCK WORKFLOW)

### Task Classification (Run FIRST, silently)
- **Tiny** (single file, <20 lines, no logic change): Skip loop. Just make the edit.
- **Standard / Complex** (multi-file OR new logic OR schema change): Run the full loop below.

### Full Loop
0. **AUDIT:** Detect stack/intent → auto-load specialist skill → print `✅ Loaded: [skill-name]`.
1. **GRILL & PLAN:** Run `/grill-with-docs` (Grill me). Ask clarifying questions, state assumptions, draft `implementation_plan.md`, and get explicit user approval.
2. **CHECKLIST:** Run `/to-tickets` to break the plan into a TODO checklist of tracer-bullet tasks in `task.md`.
3. **EXECUTE:** Run `/implement` to code each task. Write clean, surgical, vertical slices (schema → API → UI). Run tests & linters.
4. **REVIEW:** Run `/code-review` to verify specs and standards.
5. **COMMIT:** Run `/git-commit` to stage, analyze diffs, and generate conventional commits → stop for approval.
6. **DIAGNOSE:** If tests/build fails, stop coding → run `/diagnosing-bugs` (build a minimal failing test repro case first).

### Invariants & Conflicts
- **Docs:** Update `CONTEXT.md` for new domain terms. Update `ARCHITECTURE.md` or create ADR for schema/architectural changes.
- **Conflicts:** If a user request conflicts with a local rule in `.agents/AGENTS.md`, ask: `⚠️ This conflicts with local rule: [rule]. Override it? [yes/no]` before proceeding.

## 4. CORE COMMANDS REFERENCE
Invoke via `/command` or natural language. Skills are SKILL.md folders living in your agent's global skills folder. Discovery per tool (full map: playbook.md §5.1):
- Cross-tool standard: `~/.agents/skills/` (opencode, Claude Code, Freebuff all read it) — keep skills here
- Gemini CLI: `~/.gemini/config/skills/` and `~/.gemini/skills/`
- Project-local skills: `.agents/skills/`
Never hardcode one tool's path in rule files — keep this file tool-agnostic.
- `/grill` (`grill-with-docs`): Run requirements interview and plan.
- `/to-issues` (`to-tickets`): Generate `task.md` checklist.
- `/implement` (`implement`): Execute coding tasks.
- `/diagnose` (`diagnosing-bugs`): Debug and repro failing tests.
- `/review` (`code-review`): Standard and spec correctness check.
- `/git-commit` (`git-commit`): Conventional commit helper.
- `/design-review` (`design-review` / `impeccable`): UI/UX audit.

## 5. TASK → SKILL ROUTER (auto-load on AUDIT)

On AUDIT (step 0 of the loop), match the task against this table. Load the listed craft skill(s), print `✅ Loaded: [skill]`, and use them at every phase they apply to. Load **max 2-3 craft skills** — the table is a pick list, not a dump. No row matches → proceed without craft load (or suggest `/ask-matt`).

Process skills (Matt's: `grilling`, `to-spec`, `to-tickets`, `implement`, `tdd`, `code-review`, `diagnosing-bugs`) are NOT in this table — they run every time as the workflow itself.

| When the task is about… | Load (craft skills) | Applies to |
|---|---|---|
| Python code | `python-best-practices`, `python-testing-patterns` (+ `fastapi-best-practices` if FastAPI, `sqlalchemy-expert` if SQLAlchemy) | grill, implement, review |
| TypeScript / React / Next.js | `typescript-best-practices`, `nodejs-best-practices`, `nextjs-best-practices`, `vercel-react-best-practices` | grill, implement, review |
| UI design or polish | `impeccable`, `frontend-design`, `web-design-guidelines`, `tailwind-patterns` | grill, implement, review |
| Animations / motion | `emil-design-eng`, `animation-vocabulary`, `improve-animations` | audit, implement |
| Scraping / crawling | `scrapling-official`, `defuddle`, `apify-ultimate-scraper` | grill, implement |
| Tweets / content / marketing | `build-in-public`, `copywriting` (+ `emails`, `cro`, `launch`, `seo-audit` as needed) | grill, implement |
| Cleanup / refactor / dead code | `codebase-cleanup`, `ponytail`, `ponytail-review`, `production-code-audit` | audit, implement, review |
| Database / schema / migrations | `database-design`, `database-migrations-sql-migrations`, `postgres-best-practices`, `supabase` | grill, implement |
| Debugging / failing tests | `diagnosing-bugs`, `tdd` | implement |
| Writing tests | `tdd`, `python-testing-patterns` or `javascript-testing-patterns` | implement |
| Docs / README / writing | `doc-coauthoring`, `readme`, `writing-for-agents`, `pdf` / `docx` / `xlsx` | audit, implement |
| Deploy / infra / CI | `deploy-to-vercel` or `vercel-cli-with-tokens`, `docker-expert`, `terraform-specialist`, `github-actions-templates` | implement, review |
| Security | `web-security-testing`, `api-security-testing` | review |
| Performance | `web-perf`, `vercel-optimize` | review |

---

## 7. SESSION RESUME

**Last session date:** 2026-08-15

**What we built / changed:**
- Converted notification card to authentic Apple iOS 18 **Frosted Glass Material** (`bg-[#232326]/85 backdrop-blur-2xl backdrop-saturate-[180%] border border-white/20 shadow-[inset_0_1px_1px_0_rgba(255,255,255,0.45)]`) in `IosNotificationBanner.tsx`.
- Reorganized components into clean domain folders: `frontend/components/mockup/IosNotificationBanner.tsx` and `frontend/components/ui/IphoneFrame.tsx`.
- Purged unneeded temporary assets: `Generate React HTML CSS Code.zip` (396 KB) and `goldsand-830x6376.png` (229 KB).
- Purged legacy component files `FigmaNotificationCollapsed.tsx` and `ui/iphone.tsx`.
- Fixed ESLint unescaped entities in `GrocerFAQ.tsx` and `GrocerFooter.tsx`.
- Removed top kicker header badges (`"Interactive Prototype • 1-Tap Predictive WhatsApp Restock"` and `"Prophet ML Engine • LangGraph Agent"`) from `GrocerHero.tsx`.
- Equalized notification title and message copy font sizes to **`10.5px`** in `IosNotificationBanner.tsx`.
- Set `PhoneMockup` container width to **`295px`** in `PhoneMockup.tsx`.
- Added `-webkit-font-smoothing: antialiased`, `text-rendering: optimizeLegibility`, and GPU promotion (`transform: translateZ(0)`) across `IphoneFrame.tsx`, `PhoneMockup.tsx`, and `IosNotificationBanner.tsx`.
- Applied authentic Apple typography weights (`font-semibold` 600 for title, `font-normal` 400 for timestamp & body copy) in `IosNotificationBanner.tsx`.
- Aligned title and timestamp on the typographic baseline (`items-baseline`) in `IosNotificationBanner.tsx`.
- Reduced top and bottom vertical padding around notification text (`pt-[7px] pb-[20px]`) in `IosNotificationBanner.tsx` for a snug, compact card feel.
- Made `"now"` timestamp clearly visible in crisp `text-white/65` (`ml-2 shrink-0 whitespace-nowrap`) in `IosNotificationBanner.tsx`.
- Removed hover scale animation (`hover:scale-[1.01]`) so the notification stays completely static on mouse hover.
- Moved notification card position higher up on the lock screen (`pb-[95px] flex flex-col justify-end items-center`) in `PhoneMockup.tsx`.
- Reduced notification corner radius to `rounded-[22px]` (outer card & backdrops) and `rounded-[20px]` (glass fill) in `IosNotificationBanner.tsx`.
- Tightened icon-to-text horizontal gap to `gap-2` (8px) and app icon size to `w-[32px] h-[32px] rounded-[9px]`.
- Simplified Chat header to `WhatsApp` (with verified badge `✓`).
- Completely eliminated all background edge gaps by extending screen content (`left: 3.2%`, `top: 1.5%`, `width: 93.6%`, `height: 97.0%`, `borderRadius: 44px`) 3px under the black titanium bezel overlay (`/iphone-16-pro-frame.png` at `z-20`).
- Added Apple System Emoji styling (`-apple-system, BlinkMacSystemFont, "Apple Color Emoji"`) with Apple emojis across all WhatsApp messages & action buttons.
- Integrated official WhatsApp SVG brand icon (`WhatsAppIcon.tsx`) and exterior View Switcher (`[ 💬 WhatsApp Flow ]` / `[ 📊 Pantry Health ]`).
- Verified 16/16 Pytest tests passing (`1.60s`), ESLint `0 errors`, & Next.js production build (`0 errors / 0 warnings`).

**Immediate next task:**
[Deep codebase cleanup, unneeded asset & zip purge, iOS 18 Frosted Glass Material conversion (bg-[#232326]/85 backdrop-blur-2xl backdrop-saturate-[180%] specular highlight), IosNotificationBanner & IphoneFrame component reorganization, hero kicker badge purge, equalized 10.5px title & message font sizes, PhoneMockup container width 295px, subpixel vector font smoothing (-webkit-font-smoothing: antialiased, translateZ(0)), Apple font-semibold title & font-normal timestamp weights, typographic baseline alignment, tightened top/bottom vertical padding, crisp timestamp visibility, hover scale animation removal, notification position raised, reduced 22px corner radius, 8px icon spacing, old notification code purge, iPhone mockup alignment to active image assets (iphone-16-pro-frame.png, wallpaper.png), official Apple SF Pro OTF font integration, header name simplification, edge gap fixes, Apple emoji & build verification complete! Ready for GitHub publish or build-in-public posts!]

**Open blockers:**
[None]










