import useSWR from "swr";
import {
  predictionsApi,
  ordersApi,
  householdApi,
  recipesApi,
  pricesApi,
  restockApi,
  APIPredictionsResponse,
  APIOrdersResponse,
  APIHouseholdProfile,
  APIRecipesResponse,
  APIPriceFeedItem,
  APIPriceAlertsResponse,
  APIRestockStatusResponse,
  APIRestockHistoryResponse
} from "./api";

// Fetchers
const fetchPredictions = (userId: string) => predictionsApi.getForHousehold(userId).then(res => res.data);
const fetchOrders = (userId: string) => ordersApi.getOrders(userId).then(res => res.data);
const fetchProfile = (userId: string) => householdApi.getProfile(userId).then(res => res.data);
const fetchRecipes = (userId: string) => recipesApi.getForHousehold(userId).then(res => res.data);
const fetchPricesFeed = () => pricesApi.getFeed().then(res => res.data);
const fetchPricesAlerts = () => pricesApi.getAlerts().then(res => res.data);
const fetchRestockStatus = (userId: string) => restockApi.getStatus(userId).then(res => res.data);
const fetchRestockHistory = (userId: string) => restockApi.getHistory(userId).then(res => res.data);


// Custom Hooks
export function usePredictions(userId: string = "demo_user_001") {
  const { data, error, isLoading, mutate } = useSWR<APIPredictionsResponse>(
    `/api/predictions/${userId}`,
    () => fetchPredictions(userId),
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  return {
    predictionsData: data,
    isLoading,
    isError: error,
    mutatePredictions: mutate
  };
}

export function useOrders(userId: string = "demo_user_001") {
  const { data, error, isLoading, mutate } = useSWR<APIOrdersResponse>(
    `/api/orders/${userId}`,
    () => fetchOrders(userId),
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  return {
    ordersData: data,
    isLoading,
    isError: error,
    mutateOrders: mutate
  };
}

export function useHouseholdProfile(userId: string = "demo_user_001") {
  const { data, error, isLoading, mutate } = useSWR<APIHouseholdProfile>(
    `/api/household/${userId}`,
    () => fetchProfile(userId),
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  return {
    profileData: data,
    isLoading,
    isError: error,
    mutateProfile: mutate
  };
}

export function useRecipes(userId: string = "demo_user_001") {
  const { data, error, isLoading, mutate } = useSWR<APIRecipesResponse>(
    `/api/recipes/${userId}`,
    () => fetchRecipes(userId),
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  return {
    recipesData: data,
    isLoading,
    isError: error,
    mutateRecipes: mutate
  };
}

export function usePricesFeed() {
  const { data, error, isLoading, mutate } = useSWR<APIPriceFeedItem[]>(
    "/api/prices/feed",
    fetchPricesFeed,
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  return {
    feedData: data,
    isLoading,
    isError: error,
    mutateFeed: mutate
  };
}

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

export function useRestockStatus(userId: string = "demo_user_001") {
  const { data, error, isLoading, mutate } = useSWR<APIRestockStatusResponse>(
    `/api/restock/${userId}`,
    () => fetchRestockStatus(userId),
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  return {
    restockStatusData: data,
    isLoading,
    isError: error,
    mutateRestockStatus: mutate
  };
}

export function useRestockHistory(userId: string = "demo_user_001") {
  const { data, error, isLoading, mutate } = useSWR<APIRestockHistoryResponse>(
    `/api/restock/${userId}/history`,
    () => fetchRestockHistory(userId),
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  return {
    restockHistoryData: data,
    isLoading,
    isError: error,
    mutateRestockHistory: mutate
  };
}

