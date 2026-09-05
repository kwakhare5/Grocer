/**
 * Type-Safe FastAPI Backend Client for GROCER v2 (Phase 7).
 * Connects Next.js Operations Deck & Customer Replenishment to the FastAPI backend.
 * Provides fallback to simulated state when backend is offline.
 */

import { DarkStore, RecommendationItem, ActionType, RiskSeverity, ActionStatus } from "./types";

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
// Store Coordinate & Metadata Map (Mumbai Topography)
// ---------------------------------------------------------------------------

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

  /** Fetch active simulation from backend (or auto-initialize default) */
  async getActiveSimulation(): Promise<BackendSimulation | null> {
    return safeFetch<BackendSimulation>("/api/simulations/active");
  },

  /** Fetch all stores from backend */
  async getStores(): Promise<BackendStore[] | null> {
    return safeFetch<BackendStore[]>("/api/stores");
  },

  /** Fetch all products from backend */
  async getProducts(): Promise<BackendProduct[] | null> {
    return safeFetch<BackendProduct[]>("/api/products");
  },

  /** Fetch active risks */
  async getRisks(status = "active"): Promise<BackendRisk[] | null> {
    return safeFetch<BackendRisk[]>(`/api/risks?status=${status}`);
  },

  /** Trigger risk evaluation */
  async evaluateRisks(): Promise<{ active_risks_count: number } | null> {
    return safeFetch<{ active_risks_count: number }>("/api/risks/evaluate", {
      method: "POST",
    });
  },

  /** Fetch recommendations */
  async getRecommendations(status?: string): Promise<BackendRecommendation[] | null> {
    const query = status ? `?status=${status}` : "";
    return safeFetch<BackendRecommendation[]>(`/api/recommendations${query}`);
  },

  /** Trigger recommendation evaluation for a specific risk */
  async evaluateRecommendation(riskId: string): Promise<BackendRecommendation | null> {
    return safeFetch<BackendRecommendation>(`/api/recommendations/evaluate/${riskId}`, {
      method: "POST",
    });
  },

  /** Approve a recommendation (spec §18 LOCKED human approval) */
  async approveRecommendation(recommendationId: string): Promise<{ recommendation_id: string; status: string } | null> {
    return safeFetch<{ recommendation_id: string; status: string }>(
      `/api/recommendations/${recommendationId}/approve`,
      { method: "POST" }
    );
  },

  /** Reject a recommendation */
  async rejectRecommendation(recommendationId: string): Promise<{ recommendation_id: string; status: string } | null> {
    return safeFetch<{ recommendation_id: string; status: string }>(
      `/api/recommendations/${recommendationId}/reject`,
      { method: "POST" }
    );
  },

  /** Execute transfer execution pipeline for an APPROVED recommendation (spec §19–21) */
  async executeAgent(recommendationId: string): Promise<BackendAgentRun | null> {
    return safeFetch<BackendAgentRun>(`/api/agent/execute/${recommendationId}`, {
      method: "POST",
    });
  },

  /** Get agent run status */
  async getAgentRun(runId: string): Promise<{ run_id: string; status: string } | null> {
    return safeFetch<{ run_id: string; status: string }>(`/api/agent/runs/${runId}`);
  },

  /** Fetch recent agent runs from backend (Phase 7) */
  async getAgentRuns(): Promise<BackendAgentRun[] | null> {
    return safeFetch<BackendAgentRun[]>("/api/agent/runs");
  },

  /** Advance simulation clock by N hours */
  async advanceSimulation(simulationId: string, hours: number): Promise<BackendSimulation | null> {
    return safeFetch<BackendSimulation>(`/api/simulations/${simulationId}/advance`, {
      method: "POST",
      body: JSON.stringify({ hours }),
    });
  },

  /** Reset simulation */
  async resetSimulation(simulationId: string): Promise<BackendSimulation | null> {
    return safeFetch<BackendSimulation>(`/api/simulations/${simulationId}/reset`, {
      method: "POST",
    });
  },

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
};

// ---------------------------------------------------------------------------
// Transformers: Backend Models -> UI View Models
// ---------------------------------------------------------------------------

