import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
});

export interface APIHouseholdProfile {
  id: string;
  user_id: string;
  phone_number: string | null;
  composition: string;
  composition_confidence: number | null;
  intelligence_consent: boolean;
  notifications_enabled: boolean;
  created_at: string | null;
}

export interface APIPrediction {
  item_id: string;
  item_name: string;
  category: string;
  avg_daily_consumption: number;
  consumption_cycle_days: number;
  last_purchase_date: string | null;
  last_purchase_quantity: number;
  estimated_depletion_date: string | null;
  days_remaining: number | null;
  stock_fill_percent?: number;
  confidence_score: number;
  data_points: number;
  status: 'depleted' | 'critical' | 'low' | 'ok' | 'unknown';
  updated_at: string | null;
}

export interface APIPredictionsResponse {
  user_id: string;
  household_id: string;
  total_items: number;
  predictions: APIPrediction[];
  generated_at: string;
}

export interface APIRecipe {
  id: string;
  name: string;
  servings: number;
  ingredients: {
    name: string;
    needed: string;
    status: 'have' | 'low' | 'missing';
    estimated?: string;
    price?: number;
  }[];
  cuisine: string | null;
  pinned_for: string | null;
  created_at: string | null;
}

export interface APIRecipesResponse {
  user_id: string;
  household_id: string;
  total: number;
  recipes: APIRecipe[];
}

export interface APIPriceFeedItem {
  id: string;
  item_id: string;
  name: string;
  unit: string;
  current: number;
  avg30d: number;
  signal: 'SPIKE' | 'DIP' | 'WATCH' | 'STABLE';
  suggestion: string | null;
  history: { day: string; price: number }[];
}

export interface APIPriceAlertsResponse {
  alerts: APIPriceFeedItem[];
}

// ---------------------------------------------------------------------------
// Restock — matches backend/api/routes/restock.py exactly (3 endpoints,
// no cart/checkout endpoints exist on the backend).
// ---------------------------------------------------------------------------

export interface APIRestockItem {
  item_id: string;
  item_name: string;
  category: string;
  confidence_score: number;
  confidence_label: string;
  avg_daily_consumption: number;
  estimated_depletion_date: string;
  days_remaining: number;
  last_purchase_date: string | null;
}

export interface APIRestockStatusResponse {
  user_id: string;
  household_id: string;
  threshold_days: number;
  min_confidence: number;
  depleting_count: number;
  depleting_items: APIRestockItem[];
}

export interface APIRestockCheckSummaryItem {
  name: string;
  days_remaining: number;
  confidence: string;
}

export interface APIRestockCheckResponse {
  alerts_triggered: number;
  alert_id?: string;
  message: string;
  whatsapp_preview?: string;
  items: APIRestockCheckSummaryItem[];
}

export interface APIRestockAlert {
  id: string;
  item_ids: string[] | null;
  message: string;
  sent_at: string | null;
  status: 'pending' | 'sent' | 'acted' | 'dismissed';
  acted_at: string | null;
}

export interface APIRestockHistoryResponse {
  user_id: string;
  alerts: APIRestockAlert[];
}

export const householdApi = {
  sync: (userId: string) => api.post<{ message: string; household_id: string }>(`/api/household/${userId}/sync`),
  getProfile: (userId: string) => api.get<APIHouseholdProfile>(`/api/household/${userId}`),
  switchScenario: (userId: string, scenario: string) => api.post<{ success: boolean; message: string }>(`/api/household/${userId}/scenario`, { scenario }),
};

export const predictionsApi = {
  getForHousehold: (householdId: string) => api.get<APIPredictionsResponse>(`/api/predictions/${householdId}`),
};

export const recipesApi = {
  getForHousehold: (userId: string) => api.get<APIRecipesResponse>(`/api/recipes/${userId}`),
};

export const pricesApi = {
  getFeed: () => api.get<APIPriceFeedItem[]>('/api/prices/feed'),
  getAlerts: () => api.get<APIPriceAlertsResponse>('/api/prices/alerts'),
};

export interface APIOrder {
  order_id: string;
  placed_at: string;
  total: number;
  status: string;
  platform?: string;
  items: { item_name: string; quantity: number; price: number }[];
}

export interface APIOrdersResponse {
  user_id: string;
  total: number;
  orders: APIOrder[];
}

export const ordersApi = {
  getOrders: (userId: string, limit: number = 30) => api.get<APIOrdersResponse>(`/api/orders/${userId}?limit=${limit}`),
};

export const restockApi = {
  /** GET /api/restock/{user_id} — read-only depletion status, no side effects. */
  getStatus: (userId: string) =>
    api.get<APIRestockStatusResponse>(`/api/restock/${userId}`),

  /** POST /api/restock/{user_id}/check-now — triggers a check, persists a RestockAlert. */
  checkNow: (userId: string) =>
    api.post<APIRestockCheckResponse>(`/api/restock/${userId}/check-now`),

  /** GET /api/restock/{user_id}/history?limit= — last N RestockAlert records. */
  getHistory: (userId: string, limit: number = 20) =>
    api.get<APIRestockHistoryResponse>(`/api/restock/${userId}/history?limit=${limit}`),
};

export default api;
