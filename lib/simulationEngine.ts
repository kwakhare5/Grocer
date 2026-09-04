import { DEFAULT_PANTRY_STAPLES, ICON_MAP } from "./mockData";
import { StapleItem } from "./types";

export interface SimulationState {
  isRestocked: boolean;
  scenario?: string;
  orderCount: number;
}

/**
 * Calculates current pantry depletion levels based on consumption velocity and household state.
 */
export function getSimulatedPantryStaples(isRestocked: boolean, scenario?: string): StapleItem[] {
  if (isRestocked) {
    return DEFAULT_PANTRY_STAPLES.map((item) => ({
      id: item.id,
      name: item.name,
      days: 14,
      fillPct: 100,
      avg: `${item.dailyRate}${item.unit}/day`,
      icon: ICON_MAP[item.iconName] || ICON_MAP.milk,
      category: item.category,
    }));
  }

  if (scenario === "party") {
    return DEFAULT_PANTRY_STAPLES.map((item) => {
      const isFastDepletion = item.category === "dairy" || item.category === "produce";
      const days = isFastDepletion ? 0.5 : item.defaultDays;
      const fillPct = isFastDepletion ? 8 : item.defaultFillPct;
      return {
        id: item.id,
        name: item.name,
        days: Math.round(days * 10) / 10,
        fillPct,
        avg: `${(item.dailyRate * (isFastDepletion ? 2.5 : 1)).toFixed(2)}${item.unit}/day`,
        icon: ICON_MAP[item.iconName] || ICON_MAP.milk,
        category: item.category,
      };
    });
  }

  if (scenario === "vacation") {
    return DEFAULT_PANTRY_STAPLES.map((item) => ({
      id: item.id,
      name: item.name,
      days: item.defaultDays + 7,
      fillPct: Math.min(100, item.defaultFillPct + 30),
      avg: `${item.dailyRate}${item.unit}/day (Travel Gap Filtered)`,
      icon: ICON_MAP[item.iconName] || ICON_MAP.milk,
      category: item.category,
    }));
  }

  return DEFAULT_PANTRY_STAPLES.map((item) => ({
    id: item.id,
    name: item.name,
    days: item.defaultDays,
    fillPct: item.defaultFillPct,
    avg: `${item.dailyRate}${item.unit}/day`,
    icon: ICON_MAP[item.iconName] || ICON_MAP.milk,
    category: item.category,
  }));
}

/**
 * Pure TypeScript 5-Node Execution Pipeline for WhatsApp messages.
 */
export function processWhatsAppSimulationMessage(
  userText: string,
  stage: "initial" | "item_added" | "breakdown" | "confirmed" | "reminded" | "skipped",
  customerName = "Karan",
  primaryItem = "Amul Taaza Milk 1L"
): {
  reply: string;
  nextStage: "initial" | "item_added" | "breakdown" | "confirmed" | "reminded" | "skipped";
  restockPantry: boolean;
  isReminder?: boolean;
  isSkip?: boolean;
} {
  const normalized = userText.trim().toLowerCase();

  // Remind Later
  if (normalized.includes("remind") || normalized.includes("later") || normalized.includes("tomorrow")) {
    return {
      reply: `Restock reminder scheduled. We will alert you tomorrow at 08:00 AM before breakfast.`,
      nextStage: "reminded",
      restockPantry: false,
      isReminder: true,
    };
  }

  // Skip This Week
  if (normalized.includes("skip") || normalized.includes("pause") || normalized.includes("cancel")) {
    return {
      reply: `Understood, ${customerName}. Restock alert paused for this cycle. Household consumption forecast has been updated.`,
      nextStage: "skipped",
      restockPantry: false,
      isSkip: true,
    };
  }

  // YES / Confirm action
  if (normalized === "yes" || normalized.includes("confirm") || normalized.includes("restock") || normalized.includes("pay")) {
    return {
      reply: `Order Confirmed.\n\nDispatched from Dark Store Fleet Hub. Driver assigned with 10-minute delivery ETA.\n\nHousehold Pantry Restored to 100% (${primaryItem}).`,
      nextStage: "confirmed",
      restockPantry: true,
    };
  }

  // Add Bread or specific item
  if (normalized.includes("bread")) {
    return {
      reply: "Added 1× Whole Wheat Bread 400g (₹50) to your restock batch.\n\nSubtotal: ₹116 (Delivery: FREE)\nTap below to confirm via UPI or COD.",
      nextStage: "breakdown",
      restockPantry: false,
    };
  }

  // Pantry level status question
  if (normalized.includes("pantry") || normalized.includes("level") || normalized.includes("status")) {
    return {
      reply: `Current Household Pantry: ${primaryItem} is at 15% (runs out tomorrow). Whole Wheat Bread is at 40%. All other staples are at healthy levels (>70%).\n\nWould you like to dispatch a restock batch?`,
      nextStage: "initial",
      restockPantry: false,
    };
  }

  // Default fallback response
  return {
    reply: `Consumption forecast detected your ${primaryItem} reached 15% threshold.\n\nTap 'Confirm Restock' or reply 'YES' for 10-minute dark store delivery.`,
    nextStage: stage === "reminded" || stage === "skipped" ? "initial" : stage,
    restockPantry: false,
  };
}

