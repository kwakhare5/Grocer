# Graph Report - Grocer  (2026-08-26)

## Corpus Check
- 44 files · ~274,504 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 257 nodes · 288 edges · 28 communities (21 shown, 7 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4202e435`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- GrocerValueProp.tsx
- IosNotificationBanner.tsx
- include
- compilerOptions
- devDependencies
- ARCHITECTURE.md — Product Strategy & System Architecture
- README.md
- dependencies
- usePhoneDemoEngine.ts
- package.json
- AGENTS.md — Grocer Project Rules
- Read at the START of EVERY session.
- GROCER — Engineering Prototype & Problem Exploration
- Component 3: Component-Wide Light Surface Transformation & Component Reuse
- .prettierrc.json
- page.tsx
- app/layout.tsx
- Changes Made
- Log Entries
- Grocer — Historical Context & ADRs
- graphify
- workflows/graphify.md
- eslint.config.mjs
- next.config.ts
- next-env.d.ts
- postcss.config.mjs
- task.md

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 16 edges
2. `GROCER — Engineering Prototype & Problem Exploration` - 12 edges
3. `include` - 7 edges
4. `AGENTS.md — Grocer Project Rules` - 6 edges
5. `usePhoneDemoEngine()` - 5 edges
6. `scripts` - 5 edges
7. `Log Entries` - 5 edges
8. `ARCHITECTURE.md — Product Strategy & System Architecture` - 5 edges
9. `StapleItem` - 4 edges
10. `CardSurface()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `PhoneMockup()` --calls--> `usePhoneDemoEngine()`  [EXTRACTED]
  components/PhoneMockup.tsx → hooks/usePhoneDemoEngine.ts
- `GrocerVelocityCalculator()` --calls--> `usePantryEngine()`  [EXTRACTED]
  components/grocer/GrocerVelocityCalculator.tsx → hooks/usePantryEngine.ts
- `usePhoneDemoEngine()` --calls--> `getSimulatedPantryStaples()`  [EXTRACTED]
  hooks/usePhoneDemoEngine.ts → lib/simulationEngine.ts
- `usePhoneDemoEngine()` --calls--> `processWhatsAppSimulationMessage()`  [EXTRACTED]
  hooks/usePhoneDemoEngine.ts → lib/simulationEngine.ts

## Import Cycles
- None detected.

## Communities (28 total, 7 thin omitted)

### Community 0 - "GrocerValueProp.tsx"
Cohesion: 0.23
Nodes (9): GrocerIntegrations(), GrocerValueProp(), GrocerVelocityCalculator(), CardSurface(), CardSurfaceProps, PillBadge(), PillBadgeProps, PantryItem (+1 more)

### Community 1 - "IosNotificationBanner.tsx"
Cohesion: 0.15
Nodes (5): IosNotificationBanner(), IosNotificationBannerProps, IphoneFrame(), IphoneFrameProps, WhatsAppIcon()

### Community 2 - "include"
Cohesion: 0.20
Nodes (9): **/*.mts, .next/dev/types/**/*.ts, next-env.d.ts, .next/types/**/*.ts, node_modules, **/*.ts, **/*.tsx, exclude (+1 more)

### Community 6 - "compilerOptions"
Cohesion: 0.11
Nodes (19): dom, dom.iterable, esnext, compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules (+11 more)

### Community 7 - "devDependencies"
Cohesion: 0.12
Nodes (17): eslint, eslint-config-next, devDependencies, eslint, eslint-config-next, tailwindcss, @tailwindcss/postcss, @types/node (+9 more)

### Community 8 - "ARCHITECTURE.md — Product Strategy & System Architecture"
Cohesion: 0.25
Nodes (7): 1. PRODUCT VISION & STRATEGIC PURPOSE, 2. USER EXPERIENCE & SYSTEM ARCHITECTURE, 3. CORE TECHNICAL COMPONENTS, 4. DESIGN INVARIANTS & PRINCIPLES, ARCHITECTURE.md — Product Strategy & System Architecture, The Problem: Reactive Commerce & Daily Staple Stockout Gap, The Prototype: Grocer Simulation & Showcase Engine

### Community 10 - "README.md"
Cohesion: 0.22
Nodes (8): 📌 About the Project, 🏗️ Architecture, 📜 Available Scripts, 💻 Getting Started, 🚀 Key Features, 📄 License, Prerequisites, Quick Start (1 Command)

### Community 11 - "dependencies"
Cohesion: 0.11
Nodes (19): clsx, framer-motion, lucide-react, next, dependencies, clsx, framer-motion, lucide-react (+11 more)

### Community 12 - "usePhoneDemoEngine.ts"
Cohesion: 0.18
Nodes (16): PhoneMockup(), usePhoneDemoEngine(), DEFAULT_PANTRY_STAPLES, ICON_MAP, PantryStapleDefinition, PRICE_SIGNALS, RECIPE_DB, getSimulatedPantryStaples() (+8 more)

### Community 15 - "package.json"
Cohesion: 0.20
Nodes (9): description, name, private, scripts, build, dev, lint, start (+1 more)

### Community 18 - "AGENTS.md — Grocer Project Rules"
Cohesion: 0.29
Nodes (6): 1. PROJECT IDENTITY, 2. TECH STACK, 3. DEV COMMANDS, 4. LOCAL RULES & DESIGN INVARIANTS, 5. SESSION RESUME, AGENTS.md — Grocer Project Rules

### Community 21 - "Read at the START of EVERY session."
Cohesion: 0.40
Nodes (4): Business Rules (Never Break), CONTEXT.md — Domain Language, Core Entities & Product Purpose, Read at the START of EVERY session.

### Community 22 - "GROCER — Engineering Prototype & Problem Exploration"
Cohesion: 0.15
Nodes (12): 10. Engineering decisions & design invariants (reference), 1. The problem I noticed, 2. What the prototype does, 3. System architecture, 4. How the prediction model works, 5. How the dark-store integration is mocked, 6. If this were ever pursued for real, how I'd want to validate it, 7. Conceptual integration shape (not a request for access) (+4 more)

### Community 24 - "Component 3: Component-Wide Light Surface Transformation & Component Reuse"
Cohesion: 0.12
Nodes (15): Automated Tests, Component 1: Hero Section Clean Up, Component 2: Design System Token Clean Up (Dark Mode Purge), Component 3: Component-Wide Light Surface Transformation & Component Reuse, Finalized Architecture & Design Decisions, Implementation Plan — Light Theme Unification & Hero Cleanup (Finalized via /grill-me), Manual Verification, [MODIFY] [`CardSurface.tsx`](file:///d:/Grocer/frontend/components/ui/CardSurface.tsx) (+7 more)

### Community 26 - ".prettierrc.json"
Cohesion: 0.18
Nodes (10): arrowParens, bracketSpacing, endOfLine, jsxSingleQuote, printWidth, semi, singleQuote, tabWidth (+2 more)

### Community 27 - "page.tsx"
Cohesion: 0.20
Nodes (8): GrocerFAQ(), GrocerFooter(), GrocerHeader(), GrocerHero(), GrocerLogo(), GrocerLogoProps, PillButton(), PillButtonProps

### Community 28 - "app/layout.tsx"
Cohesion: 0.33
Nodes (4): cambo, inter, metadata, outfit

### Community 30 - "Changes Made"
Cohesion: 0.22
Nodes (8): 1. Hero Section (`GrocerHero.tsx`), 2. Page Streamlining (`page.tsx`), 3. Component & Micro-Interaction Polish, Automated Tests, Changes Made, Next Steps, Verification Results, Walkthrough — Side-by-Side Hero & UI Perfection Complete

### Community 33 - "Log Entries"
Cohesion: 0.25
Nodes (7): [Grocer — Full Codebase Architecture Refactoring & Guided Demo Tour] 2026-08-14, [Grocer — Pure Next.js 16 Refactor & Full Codebase Cleanup] 2026-08-26, [Grocer — Saved Exact Figma Notification Layout & WhatsApp Icon] 2026-08-15, How to Maintain This Journal (For the Agent), Log Entries, Product Journal, [Project — Example Entry] 2026-08-12

### Community 41 - "Grocer — Historical Context & ADRs"
Cohesion: 0.50
Nodes (3): Architectural Decision Records (ADRs), Core Feature Specifications, Grocer — Historical Context & ADRs

## Knowledge Gaps
- **131 isolated node(s):** `CardSurfaceProps`, `PillBadgeProps`, `PantryItem`, `IosNotificationBannerProps`, `IphoneFrameProps` (+126 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `dependencies` connect `dependencies` to `package.json`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Why does `devDependencies` connect `devDependencies` to `package.json`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Why does `compilerOptions` connect `compilerOptions` to `include`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **What connects `CardSurfaceProps`, `PillBadgeProps`, `PantryItem` to the rest of the system?**
  _131 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `IosNotificationBanner.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.14619883040935672 - nodes in this community are weakly interconnected._
- **Should `compilerOptions` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._
- **Should `devDependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._