export function transformStores(
  backendStores: BackendStore[],
  risks: BackendRisk[] = []
): DarkStore[] {
  return backendStores.map((bs, idx) => {
    const meta = STORE_UI_METADATA[bs.name] || {
      code: `St 0${idx + 1}`,
      location: "Mumbai Dark Store",
      x: 100 + (idx % 3) * 60,
      y: 80 + Math.floor(idx / 3) * 90,
    };

    const storeRisks = risks.filter((r) => r.store_id === bs.store_id);
    const stockoutCount = storeRisks.filter((r) => r.risk_type.toLowerCase() === "stockout").length;
    const spoilageCount = storeRisks.filter((r) => r.risk_type.toLowerCase() === "spoilage").length;

    const hasCritical = storeRisks.some((r) => r.severity.toLowerCase() === "critical");
    const status: "active" | "maintenance" | "critical" =
      bs.operating_status.toLowerCase() === "maintenance"
        ? "maintenance"
        : hasCritical
        ? "critical"
        : "active";

    return {
      id: bs.store_id,
      code: meta.code,
      name: bs.name,
      location: meta.location,
      lat: bs.latitude,
      lng: bs.longitude,
      x: meta.x,
      y: meta.y,
      status,
      totalSkus: 25,
      activeBatches: 30 + (idx * 4) % 15,
      stockoutRiskCount: stockoutCount,
      spoilageRiskCount: spoilageCount,
      excessCapacityUnits: Math.max(10, 60 - stockoutCount * 20),
      inventoryHealth: {
        dairy: Math.max(20, 95 - stockoutCount * 35),
        produce: 80,
        bakery: 85,
        staples: 92,
        packaged: 96,
      },
    };
  });
}

export function transformRecommendation(
  rec: BackendRecommendation,
  stores: DarkStore[],
  products: BackendProduct[],
  risks: BackendRisk[] = []
): RecommendationItem {
  const risk = risks.find((r) => r.risk_id === rec.risk_id);
  const product = products.find((p) => p.product_id === (risk?.product_id || ""));
  const destStore = stores.find((s) => s.id === rec.destination_store_id) || {
    id: rec.destination_store_id || "st-04",
    code: "St 04",
    name: "Destination Dark Store",
  };
  const srcStore = rec.source_store_id
    ? stores.find((s) => s.id === rec.source_store_id) || {
        id: rec.source_store_id,
        code: "St 02",
        name: "Source Dark Store",
      }
    : undefined;

  const actionType = (rec.action_type.toLowerCase() as ActionType) || "hold";
  const severity: RiskSeverity =
    risk?.severity.toLowerCase() === "critical"
      ? "critical"
      : risk?.severity.toLowerCase() === "warning"
      ? "warning"
      : "low";

  const rawReasonCodes = Array.isArray(rec.reason_codes)
    ? rec.reason_codes
    : typeof rec.reason_codes === "string"
    ? [rec.reason_codes]
    : [];

  const alternatives = (rec.alternatives || []).map((alt) => {
    const act = ((alt.action_type || alt.action || "hold").toLowerCase() as ActionType);
    return {
      action: act,
      label: act.toUpperCase(),
      score: alt.score || 0,
      reason:
        alt.reason ||
        (alt.rejection_codes && alt.rejection_codes.length > 0
          ? alt.rejection_codes.join(", ")
          : alt.reason_codes?.join(", ") || "Alternative candidate"),
      isRecommended: act === actionType,
    };
  });

  const title =
    actionType === "transfer"
      ? `Transfer ${rec.quantity} units to ${destStore.name}`
      : actionType === "reorder"
      ? `Reorder ${rec.quantity} units from supplier`
      : actionType === "discount"
      ? `Apply 20% discount on ${product?.name || "Inventory"}`
      : `Hold stock for ${destStore.name}`;

  return {
    id: rec.recommendation_id,
    riskId: rec.risk_id,
    title,
    productName: product?.name || "Amul Taaza Milk 1L",
    productCategory: product?.category || "Dairy",
    sourceStore: srcStore
      ? {
          id: srcStore.id,
          code: srcStore.code,
          name: srcStore.name,
          safeExcess: 25,
        }
      : undefined,
    destinationStore: {
      id: destStore.id,
      code: destStore.code,
      name: destStore.name,
    },
    actionType,
    severity,
    status: (rec.status.toLowerCase() as ActionStatus) || "pending",
    quantity: rec.quantity,
    unit: product?.unit || "units",
    distanceKm: 2.1,
    stockoutInHours: 14,
    supplierEtaHours: 30,
    probability: risk?.probability || 0.85,
    confidence: rec.confidence,
    discountPct: actionType === "discount" ? 20 : undefined,
    reasonCodes: rawReasonCodes,
    alternatives,
    tradeoffAnalysis: {
      spoilageAvoidanceINR: actionType === "discount" ? 2800 : 0,
      transportCostINR: actionType === "transfer" ? 45 : 0,
      stockoutLossAvoidedINR: actionType === "transfer" || actionType === "reorder" ? 1850 : 0,
      netBenefitINR: actionType === "transfer" ? 1805 : actionType === "discount" ? 2800 : 850,
    },
    createdAt: rec.created_at || new Date().toISOString(),
  };
}

