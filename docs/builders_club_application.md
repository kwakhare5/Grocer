# Swiggy Builders Club Application Draft

**To:** Swiggy Builders Club Selection Committee
**Subject:** Instamart Intelligence — An AI-Powered Retention Moat to Win the Quick Commerce War

---

## 1. Problem Statement
In the hyper-competitive quick commerce landscape, Swiggy Instamart and competitors (such as Blinkit) are functionally commoditized: they deliver the same brands within the same 10-minute window at matching prices. There is virtually zero friction or switching cost for users—they use whichever app they open first. To win this war, Swiggy cannot rely solely on speed or price. We need a structural, data-driven switching cost.

---

## 2. The Solution: Instamart Intelligence
Instamart Intelligence is an AI manager that sits directly on top of a user's grocery order history, learns their household's consumption patterns, and manages restocking before they run out. 

Instead of waiting for users to realize they are out of milk or cooking oil, the system automatically runs background time-series forecasts and notifies them via a friendly **WhatsApp bot** 2 days before depletion. The user replies with a simple "YES" or "just the oil", and the system automatically compiles the cart and schedules the delivery. Additionally, the platform integrates **Price Intelligence** (notifying users of dips/spikes in volatile staples like tomatoes and onions) and **Recipe Intelligence** (parsing recipes and cross-referencing estimated pantry stock to purchase only missing ingredients).

**The Competitive Moat:** Once a household trains this AI manager for 3 to 6 months, switching to Blinkit is a massive step backwards. Blinkit starts from zero; they do not know that you consume 1L milk every 2.1 days, buy 5kg atta every 17 days, or that you were traveling in March. This household profile is a highly sticky proprietary moat.

---

## 3. Swiggy Instamart MCP APIs Integrated
This prototype was developed locally using a mock Swiggy Instamart MCP server, integrating 5 core API boundaries:
*   `get_instamart_orders`: Extracts order histories for Prophet model fitting.
*   `search_instamart_items`: Performs catalog searches for missing recipe ingredients and price trackers.
*   `update_instamart_cart`: Programmatically populates and modifies user carts based on restock approvals.
*   `place_instamart_order`: Books checkout orders automatically upon user WhatsApp confirmation.
*   `track_instamart_order`: Retrieves delivery updates to notify the household when their items are on the way.

---

## 4. Projected Business Impact
*   **Customer Retention:** Establishes a switching-cost moat, reducing monthly churn of active grocery shoppers by a projected 25-30% after 90 days.
*   **Order Frequency:** Increases purchase frequency by replacing self-initiated "emergency ordering" with structured, AI-scheduled replenishment alerts.
*   **GMV Recovery:** Recovers lost GMV by capture-prompting restocking before users run out and default to buying from a local physical kirana store.

---

## 5. Technical Architecture & Proof
The system is built on a modern, asynchronous Python/TypeScript stack:
*   **Backend:** FastAPI async web server + APScheduler background cron tasks.
*   **Databases:** PostgreSQL with **TimescaleDB** (optimizing price-series sparkline queries) and `pgvector` (fuzzy recipe ingredient embeddings).
*   **Machine Learning:** **Facebook Prophet** for robust, anomaly-filtered time-series forecasting.
*   **Agent Orchestration:** **LangGraph** with a stateful checkpointer, managing multi-turn WhatsApp restock dialogues.
*   **AI Models:** **Claude 3.5 Sonnet** for parsing recipes into standard grocery line items and interpreting natural WhatsApp user messages.
*   **Frontend Dashboard:** A Next.js 16 app displaying depletion countdowns, accuracy metrics, and interactive price feeds.

*All backend code is verified using an async pytest suite (16 integration tests passing successfully), and the frontend builds cleanly without TypeScript or ESLint compile warnings.*

---

## 6. Call to Action
I have built a fully functional, end-to-end localhost prototype demonstrating this intelligence layer. 

*   **GitHub Repository:** [Insert Link]
*   **3-Minute Demo Video:** [Insert Demo Video Link]
    *   *Demonstrates: Dashboard timeline overview, cooking oil countdown metrics, Twilio WhatsApp YES → order placed flow, tomato price spikes, and Sunday Biryani pantry checks.*

I would love to pitch this directly to the Instamart product group and request sandbox API access to test this on real user opt-in cohorts.
