# GROCER v2 — Complete UI, Colors, Buttons, Layout & Screen Flows Specification

> **Status:** Fully Aligned via `/taste-skill`, `/emil-design-eng`, and `/grill-me`.
> **Applies to:** Frontend architecture, Tailwind tokens, Component Library, Operations Deck, and WhatsApp Simulator.

---

## 1. Visual Foundation & Tone

* **Aesthetic Direction:** **Precision Crisp Light** (`#FAFAFA` canvas with `#FFFFFF` ceramic card surfaces).
* **Guiding Metaphor:** Quick-Commerce Fleet Command Cockpit + High-Fidelity Mobile Consumer Companion.
* **Anti-Slop Discipline:**
  - Zero AI-purple gradient blobs
  - Zero fake generic glassmorphism over dense tables
  - Pure high-contrast typography and semantic color coding
  - Monospace tabular figures for all dynamic telemetry, coordinates, and stock levels

---

## 2. Comprehensive Color & Semantic Token System

### 2.1 Surfaces & Structure
| Token | Hex / Class | Usage |
|---|---|---|
| `--background` | `#FAFAFA` (`bg-[#FAFAFA]`) | Main application canvas |
| `--surface-card` | `#FFFFFF` (`bg-white`) | Elevated ceramic cards and cockpit columns |
| `--surface-subtle` | `#F4F4F5` (`bg-zinc-100`) | Inactive tabs, table headers, secondary pill trays |
| `--border` | `#E4E4E7` (`border-zinc-200`) | Standard 1px crisp structural hairlines |
| `--border-hover` | `#D4D4D8` (`hover:border-zinc-300`) | Interactive card & button hover highlight |
| `--foreground` | `#09090B` (`text-zinc-950`) | High-contrast headline and body ink |
| `--foreground-muted` | `#71717A` (`text-zinc-500`) | Captions, metadata, secondary timestamps |

### 2.2 Operator Action Tokens (The 4 Core Actions)
| Action | Accent Color | Hex | Badge Class | Description |
|---|---|---|---|---|
| **TRANSFER** | **Sky Blue** | `#0284C7` | `bg-sky-50 text-sky-700 border-sky-200` | Inter-store lateral stock redistribution |
| **REORDER** | **Indigo** | `#4F46E5` | `bg-indigo-50 text-indigo-700 border-indigo-200` | Expedited supplier replenishment purchase order |
| **DISCOUNT** | **Amber** | `#D97706` | `bg-amber-50 text-amber-700 border-amber-200` | Price markdowns to clear near-expiry batch stock |
| **HOLD** | **Zinc** | `#71717A` | `bg-zinc-100 text-zinc-700 border-zinc-200` | Passive absorption of minor demand variance |

### 2.3 Risk Severity Tokens
| Severity | Hex | Visual Treatment | Trigger Threshold |
|---|---|---|---|
| **CRITICAL** | `#F43F5E` (Rose) | `bg-rose-50 text-rose-700 border-rose-200` + animated pulse | Stockout projected within <6h |
| **WARNING** | `#F59E0B` (Amber) | `bg-amber-50 text-amber-700 border-amber-200` | Stockout in 6–24h OR Spoilage <48h |
| **SAFE / HEALTHY** | `#10B981` (Emerald) | `bg-emerald-50 text-emerald-700 border-emerald-200` | Safe stock buffer > safety lead time |

---

## 3. Button & Interactive Element Hierarchy

```text
Global Actions (Nav / Simulation / Mode):
└── Full Pill (border-radius: 9999px)
    ├── Primary: Solid #09090B, White Text, subtle inner bevel, 0.97 press scale
    └── Secondary: Solid #FFFFFF, #18181B Text, 1px #E4E4E7 border, hover:bg-[#F4F4F5]

In-Card Operational Controls (Approve / Reject / Why / Filter):
└── Tactile Rounded-Rect (border-radius: 10px - 12px)
    ├── Approve: Solid #10B981 or #09090B, bold white label, 160ms ease-out
    ├── Reject / Cancel: Subdued #F4F4F5, text-zinc-600, hover:bg-rose-50 hover:text-rose-700
    └── WHY? / Inspect: 1px border-zinc-200, hover:border-zinc-400, active:scale-97
```

### Micro-Physics Rules (Emil Kowalski Standard)
- **Active Press:** `:active { transform: scale(0.97); }` on all buttons and pills.
- **Timing:** All transitions strictly under `180ms` using `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)`.
- **Hardware Acceleration:** All transforms animate via `transform` / `opacity`, never layout properties.

---

## 4. Typography Hierarchy

