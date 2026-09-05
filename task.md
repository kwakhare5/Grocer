# Tracer Bullets: Phase 8 Customer Replenishment Workflow & Swiggy MCP Commerce Integration

- [x] 1. Seam 1: CommercePort Architecture & Data Models (`backend/integrations/commerce/`) — Create abstract `CommercePort`, domain models (`DeliveryAddress`, `CommerceCart`, `ProductVariant` with `spinId`, `CommerceOrderResult`), canonical Swiggy-aligned error taxonomy, and adapter factory <!-- id: 1 -->
- [x] 2. Seam 2: High-Fidelity Mock Commerce Adapter (`backend/integrations/commerce/mock_adapter.py`) — Implement deterministic Mumbai fleet simulation, variant search, bill calculation, explicit confirmation assertion, and multi-stage tracking progression <!-- id: 2 -->
- [x] 3. Seam 3: Swiggy Instamart MCP Adapter (`backend/integrations/commerce/swiggy_adapter.py`) — Implement official Swiggy Instamart MCP protocol (`POST mcp.swiggy.com/im`), token security, error taxonomy translation, and explicit checkout confirmation guard <!-- id: 3 -->
- [x] 4. Seam 4: Customer Replenishment Service Upgrade (`backend/services/customer/service.py`) — Refactor `CustomerService` to orchestrate household depletion forecasting, runout detection, proactive alerts, and CommercePort reorders <!-- id: 4 -->
- [x] 5. Seam 5: Customer Commerce API Endpoints & Schemas (`backend/api/customers.py` & `schemas.py`) — Expose delivery addresses, go-to items, cart management, payment options, confirmed checkout, and tracking endpoints <!-- id: 5 -->
- [x] 6. Seam 6: Frontend Customer View & API Integration (`lib/apiClient.ts` & `components/customer/CustomerReplenishmentView.tsx`) — Add typed client methods, live adapter badge, bill breakdown drawer, explicit confirmation modal, and real-time delivery tracking <!-- id: 6 -->
- [x] 7. Seam 7: Phase 8 Test Suite & Full System Verification (`backend/tests/test_phase8_commerce.py`) — Write comprehensive test suite covering CommercePort, adapters, explicit confirmation safety, customer workflow, plus full pytest suite and production build <!-- id: 7 -->






