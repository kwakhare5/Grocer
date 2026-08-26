import { Milk, Apple, Egg, Wheat, Droplet, LucideIcon } from "lucide-react";
import { Recipe, PriceSignal } from "./types";

export interface PantryStapleDefinition {
  id: string;
  name: string;
  category: "dairy" | "produce" | "poultry" | "bakery" | "pantry";
  dailyRate: number; // e.g. 0.48 L/day
  unit: string;
  defaultDays: number;
  defaultFillPct: number;
  price: number;
  iconName: "milk" | "apple" | "egg" | "wheat" | "droplet";
}

export const ICON_MAP: Record<string, LucideIcon> = {
  milk: Milk,
  apple: Apple,
  egg: Egg,
  wheat: Wheat,
  droplet: Droplet,
};

export const DEFAULT_PANTRY_STAPLES: PantryStapleDefinition[] = [
  {
    id: "milk",
    name: "Amul Taaza Milk 1L",
    category: "dairy",
    dailyRate: 0.48,
    unit: "L",
    defaultDays: 1,
    defaultFillPct: 15,
    price: 66,
    iconName: "milk",
  },
  {
    id: "tomatoes",
    name: "Fresh Hybrid Tomatoes 500g",
    category: "produce",
    dailyRate: 0.14,
    unit: "kg",
    defaultDays: 1,
    defaultFillPct: 14,
    price: 32,
    iconName: "apple",
  },
  {
    id: "eggs",
    name: "Farm Fresh Eggs (12 pcs)",
    category: "poultry",
    dailyRate: 2.4,
    unit: "pcs",
    defaultDays: 2,
    defaultFillPct: 35,
    price: 90,
    iconName: "egg",
  },
  {
    id: "bread",
    name: "Whole Wheat Bread 400g",
    category: "bakery",
    dailyRate: 0.24,
    unit: "loaf",
    defaultDays: 3,
    defaultFillPct: 65,
    price: 50,
    iconName: "wheat",
  },
];

export const RECIPE_DB: Record<string, Recipe> = {
  biryani: {
    dish: "Chicken Biryani",
    servings: 6,
    prepTime: "45 mins",
    ingredients: [
      { name: "Basmati Rice", needed: "600g", status: "have", category: "Grains" },
      { name: "Onions", needed: "400g", status: "have", category: "Produce" },
      { name: "Sunflower Oil", needed: "80ml", status: "low", price: 127, category: "Oils" },
      { name: "Fresh Cream", needed: "200ml", status: "missing", price: 55, category: "Dairy" },
    ],
  },
  dal: {
    dish: "Dal Tadka",
    servings: 4,
    prepTime: "25 mins",
    ingredients: [
      { name: "Toor Dal", needed: "300g", status: "have", category: "Pulses" },
      { name: "Tomatoes", needed: "200g", status: "low", price: 32, category: "Produce" },
      { name: "Cumin Seeds", needed: "15g", status: "have", category: "Spices" },
      { name: "Ghee", needed: "50g", status: "missing", price: 68, category: "Dairy" },
    ],
  },
  paneer: {
    dish: "Paneer Butter Masala",
    servings: 4,
    prepTime: "30 mins",
    ingredients: [
      { name: "Paneer", needed: "250g", status: "missing", price: 95, category: "Dairy" },
      { name: "Tomatoes", needed: "300g", status: "low", price: 48, category: "Produce" },
      { name: "Butter", needed: "50g", status: "missing", price: 45, category: "Dairy" },
      { name: "Cashews", needed: "40g", status: "have", category: "Nuts" },
    ],
  },
  oats: {
    dish: "Morning Oats Bowl",
    servings: 2,
    prepTime: "10 mins",
    ingredients: [
      { name: "Rolled Oats", needed: "150g", status: "have", category: "Grains" },
      { name: "Honey", needed: "50ml", status: "have", category: "Pantry" },
      { name: "Fresh Milk", needed: "300ml", status: "low", price: 66, category: "Dairy" },
      { name: "Almonds", needed: "50g", status: "missing", price: 120, category: "Nuts" },
    ],
  },
};

export const PRICE_SIGNALS: PriceSignal[] = [
  { name: "Tomatoes 500g", current: 48, avg: 20, signal: "SPIKE", desc: "+140% vs 30d avg" },
  { name: "Sunflower Oil 1L", current: 98, avg: 127, signal: "DIP", desc: "-23% Stock Up" },
  { name: "Onions 1kg", current: 42, avg: 38, signal: "WATCH", desc: "+10% gradual rise" },
];
