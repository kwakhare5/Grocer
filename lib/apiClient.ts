/**
 * Type-Safe FastAPI Backend Client for GROCER v2 (Phase 7).
 * Connects Next.js Operations Deck & Customer Replenishment to the FastAPI backend.
 * Provides fallback to simulated state when backend is offline.
 */

// Consumer-facing types only â€” operations types removed in Phase 0 cleanup


const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// ---------------------------------------------------------------------------
// Backend Response Types
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  timestamp: string;
  database: string;
}

export interface BackendStore {
  store_id: string;
  name: string;
  latitude: number;
  longitude: number;
  operating_status: string;
  created_at: string;
}

export interface BackendProduct {
  product_id: string;
  name: string;
  category: string;
  unit: string;
  shelf_life_hours: number;
  base_price: number;
  supplier_id: string;
  created_at: string;
}

export interface BackendInventory {
  inventory_id: string;
  store_id: string;
  product_id: string;
  quantity: number;
  updated_at: string;
}

export interface BackendRisk {
  risk_id: string;
  store_id: string;
  product_id: string;
  risk_type: string;
  severity: string;
  probability: number;
  expected_time: string;
  status: string;
  created_at: string;
}

export interface BackendRecommendation {
  recommendation_id: string;
  risk_id: string;
  action_type: string;
  quantity: number;
  source_store_id?: string | null;
  destination_store_id?: string | null;
  score: number;
  confidence: number;
  reason_codes: string[] | string;
  alternatives: Array<{
    action_type?: string;
    action?: string;
    score: number;
    reason_codes?: string[];
    rejection_codes?: string[];
    reason?: string;
    transfer_quantity?: number;
    reorder_quantity?: number;
  }> | null;
  status: string;
  created_at: string;
}

export interface BackendAgentRunEvent {
  node?: string;
  result?: string;
  action?: string;
  action_id?: string;
  status?: string;
  target_store?: string;
  transfer_id?: string;
  purchase_order_id?: string;
  quantity?: number;
  batches_affected?: Array<{
    batch_id?: string;
    quantity_deducted?: number;
    destination_batch_id?: string;
    quantity_added?: number;
    expires_at?: string;
  }>;
  verification_details?: {
    source_non_negative?: boolean;
    dest_inventory_updated?: boolean;
    batches_balanced?: boolean;
    audit_events_count?: number;
    invariants_satisfied?: boolean;
    [key: string]: unknown;
  };
  error?: string;
  [key: string]: unknown;
}

export interface BackendAgentRun {
  run_id: string;
  recommendation_id: string;
  status: "completed" | "requires_human_review" | "failed";
  action_type?: string | null;
  events: BackendAgentRunEvent[];
  error?: string | null;
  new_recommendation_id?: string | null;
  requires_human_review: boolean;
  started_at: string;
  finished_at: string;
}

export interface BackendSimulation {
  simulation_id: string;
  seed: number;
  current_time: string;
  status: string;
}

export interface BackendCustomerListItem {
  customer_id: string;
  name: string;
  home_store_id: string;
  home_store_name: string;
  staple_count: number;
  critical_staple: string;
  days_left: number;
  fill_pct: number;
  last_order_at?: string | null;
}

export interface BackendCustomerDetail {
  customer_id: string;
  name: string;
  home_store_id: string;
  home_store_name: string;
  staples: Array<{
    id: string;
    name: string;
    category: string;
    daily_rate: number;
    unit: string;
    days_left: number;
    fill_pct: number;
    price: number;
  }>;
}

export interface BackendCustomerMessages {
  customer_id: string;
  customer_name: string;
  home_store_name: string;
  messages: Array<{
    sender: string;
    text: string;
    timestamp: string;
    quick_actions?: string[];
  }>;
}

export interface BackendCustomerMessageResponse {
  reply: string;
  stage: string;
  timestamp: string;
  quick_actions: string[];
}

export interface BackendCustomerReorderResponse {
  order_id: string;
  customer_id: string;
  customer_name: string;
  store_id: string;
  store_name: string;
  items: Array<{
    product_id: string;
    product_name: string;
    quantity: number;
    price: number;
  }>;
  total_amount: number;
  status: string;
  created_at: string;
  pantry_restored: boolean;
  store_inventory_updated: Record<string, number>;
}

export interface BackendCustomerRemindResponse {
  customer_id: string;
  status: string;
  delay_hours: number;
  scheduled_time: string;
  message: string;
}

export interface BackendCustomerSkipResponse {
  customer_id: string;
  status: string;
  reason: string;
  message: string;
}

// ---------------------------------------------------------------------------
// Phase 8: CommercePort & Swiggy Instamart Models
// ---------------------------------------------------------------------------

export interface BackendCommerceAdapterInfo {
  adapter_type: "mock" | "swiggy_mcp" | string;
  endpoint: string;
  mode: string;
}

export interface BackendDeliveryAddress {
  id: string;
  label: string;
  street: string;
  city: string;
  postal_code: string;
  latitude?: number;
  longitude?: number;
  is_serviceable: boolean;
}

