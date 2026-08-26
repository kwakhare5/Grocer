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
 * Pure TypeScript 5-Node LangGraph Simulation Engine for WhatsApp messages.
 */
export function processWhatsAppSimulationMessage(
  userText: string,
  stage: "initial" | "item_added" | "breakdown" | "confirmed"
): {
  reply: string;
  nextStage: "initial" | "item_added" | "breakdown" | "confirmed";
  restockPantry: boolean;
} {
  const normalized = userText.trim().toLowerCase();

  // YES / Confirm action
  if (normalized === "yes" || normalized.includes("confirm") || normalized.includes("restock") || normalized.includes("pay")) {
    return {
      reply: "🎉 Order #ORD-4029 Confirmed!\n\nDispatched from Zepto Dark Store. Driver assigned with 10-minute delivery ETA.\n\n✨ Household Pantry Restored to 100% 🥛🍞",
      nextStage: "confirmed",
      restockPantry: true,
    };
  }

  // Add Bread or specific item
  if (normalized.includes("bread")) {
    return {
      reply: "➕ Added 1× Whole Wheat Bread 400g (₹50) to your restock batch.\n\n🛒 Subtotal: ₹116 (Delivery: FREE)\nTap below to confirm via UPI or COD.",
      nextStage: "breakdown",
      restockPantry: false,
    };
  }

  // Recipe or pantry question
  if (normalized.includes("recipe") || normalized.includes("biryani") || normalized.includes("paneer")) {
    return {
      reply: "🍳 Cross-referenced your pantry: You have Basmati Rice & Onions. You need Fresh Cream (₹55) and Sunflower Oil (₹127) to complete Chicken Biryani.\n\nWould you like me to add them to your cart?",
      nextStage: "item_added",
      restockPantry: false,
    };
  }

  // Default fallback response
  return {
    reply: "🤖 Prophet ML detected your Milk & Tomatoes are down to <15%.\n\nReply 'YES' to 1-tap restock for delivery in 10 minutes.",
    nextStage: stage,
    restockPantry: false,
  };
}
