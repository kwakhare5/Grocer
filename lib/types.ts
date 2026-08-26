import type { LucideIcon } from "lucide-react";

export interface StapleItem {
  id: string;
  name: string;
  days: number;
  fillPct: number;
  avg: string;
  icon: LucideIcon;
  category: string;
}

export interface RecipeIngredient {
  name: string;
  needed: string;
  status: "have" | "low" | "missing";
  price?: number;
  category: string;
}

export interface Recipe {
  dish: string;
  servings: number;
  prepTime: string;
  ingredients: RecipeIngredient[];
}

export interface PriceSignal {
  name: string;
  current: number;
  avg: number;
  signal: "SPIKE" | "DIP" | "WATCH";
  desc: string;
}

export interface WhatsAppMessage {
  sender: "bot" | "user";
  text: string;
  timestamp: string;
}

export interface PhoneMockupProps {
  activeScenario?: string;
  initialViewMode?: "lockscreen" | "whatsapp" | "pantry";
}