export interface BackendCommerceProductVariant {
  spin_id: string;
  name: string;
  pack_size: string;
  price: number;
  mrp: number;
  in_stock: boolean;
}

export interface BackendCommerceProductItem {
  product_id: string;
  name: string;
  category: string;
  variants: BackendCommerceProductVariant[];
  image_url?: string;
}

export interface BackendCommerceCartItem {
  spin_id: string;
  name: string;
  pack_size: string;
  unit_price: number;
  quantity: number;
  total_price: number;
}

export interface BackendCommerceCart {
  cart_id: string;
  address_id?: string;
  items: BackendCommerceCartItem[];
  item_total: number;
  delivery_fee: number;
  packaging_fee: number;
  discount: number;
  grand_total: number;
  is_serviceable: boolean;
}

export interface BackendCommercePaymentOption {
  method: "UPI" | "COD";
  label: string;
  is_available: boolean;
  description?: string;
}

export interface BackendCommerceOrderResult {
  order_id: string;
  cart_id: string;
  status: string;
  items: BackendCommerceCartItem[];
  payment_method: string;
  grand_total: number;
  delivery_address: BackendDeliveryAddress;
  placed_at: string;
  tracking_url?: string;
}

export interface BackendCommerceTracking {
  order_id: string;
  status: "ORDER_CONFIRMED" | "PACKING" | "OUT_FOR_DELIVERY" | "DELIVERED" | string;
  eta_minutes: number;
  driver_name?: string;
  driver_phone?: string;
  last_updated_at: string;
}


// ---------------------------------------------------------------------------
// Store Coordinate & Metadata Map (Mumbai Topography)
// ---------------------------------------------------------------------------

// OPERATIONS RESIDUE — Phase 0 cleanup: used by transformStores which was removed.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const STORE_UI_METADATA: Record<string, { code: string; location: string; x: number; y: number }> = {
  "Andheri East": { code: "St 01", location: "MIDC Cyber Hub, Mumbai", x: 130, y: 110 },
  "Bandra West": { code: "St 02", location: "Hill Road / Turner, Mumbai", x: 90, y: 210 },
  "Powai Galleria": { code: "St 03", location: "Hiranandani Gardens, Mumbai", x: 210, y: 100 },
  "Dadar / Lower Parel": { code: "St 04", location: "Senapati Bapat Marg, Mumbai", x: 120, y: 290 },
  "Thane West": { code: "St 05", location: "Ghodbunder Road, Mumbai", x: 240, y: 40 },
};


// ---------------------------------------------------------------------------
// API Client Functions
// ---------------------------------------------------------------------------

