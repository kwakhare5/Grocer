# Grocer — Proactive WhatsApp Grocery Replenishment Assistant & Swiggy Instamart CommercePort

[![Next.js](https://img.shields.io/badge/Next.js-16.2.6-black?style=flat&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Swiggy Instamart](https://img.shields.io/badge/Swiggy-CommercePort%20MCP-FC8019?style=flat)](https://mcp.swiggy.com/builders/llms.txt)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat&logo=typescript)](https://typescriptlang.org/)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind-v4.0-38B2AC?style=flat&logo=tailwind-css)](https://tailwindcss.com/)

**Grocer** is an intelligent, proactive consumer grocery replenishment assistant designed for Indian households. Rather than waiting for pantries to run empty, Grocer forecasts household staple consumption (milk, eggs, tomatoes, bread, curd) and initiates contextual, interactive WhatsApp restocking conversations. Once confirmed by the user, orders are routed seamlessly to quick-commerce delivery via **Swiggy Instamart** through an abstracted **CommercePort** adapter.

> [!NOTE]
> **Subsystem Decoupling:**
> This repository houses the **Consumer WhatsApp Replenishment Assistant & CommercePort**.
> The dark store fleet operations command center has been split into its own standalone platform at [kwakhare5/Dark-store-operator](https://github.com/kwakhare5/Dark-store-operator).

---

## 🌟 Key Highlights

```
   ┌────────────────────────────────────────────────────────┐
   │             Household Pantry Depletion Math            │
   │  - Daily staple run-rates (e.g. 0.48L milk/day)        │
   │  - 25 Mumbai household profiles (diets & family sizes) │
   └───────────────────────────┬────────────────────────────┘
                               │ Anticipatory Trigger
   ┌───────────────────────────▼────────────────────────────┐
   │            WhatsApp Interactive Conversational UI      │
   │  - iPhone 17 Pro native chat viewport                  │
   │  - Natural restock proposals & 1-tap responses         │
   │  - Remind later & quantity modifier controls           │
   └───────────────────────────┬────────────────────────────┘
                               │ Explicit Human Approval
   ┌───────────────────────────▼────────────────────────────┐
   │         CommercePort & Consequential Action Guard      │
   │  - Mandatory explicit confirmation gate                │
   │  - Abstracted Swiggy Instamart MCP & Mock Adapters     │
   │  - Real-time cart synchronization & order dispatch     │
   └────────────────────────────────────────────────────────┘
```

---

## 📱 Features

### 1. Proactive WhatsApp Conversational Restock
- Renders an interactive, true-to-life **iPhone 17 Pro frame** with WhatsApp chat bubbles.
- Anticipates staple depletion before breakfast or dinner:
  > *"Good morning Rohan! Your Amul Taaza Milk has 1 day left (~15% remaining). Would you like to restock 2 packs via Swiggy Instamart for ₹132?"*
- Supports 1-tap quick actions:
  - **Restock Now (₹132)**
  - **Remind Me in 2 Hours**
  - **Skip for Now**

### 2. Interactive Household Pantry Telemetry
- Real-time pantry level gauges across critical grocery categories:
  - **Dairy:** Amul Taaza Milk 1L, Fresh Malai Paneer 200g, Epigamia Greek Yogurt
  - **Produce:** Fresh Hybrid Tomatoes 500g, Farm Fresh Red Onions 1kg, Cavendish Bananas
  - **Poultry & Bakery:** Fresh Farm Eggs (Pack of 6), The Baker's Dozen Sourdough Bread
  - **Pantry Staples:** Fortune Sunlite Sunflower Oil 1L, Aashirvaad Shudh Chakki Atta 5kg
- Live depletion visualizers displaying days remaining, daily consumption rates, and reorder threshold badges.

### 3. Swiggy Instamart CommercePort Integration
- Standardized `CommercePort` interface supporting dual operational modes:
  - **Live Swiggy MCP Server:** Dispatches live API calls to Swiggy Instamart endpoints (`/instamart/cart`, `/instamart/checkout`).
  - **Simulated CommercePort:** High-fidelity in-memory edge fallback with full SKU catalogs and simulated rider tracking.
- Features real-time cart inspector, address selector, and simulated live rider tracking (`ORDER_CONFIRMED` $\to$ `PACKING` $\to$ `OUT_FOR_DELIVERY` $\to$ `DELIVERED`).

### 4. Strict Consequential Action Guard (Spec §28.3 & §39.15)
- Invariant safety rule: The assistant **cannot execute a checkout without explicit human authorization**.
- A checkout request without `explicit_confirmation: true` is strictly rejected server-side with an `UnconfirmedCheckoutError` (HTTP 400).
- Users are presented with a clear checkout verification modal detailing itemized costs, delivery address, and delivery partner fees before confirmation.

### 5. 25 Realistic Mumbai Household Personas
- Spans distinct neighborhoods, household sizes, and dietary patterns:
  - **Rohan Mehta** (Bandra West, 3 members, Vegetarian)
  - **Priya Sharma** (Powai Galleria, 2 members, Non-Vegetarian)
  - **Dr. Ananya Iyer** (Lower Parel, 4 members, South Indian Traditional)
  - **Vikram Patel** (Andheri East, 5 members, Jain Vegetarian)
  - ...and 21 additional simulated households with deterministic consumption patterns.

---

## 🛠️ Tech Stack

- **Frontend:** Next.js 16.2.6 (App Router with Turbopack), React 19, TypeScript 5.
- **Styling:** Tailwind CSS v4, Framer Motion (fluid spring animations), Lucide React.
- **Typography:** Swiss Logistics System (`PP Mori` primary sans, `Geist Mono` tabular telemetry, and strictly upright `PP Editorial New` accents).
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy Async, SQLite (WAL mode).
- **Testing:** Pytest with 100% green customer commerce test coverage.

---

## 🚀 Quickstart

### Prerequisites
- Node.js 20+
- Python 3.11+

### 1. Frontend Setup
```bash
# Install dependencies
npm install

# Run development server (Turbopack)
npm run dev

# Run production build
npm run build

# Run linting
npm run lint
```
Open [http://localhost:3000](http://localhost:3000) to view the application.

### 2. Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run customer commerce test suite
pytest tests/

# Run FastAPI server
uvicorn backend.main:app --reload --port 8000
```

---

## 🔒 Safety & Domain Invariants

1. **Explicit Confirmation Gate:** Autonomous cart creation is permitted, but financial execution strictly requires `explicit_confirmation: true`.
2. **Decoupled Commerce Boundary:** Customer orders route via `CommercePort` and emit decoupled audit events, ensuring consumer carts never directly mutate internal dark store state.
3. **Zero AI Slop:** No emoji spam in buttons, clean Lucide SVG icons, crisp monospace metrics, and authentic Indian grocery branding.

---

## 📄 Related Projects
- [Dark Store Operator](https://github.com/kwakhare5/Dark-store-operator) — Autonomous quick-commerce dark store fleet operations platform.

---

## 📄 License
MIT © 2026 Karan Wakhare