```text
Display & Section Headers:  Outfit (Semibold / Bold 600-700)
Problem Statement Accents:  Cambo Serif (Editorial italic/regular)
Body & Interfaces:          Outfit (Regular / Medium 400-500)
Telemetry / Stock / Clock:  Geist Mono / JetBrains Mono / font-mono (tabular-nums)
```

---

## 5. Operations Cockpit Layout (3-Column Architecture)

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [Logo] GROCER v2   │   [ ▶ Run | ⏸ Pause | +1h | +6h | +24h | Reset ]   │   [ Operations ↔ WhatsApp ] │
├──────────────────────────┬──────────────────────────────────────┬────────────────────────────────┤
│ 1. SPATIAL TOPOLOGY      │ 2. RECOMMENDATION STREAM             │ 3. WHY EXPLAINABILITY          │
│    (Left Column, 30%)    │    (Center Column, 42%)              │    & APPROVAL INSPECTOR (28%)  │
│                          │                                      │                                │
│ • Interactive SVG Mumbai │ • Real-Time Decision Cards:          │ • Root Cause Breakdown         │
│   Dark Store Network:    │   ┌──────────────────────────────┐   │ • 3 Ranked Alternatives:       │
│   - Andheri (19.11)      │   │ HIGH STOCKOUT RISK           │   │   1. [REC] Transfer (Score 92) │
│   - Bandra  (19.06)      │   │ Store 04 · Milk 1L           │   │   2. Emergency Reorder (ETA 30h)
│   - Powai   (19.12)      │   │ TRANSFER 20 units (St 02→04) │   │   3. Hold & Absorb Loss        │
│   - Dadar   (19.02)      │   │ [ WHY? ] [ APPROVE ] [ REJ ] │   │ • Tradeoff Analysis:           │
│   - Thane   (19.22)      │   └──────────────────────────────┘   │   - Spoilage Avoidance: +₹1,320│
│ • Live Stockout Pulse    │ • Real-time Filters (All/Stockout/   │   - Transport Cost: -₹140      │
│ • Dotted Transit Lines   │   Spoilage/Transfers/Reorders)       │   - Net Benefit: +₹1,180       │
│ • Store Inventory Health │ • Live Simulation Event Feed         │ • [ ⚡ APPROVE ACTION ]         │
│   Bars (Dairy/Produce)   │   (Orders, Batch Expiry, Restock)    │ • [ ✕ REJECT WITH REASON ]     │
└──────────────────────────┴──────────────────────────────────────┴────────────────────────────────┘
```

---

## 6. End-to-End Screen Flows

### Flow A: Operator Recommendation Approval
1. **Detection:** Risk Engine identifies projected stockout at Store 04 (Dadar).
2. **Generation:** Decision Engine ranks `TRANSFER from Store 02 (Bandra)` as optimal (Score 94, safe excess: 20).
3. **Display:** Recommendation Card appears in Center Column with Sky Blue `[TRANSFER]` badge and countdown.
4. **Inspection:** Operator clicks card or `[ WHY? ]` → Right Inspector slides in (`180ms ease-out`), displaying the 3 evaluated options, stock projection graph, and financial delta.
5. **Execution:** Operator clicks `[ ⚡ APPROVE ACTION ]`:
   - Card transitions optimistically to `EXECUTING` state with a checkmark.
   - SVG Map in Left Column animates a pulsed dotted particle traveling from Bandra to Dadar.
   - Dadar inventory meter updates in real-time.
   - `ACTION_APPROVED` and `TRANSFER_COMPLETED` events log to Activity Timeline.

### Flow B: Customer WhatsApp Simulated Restocking
1. **Push Alert:** Lockscreen Notification appears on simulated iPhone:
   > *"Grocer: You're running low on Full Cream Milk (0.5L left). Restock before 7 AM tomorrow?"*
2. **Open Chat:** Tapping notification opens WhatsApp conversational interface.
3. **Smart Replenishment Bubble:** Displays product image, price (`₹66`), quantity (`1L`), and 3 quick-action chips:
   - `[ ⚡ Confirm 1L (₹66) ]`
   - `[ ⏰ Remind Tomorrow ]`
   - `[ ✏️ Modify Items ]`
4. **1-Tap Confirmation:** Customer taps `[ ⚡ Confirm 1L ]`:
   - Instant double-blue-tick delivery feedback.
   - Bot sends Order Confirmed card (`Delivery by 6:45 AM`).
   - Order is dispatched to the backend database and immediately reflects in Operations Cockpit activity feed.
5. **Pantry View Sync:** Switching to Pantry tab shows Milk level restored to 100% with fresh batch expiry timer.
