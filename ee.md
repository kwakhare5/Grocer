# Restock API Sync Fix — Frontend ↔ Backend

**Scope:** `frontend/lib/api.ts`, `frontend/lib/hooks.ts`, and a safe audit of unused FastAPI routes.
**Constraints honored:** no new features/UI, existing dashboard (household/predictions/prices/recipes/orders) untouched, strict TypeScript typing matching the established SWR pattern in this codebase.

---

## Table of Contents

1. [Diagnosis](#1-diagnosis)
2. [Fix 1 — `frontend/lib/api.ts` diff](#2-fix-1--frontendlibapits-diff)
3. [Fix 2 — `frontend/lib/hooks.ts` diff](#3-fix-2--frontendlibhooksts-diff)
4. [Fix 3 — Unused Backend Route Audit](#4-fix-3--unused-backend-route-audit)
5. [Verification Checklist](#5-verification-checklist)

---

## 1. Diagnosis

`restock.py` exposes three endpoints, none of which are "cart" endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/restock/{user_id}` | Read-only depletion status (`depleting_items`) |
| `POST` | `/api/restock/{user_id}/check-now` | Triggers a check, persists a `RestockAlert` |
| `GET` | `/api/restock/{user_id}/history?limit=` | Last N `RestockAlert` records |

`api.ts` currently has `getCart` / `addToCart` / `checkout` — none of these routes exist on the backend at all, so any component calling `restockApi.getCart(...)` today is hitting a 404. This isn't a "some fields don't match" problem, it's a "these endpoints don't exist" problem — the fix is a full replacement of the `restockApi` object plus the response types it returns.

One shape subtlety worth calling out before the diff: `POST /check-now` returns **two different shapes** depending on whether anything was found —

```jsonc
// nothing depleting:
{ "alerts_triggered": 0, "message": "...", "items": [] }

// items found:
{ "alerts_triggered": 2, "alert_id": "...", "message": "...", "whatsapp_preview": "...", "items": [...] }
```

`alert_id` and `whatsapp_preview` are *absent from the JSON entirely* in the empty case (not `null`) — so in TypeScript they're modeled as optional (`?`), not nullable (`| null`), matching how a key that's missing from a JSON object deserializes to `undefined` rather than `null`.

---

## 2. Fix 1 — `frontend/lib/api.ts` diff

```diff
 export interface APIPriceAlertsResponse {
   alerts: APIPriceFeedItem[];
 }
 
+// ---------------------------------------------------------------------------
+// Restock — matches backend/api/routes/restock.py exactly (3 endpoints,
+// no cart/checkout endpoints exist on the backend).
+// ---------------------------------------------------------------------------
+
+export interface APIRestockItem {
+  item_id: string;
+  item_name: string;
+  category: string;
+  confidence_score: number;
+  confidence_label: string;
+  avg_daily_consumption: number;
+  estimated_depletion_date: string;
+  days_remaining: number;
+  last_purchase_date: string | null;
+}
+
+export interface APIRestockStatusResponse {
+  user_id: string;
+  household_id: string;
+  threshold_days: number;
+  min_confidence: number;
+  depleting_count: number;
+  depleting_items: APIRestockItem[];
+}
+
+export interface APIRestockCheckSummaryItem {
+  name: string;
+  days_remaining: number;
+  confidence: string;
+}
+
+export interface APIRestockCheckResponse {
+  alerts_triggered: number;
+  // Absent from the JSON entirely (not null) when alerts_triggered === 0 —
+  // see backend/api/routes/restock.py::trigger_restock_check's early return.
+  alert_id?: string;
+  message: string;
+  whatsapp_preview?: string;
+  items: APIRestockCheckSummaryItem[];
+}
+
+export interface APIRestockAlert {
+  id: string;
+  item_ids: string[] | null;
+  message: string;
+  sent_at: string | null;
+  // 'dismissed' is referenced in the backend docstring for get_alert_history
+  // ("track acted/dismissed status") even though no code path shown sets it —
+  // kept in the union so the type doesn't silently narrow it out.
+  status: 'pending' | 'sent' | 'acted' | 'dismissed';
+  acted_at: string | null;
+}
+
+export interface APIRestockHistoryResponse {
+  user_id: string;
+  alerts: APIRestockAlert[];
+}
+
 export const householdApi = {
   sync: (userId: string) => api.post<{ message: string; household_id: string }>(`/api/household/${userId}/sync`),
   getProfile: (userId: string) => api.get<APIHouseholdProfile>(`/api/household/${userId}`),
   switchScenario: (userId: string, scenario: string) => api.post<{ success: boolean; message: string }>(`/api/household/${userId}/scenario`, { scenario }),
 };
```

```diff
-export const restockApi = {
-  getCart: (userId: string) => api.get(`/api/restock/${userId}/cart`),
-  addToCart: (userId: string, data: { item_name: string, quantity?: number, source?: string }) => api.post(`/api/restock/${userId}/cart`, data),
-  checkout: (userId: string) => api.post(`/api/restock/${userId}/checkout`),
-};
+export const restockApi = {
+  /** GET /api/restock/{user_id} — read-only depletion status, no side effects. */
+  getStatus: (userId: string) =>
+    api.get<APIRestockStatusResponse>(`/api/restock/${userId}`),
+
+  /** POST /api/restock/{user_id}/check-now — triggers a check, persists a RestockAlert. */
+  checkNow: (userId: string) =>
+    api.post<APIRestockCheckResponse>(`/api/restock/${userId}/check-now`),
+
+  /** GET /api/restock/{user_id}/history?limit= — last N RestockAlert records. */
+  getHistory: (userId: string, limit: number = 20) =>
+    api.get<APIRestockHistoryResponse>(`/api/restock/${userId}/history?limit=${limit}`),
+};
 
 export default api;
```

Nothing else in the file changes — `householdApi`, `predictionsApi`, `recipesApi`, `pricesApi`, and `ordersApi` are all already correctly mapped and are left untouched.

---

## 3. Fix 2 — `frontend/lib/hooks.ts` diff

```diff
 import useSWR from "swr";
 import {
   predictionsApi,
   ordersApi,
   householdApi,
   recipesApi,
   pricesApi,
+  restockApi,
   APIPredictionsResponse,
   APIOrdersResponse,
   APIHouseholdProfile,
   APIRecipesResponse,
   APIPriceFeedItem,
-  APIPriceAlertsResponse
+  APIPriceAlertsResponse,
+  APIRestockStatusResponse,
+  APIRestockHistoryResponse
 } from "./api";
 
 // Fetchers
 const fetchPredictions = (userId: string) => predictionsApi.getForHousehold(userId).then(res => res.data);
 const fetchOrders = (userId: string) => ordersApi.getOrders(userId).then(res => res.data);
 const fetchProfile = (userId: string) => householdApi.getProfile(userId).then(res => res.data);
 const fetchRecipes = (userId: string) => recipesApi.getForHousehold(userId).then(res => res.data);
 const fetchPricesFeed = () => pricesApi.getFeed().then(res => res.data);
 const fetchPricesAlerts = () => pricesApi.getAlerts().then(res => res.data);
+const fetchRestockStatus = (userId: string) => restockApi.getStatus(userId).then(res => res.data);
+const fetchRestockHistory = (userId: string) => restockApi.getHistory(userId).then(res => res.data);
```

Append the two new hooks at the end of the file, immediately after `usePriceAlerts` — same shape (fetcher key = the endpoint path, `revalidateOnFocus: false`, `dedupingInterval: 60000`) as every other hook already in the file:

```diff
 export function usePriceAlerts() {
   const { data, error, isLoading, mutate } = useSWR<APIPriceAlertsResponse>(
     "/api/prices/alerts",
     fetchPricesAlerts,
     { revalidateOnFocus: false, dedupingInterval: 60000 }
   );
 
   return {
     alertsData: data,
     isLoading,
     isError: error,
     mutateAlerts: mutate
   };
 }
+
+export function useRestockStatus(userId: string = "demo_user_001") {
+  const { data, error, isLoading, mutate } = useSWR<APIRestockStatusResponse>(
+    `/api/restock/${userId}`,
+    () => fetchRestockStatus(userId),
+    { revalidateOnFocus: false, dedupingInterval: 60000 }
+  );
+
+  return {
+    restockStatusData: data,
+    isLoading,
+    isError: error,
+    mutateRestockStatus: mutate
+  };
+}
+
+export function useRestockHistory(userId: string = "demo_user_001") {
+  const { data, error, isLoading, mutate } = useSWR<APIRestockHistoryResponse>(
+    `/api/restock/${userId}/history`,
+    () => fetchRestockHistory(userId),
+    { revalidateOnFocus: false, dedupingInterval: 60000 }
+  );
+
+  return {
+    restockHistoryData: data,
+    isLoading,
+    isError: error,
+    mutateRestockHistory: mutate
+  };
+}
```

**Why no `useRestockCheckNow` hook:** `check-now` is a `POST` that mutates state (writes a `RestockAlert`), not a data fetch — SWR's `useSWR` is for `GET`-style reads, which is exactly why every other hook in this file wraps a `GET`. You didn't ask for a mutation hook, so none was added (per the "no new features" constraint) — `restockApi.checkNow(userId)` is already fully typed and callable directly from wherever you need it (e.g. a button's `onClick`), followed by `mutateRestockStatus()` and/or `mutateRestockHistory()` to refresh the two read hooks above. If you later want that wrapped in a `useSWRMutation`-style hook, that's a one-line addition on top of what's here.

---

## 4. Fix 3 — Unused Backend Route Audit

**Recommended approach: `include_in_schema=False`, not deletion.** It's a single keyword argument on the existing decorator, requires no import changes, can't break startup (the route is still registered and callable, just hidden from `/docs` and `/openapi.json`), and it's trivially reversible. Deleting the functions is riskier without first confirming nothing else references them (backend tests, the APScheduler jobs, or a curl-based demo script) — the audit table below flags where that risk is real vs. negligible for each route.

| Endpoint | Likely file | Risk if deleted outright | Recommended action |
|---|---|---|---|
| `POST /api/household/{user_id}/rebuild-models` | `backend/api/routes/household.py` | Low-medium — often used as a manual demo/debug trigger even when the frontend doesn't call it directly | Hide from schema, keep the code |
| `POST /api/recipes/parse` | `backend/api/routes/recipes.py` | Medium — recipe-parsing tests commonly exercise this exact route directly | **Grep your test suite before touching this one** (command below) |
| `POST /api/recipes/pin` | `backend/api/routes/recipes.py` | Medium — same reasoning as `/parse` | Grep tests first |
| `GET /api/predictions/` (no user_id) | `backend/api/routes/predictions.py` | Low — typically just an index/health stub | Hide from schema |
| `GET /api/recipes/` (no user_id) | `backend/api/routes/recipes.py` | Low — same pattern | Hide from schema |

### The pattern to apply

Find each route's decorator and add `include_in_schema=False` as a keyword argument — no other line changes needed:

```diff
-@router.post("/{user_id}/rebuild-models")
+@router.post("/{user_id}/rebuild-models", include_in_schema=False)
 async def rebuild_household_models(user_id: str, ...):
     ...
```

```diff
-@router.post("/parse")
+@router.post("/parse", include_in_schema=False)
 async def parse_recipe(...):
     ...
```

```diff
-@router.post("/pin")
+@router.post("/pin", include_in_schema=False)
 async def pin_recipe(...):
     ...
```

```diff
-@router.get("/")
+@router.get("/", include_in_schema=False)
 async def predictions_index():
     ...
```

```diff
-@router.get("/")
+@router.get("/", include_in_schema=False)
 async def recipes_index():
     ...
```

Apply the same one-argument change to whichever of these five decorators actually exist in your `household.py`/`recipes.py`/`predictions.py` — I don't have those three files in front of me in this handoff, so match the decorator signature you actually have rather than copy-pasting these verbatim if the argument order/names differ slightly.

### Before touching `/parse` or `/pin`: check for hidden callers

Run this from your repo root — it catches references from tests, the scheduler, and any leftover frontend code in one pass:

```bash
grep -rn "recipes/parse\|recipes/pin\|rebuild-models" \
  backend/tests/ backend/notifications/ frontend/ --include="*.py" --include="*.ts" --include="*.tsx"
```

- **Zero hits** → safe to also comment out the function body (not just hide from schema) if you want them gone entirely; leave a one-line marker so a future you knows why:
  ```python
  # DISABLED 2026-07-09: unused by frontend, no test coverage found.
  # @router.post("/parse", include_in_schema=False)
  # async def parse_recipe(...):
  #     ...
  ```
- **Any hits** → leave the route active with just `include_in_schema=False`; whatever's calling it still needs it to work, it just doesn't need to show up in your public API docs.

### Why not delete the router include or the whole file

`app.include_router(recipes.router)` in `main.py` should stay untouched regardless — even after hiding/disabling individual routes, other routes in the same file (e.g. `GET /api/recipes/{user_id}`, which your dashboard *does* use via `useRecipes`) still need that router mounted. Removing the whole router would break the working part of the feature, not just the unused part.

---

## 5. Verification Checklist

1. **Type-check the frontend:** `npx tsc --noEmit` from the `frontend/` directory — confirms `APIRestockStatusResponse`/`APIRestockHistoryResponse` compile cleanly and nothing else in the codebase was importing the old `getCart`/`addToCart`/`checkout` methods (if something was, `tsc` will now tell you exactly where, since those methods no longer exist).
2. **Grep for old call sites**, in case something silently referenced the removed cart methods without TypeScript catching it (e.g. inside a `.js` file or dynamic property access):
   ```bash
   grep -rn "restockApi\.\(getCart\|addToCart\|checkout\)" frontend/
   ```
   This should return nothing after the fix; if it returns hits, those call sites need to be pointed at `getStatus`/`checkNow`/`getHistory` before you ship.
3. **Manually hit the three real endpoints** against your running backend to confirm the TS interfaces match the live JSON exactly:
   ```bash
   curl -s http://localhost:8000/api/restock/demo_user_001 | jq
   curl -s -X POST http://localhost:8000/api/restock/demo_user_001/check-now | jq
   curl -s http://localhost:8000/api/restock/demo_user_001/history | jq
   ```
4. **Confirm the OpenAPI schema shrank correctly:** visit `http://localhost:8000/docs` before and after applying `include_in_schema=False` — the five audited routes should disappear from the Swagger UI while `curl`-ing them directly still returns a normal 200, not a 404.
5. **Run the existing backend test suite** (`pytest backend/tests/ -v`) once after the schema-hiding changes — `include_in_schema=False` shouldn't affect any test that calls the route directly (it only affects OpenAPI generation), so this should be a no-op confirmation, not a real risk.
