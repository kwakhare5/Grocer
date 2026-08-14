# Product Journal

A chronological record of project milestones, features shipped, and metrics. This file is append-only.

---

## How to Maintain This Journal (For the Agent)
During the Session End ritual (called automatically whenever significant changes are made), the agent:
1. Reads the current `JOURNAL.md`.
2. Formats all work under **at most ONE date heading per calendar day** (`### [Project — Summary] YYYY-MM-DD`).
3. If today's date heading (`YYYY-MM-DD`) already exists under `## Log Entries`, merges/appends the new bullet points under `- **Shipped**:`, updates `- **Commit**:`, and updates `- **Vibe**:`.
4. If today's date heading does NOT exist, prepends a new date heading `### [Project — Summary] YYYY-MM-DD` directly under `## Log Entries` (newest date on top).

---

## Log Entries

### [Project — Example Entry] 2026-08-12
- **Commit**: `a8f31b2`
- **Shipped**:
  - Completed Next.js Auth flow and created clean settings page.
  - Resolved SSR hydration mismatch by wrapping theme provider in client wrapper.
- **Hurdles**: Spent 3 hours fighting a hydration mismatch on SSR.
- **Metrics**: MRR: $0 | Users: 0 | Emails: 42
- **Visuals**: Screenshot of new responsive landing page hero section.
- **Ask/Roast**: Ask for feedback on whether a free trial or paid from day one is better for pre-launch.
- **Vibe**: 🔥 Very productive session!
