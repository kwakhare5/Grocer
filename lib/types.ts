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
  address?: string;
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
// OPERATIONS RESIDUE REMOVED — Phase 0 boundary cleanup
// The following types were removed because they belong to the dark-store
// operations product (kwakhare5/Dark-store-operator), not GROCER v2 consumer:
//   - RiskSeverity, ActionType, ActionStatus
//   - DarkStore (including inventoryHealth)
//   - RecommendationItem, RecommendationAlternative
//   - SimulationEvent, SimulationState, SimulationMetrics, ScenarioState
// Source: GROCER_V2_MASTER_SPEC.md §19
// ---------------------------------------------------------------------------
