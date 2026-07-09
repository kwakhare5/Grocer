import { Milk, Apple, Egg, Croissant, Droplets, Package, LucideIcon } from "lucide-react";

export interface ThemeColors {
  text: string;
  bg: string;
  border: string;
  hover: string;
}

export interface CategoryTheme extends ThemeColors {
  label: string;
  icon: LucideIcon;
}

export const COLOR_PALETTE = {
  blue: { text: "var(--accent)", bg: "var(--accent-dim)", border: "var(--accent-dim)", hover: "var(--accent-dim)" },
  green: { text: "var(--ok)", bg: "var(--ok-dim)", border: "var(--ok-dim)", hover: "var(--ok-dim)" },
  orange: { text: "var(--danger)", bg: "var(--danger-dim)", border: "var(--danger-dim)", hover: "var(--danger-dim)" },
  purple: { text: "var(--accent)", bg: "var(--accent-dim)", border: "var(--accent-dim)", hover: "var(--accent-dim)" },
  yellow: { text: "var(--warning)", bg: "var(--warning-dim)", border: "var(--warning-dim)", hover: "var(--warning-dim)" },
  pink: { text: "var(--danger)", bg: "var(--danger-dim)", border: "var(--danger-dim)", hover: "var(--danger-dim)" },
  gray: { text: "var(--muted)", bg: "var(--grid-line)", border: "var(--border)", hover: "var(--grid-line)" },
  sand: { text: "var(--warning)", bg: "var(--warning-dim)", border: "var(--warning-dim)", hover: "var(--warning-dim)" }
};


export function getCategoryTheme(nameOrCategory: string): CategoryTheme {
  const n = nameOrCategory.toLowerCase();

  // Dairy
  if (n.includes("dairy") || n.includes("milk")) {
    return { label: "Dairy", icon: Milk, ...COLOR_PALETTE.blue };
  }
  // Produce / Tomato / Apple (Pink)
  if (n.includes("tomato") || n.includes("strawberry") || n.includes("apple")) {
    return { label: "Produce", icon: Apple, ...COLOR_PALETTE.pink };
  }
  // Produce / Greens (Green)
  if (n.includes("onion") || n.includes("spinach") || n.includes("cucumber") || n.includes("produce")) {
    return { label: "Produce", icon: Apple, ...COLOR_PALETTE.green };
  }
  // Proteins / Eggs
  if (n.includes("protein") || n.includes("egg") || n.includes("cheese")) {
    return { label: "Proteins", icon: Egg, ...COLOR_PALETTE.orange };
  }
  // Bakery
  if (n.includes("bakery") || n.includes("bread") || n.includes("flour") || n.includes("atta")) {
    return { label: "Bakery", icon: Croissant, ...COLOR_PALETTE.sand };
  }
  // Oils
  if (n.includes("oil") || n.includes("butter") || n.includes("oils")) {
    return { label: "Oils", icon: Droplets, ...COLOR_PALETTE.yellow };
  }
  // Staples & default (Gray)
  return { label: "Staples", icon: Package, ...COLOR_PALETTE.gray };
}