async function safeFetch<T>(endpoint: string, options?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers || {}),
      },
    });
    if (!res.ok) {
      return null;
    }
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export const grocerApi = {
  /** Check if FastAPI backend is healthy and responding */
  async checkHealth(): Promise<boolean> {
    const data = await safeFetch<HealthResponse>("/api/health");
    return data !== null && data.status === "ok";
  },

  // -------------------------------------------------------------------------
  // OPERATIONS RESIDUE REMOVED — Phase 0 boundary cleanup
  // The following methods called operations-only routes that are now decoupled:
  //   getActiveSimulation, getStores, getProducts, getRisks, evaluateRisks,
  //   getRecommendations, evaluateRecommendation, approveRecommendation,
  //   rejectRecommendation, executeAgent, getAgentRun, getAgentRuns,
  //   advanceSimulation, resetSimulation
  // Source: GROCER_V2_MASTER_SPEC.md §19
  // -------------------------------------------------------------------------

  /** Fetch all customers */
  async getCustomers(): Promise<BackendCustomerListItem[] | null> {
    return safeFetch<BackendCustomerListItem[]>("/api/customers");
  },

  /** Fetch single customer detail */
  async getCustomer(customerId: string): Promise<BackendCustomerDetail | null> {
    return safeFetch<BackendCustomerDetail>(`/api/customers/${customerId}`);
  },

  /** Fetch customer messages */
  async getCustomerMessages(customerId: string): Promise<BackendCustomerMessages | null> {
    return safeFetch<BackendCustomerMessages>(`/api/customers/${customerId}/messages`);
  },

  /** Send customer message */
  async sendCustomerMessage(
    customerId: string,
    message: string
  ): Promise<BackendCustomerMessageResponse | null> {
    return safeFetch<BackendCustomerMessageResponse>(`/api/customers/${customerId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
  },

  /** Execute customer reorder */
  async reorderCustomer(
    customerId: string,
    items?: Array<{ product_id: string; quantity: number }>
  ): Promise<BackendCustomerReorderResponse | null> {
    return safeFetch<BackendCustomerReorderResponse>(`/api/customers/${customerId}/reorder`, {
      method: "POST",
      body: items ? JSON.stringify({ items }) : undefined,
    });
  },

  /** Schedule customer restock reminder */
  async remindCustomer(
    customerId: string,
    delayHours = 24
  ): Promise<BackendCustomerRemindResponse | null> {
    return safeFetch<BackendCustomerRemindResponse>(`/api/customers/${customerId}/remind`, {
      method: "POST",
      body: JSON.stringify({ delay_hours: delayHours }),
    });
  },

  /** Record customer skip decision */
  async skipCustomer(
    customerId: string,
    reason?: string
  ): Promise<BackendCustomerSkipResponse | null> {
    return safeFetch<BackendCustomerSkipResponse>(`/api/customers/${customerId}/skip`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  // -------------------------------------------------------------------------
  // Phase 8: CommercePort & Swiggy Instamart Methods
  // -------------------------------------------------------------------------

  /** Fetch active commerce adapter info */
  async getCommerceAdapterInfo(): Promise<BackendCommerceAdapterInfo | null> {
    return safeFetch<BackendCommerceAdapterInfo>("/api/customers/adapter-info");
  },

  /** Fetch saved customer delivery addresses */
  async getCustomerAddresses(customerId: string): Promise<BackendDeliveryAddress[] | null> {
    return safeFetch<BackendDeliveryAddress[]>(`/api/customers/${customerId}/addresses`);
  },

  /** Fetch quick reorder staples for address */
  async getCustomerGoToItems(
    customerId: string,
    addressId?: string
  ): Promise<BackendCommerceProductItem[] | null> {
    const query = addressId ? `?address_id=${addressId}` : "";
    return safeFetch<BackendCommerceProductItem[]>(`/api/customers/${customerId}/go-to-items${query}`);
  },

  /** Search products available at customer address */
  async searchCustomerProducts(
    customerId: string,
    query: string,
    addressId?: string
  ): Promise<BackendCommerceProductItem[] | null> {
    const params = new URLSearchParams({ query });
    if (addressId) params.append("address_id", addressId);
    return safeFetch<BackendCommerceProductItem[]>(`/api/customers/${customerId}/products?${params.toString()}`);
  },

  /** Fetch active customer cart */
  async getCustomerCart(
    customerId: string,
    cartId?: string
  ): Promise<BackendCommerceCart | null> {
    const query = cartId ? `?cart_id=${cartId}` : "";
    return safeFetch<BackendCommerceCart>(`/api/customers/${customerId}/cart${query}`);
  },

  /** Update items in customer cart */
  async updateCustomerCart(
    customerId: string,
    items: { spin_id: string; quantity: number }[],
    addressId?: string,
    cartId?: string
  ): Promise<BackendCommerceCart | null> {
    const query = cartId ? `?cart_id=${cartId}` : "";
    return safeFetch<BackendCommerceCart>(`/api/customers/${customerId}/cart${query}`, {
      method: "POST",
      body: JSON.stringify({ items, address_id: addressId }),
    });
  },

  /** Clear customer cart */
  async clearCustomerCart(customerId: string, cartId?: string): Promise<{ cleared: boolean } | null> {
    const query = cartId ? `?cart_id=${cartId}` : "";
    return safeFetch<{ cleared: boolean }>(`/api/customers/${customerId}/cart${query}`, {
      method: "DELETE",
    });
  },

  /** Fetch payment options */
  async getCustomerPaymentOptions(
    customerId: string,
    cartId?: string
  ): Promise<BackendCommercePaymentOption[] | null> {
    const query = cartId ? `?cart_id=${cartId}` : "";
    return safeFetch<BackendCommercePaymentOption[]>(`/api/customers/${customerId}/payment-options${query}`);
  },

  /** Consequential checkout requiring explicit confirmation */
  async checkoutCustomer(
    customerId: string,
    payload: { payment_method?: string; explicit_confirmation: boolean; address_id?: string },
    cartId?: string
  ): Promise<BackendCommerceOrderResult | null> {
    const query = cartId ? `?cart_id=${cartId}` : "";
    return safeFetch<BackendCommerceOrderResult>(`/api/customers/${customerId}/checkout${query}`, {
      method: "POST",
      body: JSON.stringify({
        payment_method: payload.payment_method || "UPI",
        explicit_confirmation: payload.explicit_confirmation,
        address_id: payload.address_id,
      }),
    });
  },

  /** Track live order delivery status and ETA */
  async trackCustomerOrder(
    customerId: string,
    orderId: string
  ): Promise<BackendCommerceTracking | null> {
    return safeFetch<BackendCommerceTracking>(`/api/customers/${customerId}/orders/${orderId}/track`);
  },
};

// ---------------------------------------------------------------------------
// OPERATIONS RESIDUE REMOVED — Phase 0 boundary cleanup
// The following functions were removed because they depend on DarkStore/RecommendationItem
// which are operations types not part of the GROCER v2 consumer boundary:
//   - transformStores(backendStores, risks) -> DarkStore[]
//   - transformRecommendation(rec, stores, products, risks) -> RecommendationItem
//   - createSyntheticAgentRun(rec) -> BackendAgentRun
// Source: GROCER_V2_MASTER_SPEC.md §19
// ---------------------------------------------------------------------------
