<!-- ╔══════════════════════════════════════════════════════════════════╗
     ║          Grocer — README                                        ║
     ║          Engineering Prototype & Problem Exploration           ║
     ╚══════════════════════════════════════════════════════════════════╝ -->

<div align="center">

  # Grocer

  ### *An engineering prototype & problem exploration for pre-emptive household replenishment in Quick Commerce.*

  <br/>

  ![Version](https://img.shields.io/badge/version-1.0.0-blue?style=for-the-badge)
  ![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)
  ![Language](https://img.shields.io/badge/Language-TypeScript-blue?style=for-the-badge&logo=typescript&logoColor=white)
  ![Next.js](https://img.shields.io/badge/Next.js-16.2-black?style=for-the-badge&logo=nextdotjs&logoColor=white)
  ![React](https://img.shields.io/badge/React-19.2-61DAFB?style=for-the-badge&logo=react&logoColor=black)
  ![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)

  <br/>

  <a href="#-about-the-project">About</a> &nbsp;·&nbsp;
  <a href="#-key-features">Key Features</a> &nbsp;·&nbsp;
  <a href="#-getting-started">Getting Started</a> &nbsp;·&nbsp;
  <a href="#-architecture">Architecture</a> &nbsp;·&nbsp;
  <a href="#-available-scripts">Available Scripts</a>

</div>

---

## 📌 About the Project

**Grocer** is a self-directed **engineering prototype & problem exploration** designed to address a fundamental gap in quick commerce: current platforms (Zepto, Blinkit, Swiggy Instamart, BigBasket) are fundamentally **reactive** (they wait for the user to open the app).

Built with **Next.js 16 (Turbopack), React 19, and Tailwind CSS v4**, Grocer demonstrates an end-to-end predictive replenishment system with a pure client-side simulation engine.

> **Real-World Problem & Benchmarks:**
> - **MilkBasket** built an entire business around scheduled recurring morning deliveries of milk and staples — proving predictable staple demand is a massive, real pattern.
> - **Blinkit** shipped a one-tap reorder button from past order history — proving platforms recognize repeat purchase velocity, though current implementations remain passive.
> - **The Actual Gap:** No platform has shipped a pre-emptive replenishment engine — forecasting stockouts 24h prior and delivering low-friction WhatsApp nudges.

---

## 🚀 Key Features

| Feature | Description | Technical Implementation |
|---|---|---|
| **Depletion Velocity Simulation** | Calculates daily usage rates per staple (`0.48L/day` for milk) and projects stockout dates. | Pure TS Math (`lib/simulationEngine.ts`) |
| **Interactive iPhone 16 Pro Demo** | 6.3" physical hardware frame with interactive Lock Screen, WhatsApp Chat, and Pantry Health dashboard. | Framer Motion + Lucide (`components/PhoneMockup.tsx`) |
| **5-Node State Machine** | Deterministic multi-turn restock state machine (`check_pantry → generate_alert → parse_user_reply → build_cart → execute_order`). | Client State Machine (`lib/simulationEngine.ts`) |
| **Smart Recipe Ingredient Fulfiller** | Cross-references pantry inventory against recipes (Biryani, Dal, Paneer, Oats) and adds missing items to cart in 1 tap. | Reactive Catalog (`lib/mockData.ts`) |
| **Dark Store Webhook Simulator** | Interactive API console simulating order ingestion, WhatsApp quick replies, and dark-store checkout dispatches. | Interactive Console (`components/grocer/GrocerIntegrations.tsx`) |

---

## 💻 Getting Started

### Prerequisites
- **Node.js 18+** or **Node.js 20+**
- **npm** or **pnpm**

### Quick Start (1 Command)
```bash
# 1. Clone the repository
git clone https://github.com/kwakhare5/Grocer.git
cd Grocer

# 2. Install dependencies
npm install

# 3. Start local Next.js development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to explore the interactive showcase.

---

## 🏗️ Architecture

```
Grocer (Next.js 16 + React 19)
├── app/
│   ├── layout.tsx             # Root layout & font metadata
│   ├── page.tsx               # Landing page & problem showcase
│   └── globals.css            # Tailwind CSS v4 styling tokens
├── components/
│   ├── PhoneMockup.tsx        # Interactive iPhone 16 Pro hardware simulator
│   ├── grocer/                # Hero, Bento Grid, Velocity Calculator, Integrations, FAQ, Footer
│   ├── mockup/                # iOS Notification banner & Lock screen assets
│   └── ui/                    # Authentic frame, pill badges, buttons, WhatsApp icon
├── hooks/
│   └── usePhoneDemoEngine.ts  # Unified demo state & chat interaction controller
├── lib/
│   ├── simulationEngine.ts    # Household depletion formulas & state machine
│   ├── mockData.ts            # Single-source-of-truth catalog, recipes, price signals
│   ├── types.ts               # Core TypeScript interfaces
│   └── utils.ts               # Date & formatting helpers
```

---

## 📜 Available Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start Next.js development server on `http://localhost:3000` |
| `npm run build` | Compile optimized production build via Turbopack |
| `npm run start` | Start production server |
| `npm run lint` | Run ESLint verification |

---

## 📄 License
MIT License. Created by [Karan Wakhare](https://github.com/kwakhare5).