/**
 * Generates an authoritative client-side LangGraph 5-node synthetic trace (Phase 7).
 * Used when the FastAPI backend is offline to provide realistic execution feedback.
 */
export function createSyntheticAgentRun(rec: RecommendationItem): BackendAgentRun {
  const runId = `run-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
  const now = new Date();
  const startedAt = new Date(now.getTime() - 540).toISOString();
  const finishedAt = now.toISOString();

  const isTransfer = rec.actionType === "transfer";
  const isReorder = rec.actionType === "reorder";

  const events: BackendAgentRunEvent[] = [
    {
      node: "validate",
      result: "valid",
      action_id: `act-${rec.id.slice(0, 8)}`,
      status: "executing",
      recommendation_id: rec.id,
      action_type: rec.actionType,
      target_store: rec.destinationStore.code,
    },
    {
      node: "execute",
      action: rec.actionType,
      transfer_id: isTransfer ? `tr-${Date.now().toString(36)}` : undefined,
      purchase_order_id: isReorder ? `po-${Date.now().toString(36)}` : undefined,
      batches_affected: isTransfer
        ? [
            {
              batch_id: `batch-src-${rec.sourceStore?.code || "01"}-a`,
              quantity_deducted: Math.min(rec.quantity, 15),
              destination_batch_id: `batch-dst-${rec.destinationStore.code}-x`,
              quantity_added: Math.min(rec.quantity, 15),
              expires_at: new Date(Date.now() + 48 * 3600 * 1000).toISOString(),
            },
            ...(rec.quantity > 15
              ? [
                  {
                    batch_id: `batch-src-${rec.sourceStore?.code || "01"}-b`,
                    quantity_deducted: rec.quantity - 15,
                    destination_batch_id: `batch-dst-${rec.destinationStore.code}-y`,
                    quantity_added: rec.quantity - 15,
                    expires_at: new Date(Date.now() + 72 * 3600 * 1000).toISOString(),
                  },
                ]
              : []),
          ]
        : [
            {
              batch_id: `batch-po-${rec.destinationStore.code}-fresh`,
              quantity_added: rec.quantity,
              expires_at: new Date(Date.now() + 120 * 3600 * 1000).toISOString(),
            },
          ],
      quantity: rec.quantity,
    },
    {
      node: "verify",
      result: "verified",
      verification_details: {
        source_non_negative: true,
        dest_inventory_updated: true,
        batches_balanced: true,
        audit_events_count: 2,
        invariants_satisfied: true,
      },
    },
    {
      node: "finalize",
      result: "action completed",
      executed_at: finishedAt,
      status: "completed",
    },
  ];

  return {
    run_id: runId,
    recommendation_id: rec.id,
    status: "completed",
    action_type: rec.actionType,
    events,
    error: null,
    new_recommendation_id: null,
    requires_human_review: false,
    started_at: startedAt,
    finished_at: finishedAt,
  };
}
