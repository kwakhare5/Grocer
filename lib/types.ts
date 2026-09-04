import type { LucideIcon } from "lucide-react";

// ---------------------------------------------------------------------------
// 1. Customer & Pantry Types
// ---------------------------------------------------------------------------

export interface StapleItem {
  id: string;
  name: string;
  days: number;
  fillPct: number;
  avg: string;
  icon: LucideIcon;
  category: string;
}

export interface WhatsAppMessage {
  sender: "bot" | "user";
  text: string;
  timestamp: string;
}

export interface CustomerPersona {
  id: string;
  name: string;
  homeStoreCode: string;
  homeStoreName: string;
  address: string;
  avatar: string;
  householdSize: number;
  orderFrequencyDays: number;
  primaryDepletionItem: string;
}

export interface CustomerOrderItem {
  productId: string;
  productName: string;
  quantity: number;
  priceINR: number;
}

export interface CustomerOrderPayload {
  customerId: string;
  customerName: string;
  homeStoreCode: string;
  homeStoreName: string;
  items: CustomerOrderItem[];
  totalINR: number;
  paymentMethod: "UPI" | "COD";
}

export interface PhoneMockupProps {
  className?: string;
  activeScenario?: string;
  initialViewMode?: "whatsapp";
  activeCustomer?: CustomerPersona;
  onCustomerChange?: (customer: CustomerPersona) => void;
  onPlaceOrder?: (payload: CustomerOrderPayload) => void;
  onScheduleReminder?: (customerId: string, delayHours: number) => void;
  onSkipRestock?: (customerId: string, reason?: string) => void;
}

// ---------------------------------------------------------------------------
// 2. Dark Store Network & Operations Fleet Types
// ---------------------------------------------------------------------------

export type RiskSeverity = "critical" | "warning" | "low";
export type ActionType = "transfer" | "reorder" | "discount" | "hold";
export type ActionStatus = "pending" | "approved" | "executing" | "completed" | "rejected" | "failed";

export interface DarkStore {
  id: string;
  code: string;
  name: string;
  location: string;
  lat: number;
  lng: number;
  x: number; // SVG canvas coordinate
  y: number; // SVG canvas coordinate
  status: "active" | "maintenance" | "critical";
  totalSkus: number;
  activeBatches: number;
  stockoutRiskCount: number;
  spoilageRiskCount: number;
  excessCapacityUnits: number;
  inventoryHealth: {
    dairy: number; // 0-100%
    produce: number;
    bakery: number;
    staples: number;
    packaged: number;
  };
}

// ---------------------------------------------------------------------------
// 3. Recommendation & Decision Stream Types
// ---------------------------------------------------------------------------

export interface RecommendationAlternative {
  action: ActionType;
  label: string;
  score: number;
  reason: string;
  isRecommended?: boolean;
}

export interface RecommendationItem {
  id: string;
  riskId: string;
  title: string;
  productName: string;
  productCategory: string;
  sourceStore?: {
    id: string;
    code: string;
    name: string;
    safeExcess: number;
  };
  destinationStore: {
    id: string;
    code: string;
    name: string;
  };
  actionType: ActionType;
  severity: RiskSeverity;
  status: ActionStatus;
  quantity: number;
  unit: string;
  distanceKm?: number;
  stockoutInHours: number;
  supplierEtaHours: number;
  probability: number;
  confidence: number;
  discountPct?: number;
  reasonCodes: string[];
  alternatives: RecommendationAlternative[];
  tradeoffAnalysis: {
    spoilageAvoidanceINR: number;
    transportCostINR: number;
    stockoutLossAvoidedINR: number;
    netBenefitINR: number;
  };
  createdAt: string;
}

// ---------------------------------------------------------------------------
// 4. Simulation Engine & Telemetry Event Types
// ---------------------------------------------------------------------------

export interface SimulationEvent {
  id: string;
  timestamp: string;
  type:
    | "ORDER_CREATED"
    | "INVENTORY_UPDATED"
    | "FORECAST_UPDATED"
    | "RISK_DETECTED"
    | "RECOMMENDATION_CREATED"
    | "HUMAN_APPROVED"
    | "ACTION_EXECUTING"
    | "TRANSFER_COMPLETED"
    | "ORDER_CONFIRMED"
    | "BATCH_EXPIRED"
    | "EXECUTION_FAILED"
    | "SCENARIO_STEP";
  description: string;
  storeCode?: string;
  severity?: "critical" | "warning" | "info" | "success";
}

export interface SimulationState {
  isRunning: boolean;
  currentDay: number;
  currentHour: number;
  activeScenario: string;
  totalOrdersDelivered: number;
  wasteAvoidedINR: number;
  stockoutMitigatedCount: number;
  avgTransferTimeMinutes: number;
}

export interface SimulationMetrics {
  stockoutEvents: number;
  spoiledUnits: number;
  emergencyReorders: number;
  serviceLevel: number; // 0-100%
  excessInventory: number;
  transferCount: number;
  estimatedWasteCostINR: number;
  recommendationAcceptanceRate: number; // 0-100%
}

export interface ScenarioState {
  activeScenarioId: string | null;
  currentStep: number;
  totalSteps: number;
  isAutoPlaying: boolean;
  isComplete: boolean;
  seed: number;
  grocerMetrics: SimulationMetrics;
  baselineMetrics: SimulationMetrics;
}
