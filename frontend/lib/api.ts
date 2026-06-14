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

export const householdApi = {
  sync: (userId: string) => api.post<{ message: string; household_id: string }>(`/api/household/${userId}/sync`),
  getProfile: (userId: string) => api.get<APIHouseholdProfile>(`/api/household/${userId}`),
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

export default api;
