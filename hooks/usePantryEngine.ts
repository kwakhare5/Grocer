"use client";

import { useState, useMemo } from "react";

export interface PantryItem {
  id: string;
  name: string;
  unit: string;
  currentStock: number;
  maxCapacity: number;
  dailyConsumptionRate: number;
}

export function usePantryEngine(initialHouseholdSize: number = 3) {
  const [householdMembers, setHouseholdMembers] = useState(initialHouseholdSize);
  const [weeklyRuns, setWeeklyRuns] = useState(4);

  // Core Pantry Staples Matrix
  const [items, setItems] = useState<PantryItem[]>([
    {
      id: "milk",
      name: "Fresh Milk",
      unit: "Liters",
      currentStock: 1.2,
      maxCapacity: 4.0,
      dailyConsumptionRate: 0.8,
    },
    {
      id: "eggs",
      name: "Organic Eggs",
      unit: "Pcs",
      currentStock: 4,
      maxCapacity: 12,
      dailyConsumptionRate: 2,
    },
    {
      id: "bread",
      name: "Whole Wheat Bread",
      unit: "Loaf",
      currentStock: 0.5,
      maxCapacity: 2.0,
      dailyConsumptionRate: 0.3,
    },
  ]);

  // Derived Domain Metrics
  const calculatedMetrics = useMemo(() => {
    const hoursRemaining = Math.round((items[0].currentStock / (items[0].dailyConsumptionRate * (householdMembers / 3))) * 24);
    const isAlertActive = hoursRemaining <= 24;
    const monthlyHoursSaved = Math.round(weeklyRuns * 1.5 * 4);
    const estimatedSavingsRupees = Math.round(monthlyHoursSaved * 250);

    return {
      hoursRemaining: Math.max(1, hoursRemaining),
      isAlertActive,
      monthlyHoursSaved,
      estimatedSavingsRupees,
    };
  }, [items, householdMembers, weeklyRuns]);

  const updateItemStock = (id: string, newStock: number) => {
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, currentStock: newStock } : item))
    );
  };

  return {
    householdMembers,
    setHouseholdMembers,
    weeklyRuns,
    setWeeklyRuns,
    items,
    updateItemStock,
    ...calculatedMetrics,
  };
}
