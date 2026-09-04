/**
 * GROCER v2 — Deterministic Scenario Engine (Spec §23–§27)
 *
 * Provides seeded PRNG for reproducible simulation, three built-in scenarios
 * (Hero §25, Perishables §26, Failure §27), and step-by-step event generation
 * that mutates store/recommendation/event state.
 */

import {
  DarkStore,
  RecommendationItem,
  SimulationEvent,
} from "./types";
import { INITIAL_STORES, INITIAL_RECOMMENDATIONS } from "./mockData";

// ---------------------------------------------------------------------------
// Seeded PRNG (Mulberry32) per Spec §24.1 — deterministic replay
// ---------------------------------------------------------------------------

function mulberry32(seed: number): () => number {
  let s = seed | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------------------
// Scenario Definitions
// ---------------------------------------------------------------------------

export interface ScenarioStep {
  label: string;
  description: string;
  /** Mutate stores state for this step */
  applyStores: (stores: DarkStore[], rng: () => number) => DarkStore[];
  /** Generate new recommendations for this step (or null to keep existing) */
  applyRecommendations: (
    recs: RecommendationItem[],
    stores: DarkStore[],
    rng: () => number
  ) => RecommendationItem[];
  /** Generate new events for this step */
  generateEvents: (stepIndex: number) => SimulationEvent[];
  /** Hours to advance the clock */
  advanceHours: number;
}

export interface ScenarioDefinition {
  id: string;
  name: string;
  description: string;
  seed: number;
  steps: ScenarioStep[];
}

// ---------------------------------------------------------------------------
// Baseline Policy Simulation (§28)
// Simple reorder-point: reorder when stock ≤ 20%, no transfers, no discounts.
// ---------------------------------------------------------------------------

export interface BaselineStepResult {
  stockoutEvents: number;
  spoiledUnits: number;
  emergencyReorders: number;
  excessInventory: number;
}

export function runBaselineStep(
  stores: DarkStore[],
  stepIndex: number,
  rng: () => number
): BaselineStepResult {
  let stockoutEvents = 0;
  let spoiledUnits = 0;
  let emergencyReorders = 0;
  let excessInventory = 0;

  for (const store of stores) {
    const health = store.inventoryHealth;

    // Stockouts: any category below 15% in baseline = stockout (no forecasting to prevent)
    if (health.dairy < 15) stockoutEvents++;
    if (health.produce < 15) stockoutEvents++;
    if (health.bakery < 15) stockoutEvents++;

    // Spoilage: baseline has no discount mechanism, excess spoils
    if (store.spoilageRiskCount > 0) {
      spoiledUnits += Math.round(8 + rng() * 12); // 8-20 units spoil per risk
    }

    // Emergency reorders: baseline triggers reorder when ≤ 20% (reactive, not predictive)
    if (health.dairy <= 20 || health.produce <= 20 || health.bakery <= 20) {
      emergencyReorders++;
    }

    // Excess inventory: no transfers to redistribute
    excessInventory += store.excessCapacityUnits;
  }

  // Scale with step progression (things get worse without intervention)
  const degradation = 1 + stepIndex * 0.15;

  return {
    stockoutEvents: Math.round(stockoutEvents * degradation),
    spoiledUnits: Math.round(spoiledUnits * degradation),
    emergencyReorders,
    excessInventory,
  };
}

// ---------------------------------------------------------------------------
// Timestamp helper
// ---------------------------------------------------------------------------

function stepTimestamp(baseHour: number, stepIndex: number): string {
  const hour = (baseHour + stepIndex) % 24;
  const min = Math.round(Math.random() * 59);
  return `${String(hour).padStart(2, "0")}:${String(min).padStart(2, "0")}:00`;
}

// ---------------------------------------------------------------------------
// HERO SCENARIO (§25) — Demand Spike → Transfer → Risk Falls
// ---------------------------------------------------------------------------

function buildHeroScenario(): ScenarioDefinition {
  const seed = 48291;

  const steps: ScenarioStep[] = [
    // Step 0: Normal operations baseline
    {
      label: "Normal Operations",
      description: "All stores operating within safe parameters. Forecasting engine scanning demand signals.",
      advanceHours: 1,
      applyStores: (stores) => stores,
      applyRecommendations: (recs) => recs.map((r) => ({ ...r })),
      generateEvents: (i) => [
        {
          id: `hero-ev-${i}-0`,
          timestamp: stepTimestamp(12, i),
          type: "FORECAST_UPDATED",
          description: "Holt double exponential smoothing generated 24h demand matrix across 5 stores.",
          severity: "info",
        },
      ],
    },

    // Step 1: Demand spike hits Store 04
    {
      label: "Demand Spike Detected",
      description: "Sudden demand surge at Dadar / Lower Parel (St 04). Dairy consumption velocity increases 2.8×.",
      advanceHours: 2,
      applyStores: (stores) =>
        stores.map((s) =>
          s.code === "St 04"
            ? {
                ...s,
                status: "critical" as const,
                stockoutRiskCount: 3,
                inventoryHealth: {
                  ...s.inventoryHealth,
                  dairy: 18,
                  produce: 42,
                  bakery: 35,
                },
              }
            : s
        ),
      applyRecommendations: (recs) => recs.map((r) => ({ ...r })),
      generateEvents: (i) => [
        {
          id: `hero-ev-${i}-0`,
          timestamp: stepTimestamp(12, i),
          type: "SCENARIO_STEP",
          description: "DEMAND SPIKE: Dadar area orders surged 2.8× — Saturday evening rush + local festival overlap.",
          storeCode: "St 04",
          severity: "warning",
        },
        {
          id: `hero-ev-${i}-1`,
          timestamp: stepTimestamp(12, i),
          type: "INVENTORY_UPDATED",
          description: "St 04 dairy inventory depleting rapidly: Milk 1L dropped from 34% → 18% fill in 2h.",
          storeCode: "St 04",
          severity: "critical",
        },
      ],
    },

    // Step 2: Stockout risk rises at St 04
    {
      label: "Store 04 Stockout Risk Rises",
      description: "Forecasting engine projects critical stockout at St 04 within 5.2 hours. Risk engine flags 3 products.",
      advanceHours: 1,
      applyStores: (stores) =>
        stores.map((s) =>
          s.code === "St 04"
            ? {
                ...s,
                inventoryHealth: {
                  ...s.inventoryHealth,
                  dairy: 12,
                },
              }
            : s
        ),
      applyRecommendations: (recs) => recs.map((r) => ({ ...r })),
      generateEvents: (i) => [
        {
          id: `hero-ev-${i}-0`,
          timestamp: stepTimestamp(12, i),
          type: "RISK_DETECTED",
          description: "CRITICAL stockout alert at Dadar / Lower Parel: Milk 1L runout projected in 5.2h. Supplier ETA: 28h.",
          storeCode: "St 04",
          severity: "critical",
        },
        {
          id: `hero-ev-${i}-1`,
          timestamp: stepTimestamp(12, i),
          type: "FORECAST_UPDATED",
          description: "Demand forecast revised upward for St 04 dairy: +180% vs 14-day moving average.",
          storeCode: "St 04",
          severity: "warning",
        },
      ],
    },

    // Step 3: Store 02 develops safe excess
    {
      label: "Store 02 Develops Safe Excess",
      description: "Bandra West (St 02) dairy levels remain elevated. IQR analysis confirms safe excess of 28 units above safety stock.",
      advanceHours: 1,
      applyStores: (stores) =>
        stores.map((s) =>
          s.code === "St 02"
            ? { ...s, excessCapacityUnits: 68, inventoryHealth: { ...s.inventoryHealth, dairy: 96 } }
            : s
        ),
      applyRecommendations: (recs) => recs.map((r) => ({ ...r })),
      generateEvents: (i) => [
        {
          id: `hero-ev-${i}-0`,
          timestamp: stepTimestamp(12, i),
          type: "INVENTORY_UPDATED",
          description: "Bandra West (St 02) dairy safe excess confirmed: 28 units above safety stock threshold.",
          storeCode: "St 02",
          severity: "info",
        },
      ],
    },

    // Step 4: GROCER detects risk, decision engine evaluates, transfer ranked highest
    {
      label: "GROCER Detects Risk → Transfer Ranked #1",
      description:
        "Decision engine evaluates 4 policies: Transfer (score 94), Reorder (42), Discount (N/A), Hold (12). Transfer from St 02 → St 04 ranked highest.",
      advanceHours: 0,
      applyStores: (stores) => stores,
      applyRecommendations: (_recs, stores) => {
        const destStore = stores.find((s) => s.code === "St 04");
        const srcStore = stores.find((s) => s.code === "St 02");
        const existingNonTransfer = _recs.filter((r) => r.id !== "rec-01");
        const transferRec: RecommendationItem = {
          id: "rec-hero-01",
          riskId: "risk-hero-101",
          title: "Projected Stockout: Full Cream Milk 1L",
          productName: "Full Cream Milk",
          productCategory: "dairy",
          sourceStore: {
            id: srcStore?.id || "st-02",
            code: "St 02",
            name: "Bandra West",
            safeExcess: 28,
          },
          destinationStore: {
            id: destStore?.id || "st-04",
            code: "St 04",
            name: "Dadar / Lower Parel",
          },
          actionType: "transfer",
          severity: "critical",
          status: "pending",
          quantity: 20,
          unit: "units",
          distanceKm: 2.1,
          stockoutInHours: 5.2,
          supplierEtaHours: 28.0,
          probability: 0.94,
          confidence: 0.96,
          reasonCodes: [
            "DESTINATION_HIGH_STOCKOUT_RISK",
            "SUPPLIER_LEAD_TIME_EXCEEDS_RUNOUT",
            "SOURCE_HAS_VERIFIED_SAFE_EXCESS",
            "TRANSIT_DISTANCE_UNDER_3KM",
          ],
          alternatives: [
            {
              action: "transfer",
              label: "Lateral Transfer (St 02 → St 04)",
              score: 94,
              reason: "Arrives in 22 mins, covers demand safely, St 02 remains at 140% safety stock.",
              isRecommended: true,
            },
            {
              action: "reorder",
              label: "Emergency Supplier Reorder",
              score: 42,
              reason: "Supplier lead time is 28h, resulting in ~23h of unfulfilled customer orders.",
            },
            {
              action: "hold",
              label: "Hold & Absorb Stockout",
              score: 12,
              reason: "Leaves 38 expected customer stockouts and ~₹2,508 in lost GMV.",
            },
          ],
          tradeoffAnalysis: {
            spoilageAvoidanceINR: 0,
            transportCostINR: 140,
            stockoutLossAvoidedINR: 1320,
            netBenefitINR: 1180,
          },
          createdAt: new Date().toISOString(),
        };
        return [transferRec, ...existingNonTransfer];
      },
      generateEvents: (i) => [
        {
          id: `hero-ev-${i}-0`,
          timestamp: stepTimestamp(12, i),
          type: "RECOMMENDATION_CREATED",
          description:
            "Decision engine scored: TRANSFER=94, REORDER=42, HOLD=12. Generated TRANSFER recommendation: 20 units from Bandra West (St 02) → Dadar (St 04).",
          storeCode: "St 04",
          severity: "warning",
        },
      ],
    },

    // Step 5: Operator opens WHY and approves
    {
      label: "Operator Reviews WHY → Approves",
      description:
        "Operator inspects root-cause telemetry, reviews alternative policies and financial tradeoff (net +₹1,180). Approves transfer.",
      advanceHours: 0,
      applyStores: (stores) => stores,
      applyRecommendations: (recs) =>
        recs.map((r) =>
          r.id === "rec-hero-01" ? { ...r, status: "approved" as const } : r
        ),
      generateEvents: (i) => [
        {
          id: `hero-ev-${i}-0`,
          timestamp: stepTimestamp(12, i),
          type: "HUMAN_APPROVED",
          description: "Operator APPROVED TRANSFER: 20 units Full Cream Milk from Bandra West → Dadar.",
          storeCode: "St 04",
          severity: "success",
        },
      ],
    },

    // Step 6: Pipeline validates and executes
    {
      label: "Validation Pipeline Executes Transfer",
      description:
        "5-node execution pipeline validates pre-conditions, confirms source inventory, executes transfer, and verifies post-state.",
      advanceHours: 0,
      applyStores: (stores) => stores,
      applyRecommendations: (recs) =>
        recs.map((r) =>
          r.id === "rec-hero-01" ? { ...r, status: "executing" as const } : r
        ),
      generateEvents: (i) => [
        {
          id: `hero-ev-${i}-0`,
          timestamp: stepTimestamp(12, i),
          type: "ACTION_EXECUTING",
          description: "Transfer Pipeline: pre_check → validate_inventory → execute_transfer → verify_state pipeline started.",
          storeCode: "St 04",
          severity: "info",
        },
      ],
    },

    // Step 7: Transfer verified, inventory changes, risk falls
    {
      label: "Transfer Verified → Risk Falls",
      description:
        "Transfer complete. St 04 dairy rises from 12% → 52%. St 02 excess reduced from 68 → 48. Stockout risk resolved.",
      advanceHours: 1,
      applyStores: (stores) =>
        stores.map((s) => {
          if (s.code === "St 04") {
            return {
              ...s,
              status: "active" as const,
              stockoutRiskCount: Math.max(0, s.stockoutRiskCount - 1),
              inventoryHealth: {
                ...s.inventoryHealth,
                dairy: 52,
              },
            };
          }
          if (s.code === "St 02") {
            return {
              ...s,
              excessCapacityUnits: 48,
              inventoryHealth: {
                ...s.inventoryHealth,
                dairy: 82,
              },
            };
          }
          return s;
        }),
      applyRecommendations: (recs) =>
        recs.map((r) =>
          r.id === "rec-hero-01" ? { ...r, status: "completed" as const } : r
        ),
      generateEvents: (i) => [
        {
          id: `hero-ev-${i}-0`,
          timestamp: stepTimestamp(12, i),
          type: "TRANSFER_COMPLETED",
          description: "TRANSFER VERIFIED: 20 units Full Cream Milk arrived at St 04. Dairy fill: 12% → 52%. Stockout risk cleared.",
          storeCode: "St 04",
          severity: "success",
        },
        {
          id: `hero-ev-${i}-1`,
          timestamp: stepTimestamp(12, i),
          type: "INVENTORY_UPDATED",
          description: "St 02 excess adjusted: 68 → 48 units. Inventory remains safely above safety stock.",
          storeCode: "St 02",
          severity: "info",
        },
      ],
    },

    // Step 8: Before vs After metrics
    {
      label: "Before vs After Metrics",
      description:
        "Scenario complete. Displaying Baseline vs GROCER comparison metrics. Stockouts avoided, waste cost reduced, service level maintained.",
      advanceHours: 0,
      applyStores: (stores) => stores,
      applyRecommendations: (recs) => recs,
      generateEvents: (i) => [
        {
          id: `hero-ev-${i}-0`,
          timestamp: stepTimestamp(12, i),
          type: "SCENARIO_STEP",
          description: "SCENARIO COMPLETE: Hero scenario finished. Baseline vs GROCER metrics now available for comparison.",
          severity: "success",
        },
      ],
    },
  ];

  return {
    id: "hero",
    name: "High Milk Demand Spike",
    description: "Sudden milk demand surge: system flags stockout risk and schedules a store-to-store transfer.",
    seed,
    steps,
  };
}

// ---------------------------------------------------------------------------
// PERISHABLES SCENARIO (§26) — Bread Expiry → Discount → Waste Avoided
// ---------------------------------------------------------------------------

function buildPerishablesScenario(): ScenarioDefinition {
  const seed = 73154;

  const steps: ScenarioStep[] = [
    // Step 0: Initial state — St 01 has 80 bread, 8h expiry
    {
      label: "Store 01 Bread Inventory Setup",
      description: "Andheri East (St 01) has 80 units of Whole Wheat Bread with batch expiry in 8 hours. Expected sales: 30 units.",
      advanceHours: 0,
      applyStores: (stores) =>
        stores.map((s) =>
          s.code === "St 01"
            ? {
                ...s,
                spoilageRiskCount: 2,
                inventoryHealth: { ...s.inventoryHealth, bakery: 95 },
                excessCapacityUnits: 50,
              }
            : s
        ),
      applyRecommendations: (recs) => recs.map((r) => ({ ...r })),
      generateEvents: (i) => [
        {
          id: `perish-ev-${i}-0`,
          timestamp: stepTimestamp(10, i),
          type: "SCENARIO_STEP",
          description: "PERISHABLES SCENARIO: Store 01 bread inventory = 80 units. Batch expiry = 8h. Expected sales before expiry = 30.",
          storeCode: "St 01",
          severity: "info",
        },
      ],
    },

    // Step 1: Spoilage risk detected
    {
      label: "GROCER Detects Spoilage Risk",
      description: "Forecasting engine calculates ~50 units at risk of expiry. Spoilage alert triggered at St 01.",
      advanceHours: 2,
      applyStores: (stores) =>
        stores.map((s) =>
          s.code === "St 01"
            ? {
                ...s,
                spoilageRiskCount: 3,
                status: "critical" as const,
                inventoryHealth: { ...s.inventoryHealth, bakery: 88 },
              }
            : s
        ),
      applyRecommendations: (recs) => recs.map((r) => ({ ...r })),
      generateEvents: (i) => [
        {
          id: `perish-ev-${i}-0`,
          timestamp: stepTimestamp(10, i),
          type: "RISK_DETECTED",
          description: "SPOILAGE ALERT at St 01: ~50 units Whole Wheat Bread projected to expire. 8h window, only 30 expected organic sales.",
          storeCode: "St 01",
          severity: "critical",
        },
      ],
    },

    // Step 2: Decision engine evaluates — discount ranked highest
    {
      label: "Decision Engine → Discount Ranked #1",
      description: "Engine scores: Discount 20% (score 88), Transfer to Powai (51), Hold (18). Discount accelerates sell-through 3×.",
      advanceHours: 0,
      applyStores: (stores) => stores,
      applyRecommendations: (_recs, stores) => {
        const st01 = stores.find((s) => s.code === "St 01");
        const discountRec: RecommendationItem = {
          id: "rec-perish-01",
          riskId: "risk-perish-101",
          title: "Batch Expiry Imminent: Whole Wheat Bread",
          productName: "Whole Wheat Bread 400g",
          productCategory: "bakery",
          destinationStore: {
            id: st01?.id || "st-01",
            code: "St 01",
            name: "Andheri East",
          },
          actionType: "discount",
          severity: "critical",
          status: "pending",
          quantity: 50,
          unit: "loaves",
          stockoutInHours: 72.0,
          supplierEtaHours: 12.0,
          probability: 0.87,
          confidence: 0.91,
          discountPct: 20,
          reasonCodes: [
            "BATCH_EXPIRY_WITHIN_8_HOURS",
            "EXPECTED_SALES_30_UNITS_VS_80_INVENTORY",
            "20_PCT_DISCOUNT_ACCELERATES_VELOCITY_3X",
            "50_UNITS_AT_SPOILAGE_RISK",
          ],
          alternatives: [
            {
              action: "discount",
              label: "Flash Markdown (20% Off)",
              score: 88,
              reason: "Increases hourly sell-through by 280%, expected to clear 45 of 50 at-risk units before expiry.",
              isRecommended: true,
            },
            {
              action: "transfer",
              label: "Inter-store Transfer to Powai (St 03)",
              score: 51,
              reason: "Transit 45m + cold-chain packing reduces net margin below discount yield. Powai bakery demand lower.",
            },
            {
              action: "hold",
              label: "Hold at Full Price",
              score: 18,
              reason: "Guarantees 50 units spoil, resulting in ₹2,500 direct inventory write-off.",
            },
          ],
          tradeoffAnalysis: {
            spoilageAvoidanceINR: 2250,
            transportCostINR: 0,
            stockoutLossAvoidedINR: 0,
            netBenefitINR: 1800,
          },
          createdAt: new Date().toISOString(),
        };
        const existingFiltered = _recs.filter(
          (r) => r.id !== "rec-02" && r.id !== "rec-perish-01"
        );
        return [discountRec, ...existingFiltered];
      },
      generateEvents: (i) => [
        {
          id: `perish-ev-${i}-0`,
          timestamp: stepTimestamp(10, i),
          type: "RECOMMENDATION_CREATED",
          description: "Decision engine scored: DISCOUNT=88, TRANSFER=51, HOLD=18. Generated 20% flash markdown recommendation for 50 loaves.",
          storeCode: "St 01",
          severity: "warning",
        },
      ],
    },

    // Step 3: Operator approves discount
    {
      label: "Operator Approves Discount",
      description: "Operator reviews spoilage telemetry and financial tradeoff (+₹1,800 net benefit). Approves 20% discount.",
      advanceHours: 0,
      applyStores: (stores) => stores,
      applyRecommendations: (recs) =>
        recs.map((r) =>
          r.id === "rec-perish-01" ? { ...r, status: "approved" as const } : r
        ),
      generateEvents: (i) => [
        {
          id: `perish-ev-${i}-0`,
          timestamp: stepTimestamp(10, i),
          type: "HUMAN_APPROVED",
          description: "Operator APPROVED DISCOUNT: 20% markdown on 50 loaves Whole Wheat Bread at St 01.",
          storeCode: "St 01",
          severity: "success",
        },
      ],
    },

    // Step 4: Discount applied, sell-through accelerates
    {
      label: "Discount Applied → Sell-Through Accelerates",
      description: "20% discount active. Hourly sell-through increased from 3.75 → 10.5 units/h. 45 of 50 at-risk units sold in 5h.",
      advanceHours: 5,
      applyStores: (stores) =>
        stores.map((s) =>
          s.code === "St 01"
            ? {
                ...s,
                status: "active" as const,
                spoilageRiskCount: 0,
                inventoryHealth: { ...s.inventoryHealth, bakery: 38 },
                excessCapacityUnits: 5,
              }
            : s
        ),
      applyRecommendations: (recs) =>
        recs.map((r) =>
          r.id === "rec-perish-01" ? { ...r, status: "completed" as const } : r
        ),
      generateEvents: (i) => [
        {
          id: `perish-ev-${i}-0`,
          timestamp: stepTimestamp(10, i),
          type: "INVENTORY_UPDATED",
          description: "DISCOUNT EFFECTIVE: 45 of 50 at-risk loaves sold. Only 5 units spoiled vs 50 without intervention. ₹2,250 spoilage avoided.",
          storeCode: "St 01",
          severity: "success",
        },
        {
          id: `perish-ev-${i}-1`,
          timestamp: stepTimestamp(10, i),
          type: "SCENARIO_STEP",
          description: "PERISHABLES SCENARIO COMPLETE: Inventory rescued: 45 units sold. Spoilage avoided: ₹2,250. Net benefit: +₹1,800.",
          severity: "success",
        },
      ],
    },
  ];

  return {
    id: "perishables",
    name: "Expiring Bakery Stock",
    description: "Expiring bakery batches: system applies targeted markdowns before stock spoils.",
    seed,
    steps,
  };
}

// ---------------------------------------------------------------------------
// FAILURE SCENARIO (§27) — Pre-check Fails → Recalculate → Re-approve
// ---------------------------------------------------------------------------

function buildFailureScenario(): ScenarioDefinition {
  const seed = 91537;

  const steps: ScenarioStep[] = [
    // Step 0: GROCER recommends transfer
    {
      label: "GROCER Recommends Transfer",
      description: "Standard transfer recommendation: 20 units Milk from St 02 → St 04 (same as hero scenario setup).",
      advanceHours: 0,
      applyStores: (stores) =>
        stores.map((s) =>
          s.code === "St 04"
            ? {
                ...s,
                status: "critical" as const,
                stockoutRiskCount: 2,
                inventoryHealth: { ...s.inventoryHealth, dairy: 22 },
              }
            : s
        ),
      applyRecommendations: (_recs, stores) => {
        const destStore = stores.find((s) => s.code === "St 04");
        const srcStore = stores.find((s) => s.code === "St 02");
        const transferRec: RecommendationItem = {
          id: "rec-fail-01",
          riskId: "risk-fail-101",
          title: "Projected Stockout: Full Cream Milk 1L",
          productName: "Full Cream Milk",
          productCategory: "dairy",
          sourceStore: {
            id: srcStore?.id || "st-02",
            code: "St 02",
            name: "Bandra West",
            safeExcess: 28,
          },
          destinationStore: {
            id: destStore?.id || "st-04",
            code: "St 04",
            name: "Dadar / Lower Parel",
          },
          actionType: "transfer",
          severity: "critical",
          status: "pending",
          quantity: 20,
          unit: "units",
          distanceKm: 2.1,
          stockoutInHours: 6.8,
          supplierEtaHours: 28.0,
          probability: 0.91,
          confidence: 0.94,
          reasonCodes: [
            "DESTINATION_HIGH_STOCKOUT_RISK",
            "SUPPLIER_LEAD_TIME_EXCEEDS_RUNOUT",
            "SOURCE_HAS_VERIFIED_SAFE_EXCESS",
          ],
          alternatives: [
            {
              action: "transfer",
              label: "Lateral Transfer (St 02 → St 04)",
              score: 92,
              reason: "Arrives in 22 mins, covers demand safely.",
              isRecommended: true,
            },
            {
              action: "reorder",
              label: "Emergency Supplier Reorder",
              score: 40,
              reason: "Supplier ETA 28h exceeds stockout window.",
            },
            {
              action: "hold",
              label: "Hold & Absorb",
              score: 10,
              reason: "Expected 35 customer stockouts and ₹2,310 lost GMV.",
            },
          ],
          tradeoffAnalysis: {
            spoilageAvoidanceINR: 0,
            transportCostINR: 140,
            stockoutLossAvoidedINR: 1320,
            netBenefitINR: 1180,
          },
          createdAt: new Date().toISOString(),
        };
        const existingFiltered = _recs.filter(
          (r) => r.id !== "rec-01" && r.id !== "rec-fail-01"
        );
        return [transferRec, ...existingFiltered];
      },
      generateEvents: (i) => [
        {
          id: `fail-ev-${i}-0`,
          timestamp: stepTimestamp(14, i),
          type: "RECOMMENDATION_CREATED",
          description: "Generated TRANSFER: 20 units Milk from Bandra West (St 02) → Dadar (St 04).",
          storeCode: "St 04",
          severity: "warning",
        },
      ],
    },

    // Step 1: Human approves
    {
      label: "Human Approves Transfer",
      description: "Operator reviews and approves the transfer recommendation.",
      advanceHours: 0,
      applyStores: (stores) => stores,
      applyRecommendations: (recs) =>
        recs.map((r) =>
          r.id === "rec-fail-01" ? { ...r, status: "approved" as const } : r
        ),
      generateEvents: (i) => [
        {
          id: `fail-ev-${i}-0`,
          timestamp: stepTimestamp(14, i),
          type: "HUMAN_APPROVED",
          description: "Operator APPROVED TRANSFER: 20 units Milk from St 02 → St 04.",
          storeCode: "St 04",
          severity: "success",
        },
      ],
    },

    // Step 2: Source inventory unexpectedly changes (external event)
    {
      label: "Source Inventory Unexpectedly Changes",
      description:
        "Between approval and execution: flash sale at Bandra West depleted dairy stock. St 02 dairy drops from 92% → 28%. Safe excess evaporated.",
      advanceHours: 1,
      applyStores: (stores) =>
        stores.map((s) =>
          s.code === "St 02"
            ? {
                ...s,
                excessCapacityUnits: 2,
                stockoutRiskCount: 1,
                inventoryHealth: { ...s.inventoryHealth, dairy: 28 },
              }
            : s
        ),
      applyRecommendations: (recs) => recs,
      generateEvents: (i) => [
        {
          id: `fail-ev-${i}-0`,
          timestamp: stepTimestamp(14, i),
          type: "INVENTORY_UPDATED",
          description: "UNEXPECTED: Flash sale at Bandra West depleted dairy stock. St 02 dairy: 92% → 28%. Transfer source no longer has safe excess.",
          storeCode: "St 02",
          severity: "critical",
        },
      ],
    },

    // Step 3: Pre-check fails — does NOT execute
    {
      label: "Transfer Pre-Check FAILS",
      description:
        "Pre-check validation detects stale state: source safe excess < transfer quantity. Execution BLOCKED to prevent inventory violation.",
      advanceHours: 0,
      applyStores: (stores) => stores,
      applyRecommendations: (recs) =>
        recs.map((r) =>
          r.id === "rec-fail-01" ? { ...r, status: "failed" as const } : r
        ),
      generateEvents: (i) => [
        {
          id: `fail-ev-${i}-0`,
          timestamp: stepTimestamp(14, i),
          type: "EXECUTION_FAILED",
          description:
            "PRE-CHECK FAILED: Source St 02 safe excess = 2 units, transfer requires 20. Stale recommendation blocked from execution.",
          storeCode: "St 02",
          severity: "critical",
        },
        {
          id: `fail-ev-${i}-1`,
          timestamp: stepTimestamp(14, i),
          type: "SCENARIO_STEP",
          description: "SAFETY GUARD: Agent prevented stale transfer execution. System integrity maintained. Recalculating alternatives...",
          severity: "warning",
        },
      ],
    },

    // Step 4: Recalculate alternatives — new recommendation (reorder this time)
    {
      label: "Recalculate → New Recommendation",
      description:
        "Decision engine recalculates with updated world state. No inter-store transfer viable. Emergency supplier reorder now ranked highest (score 78).",
      advanceHours: 0,
      applyStores: (stores) => stores,
      applyRecommendations: (_recs, stores) => {
        const destStore = stores.find((s) => s.code === "St 04");
        const failedRec = _recs.find((r) => r.id === "rec-fail-01");
        const reorderRec: RecommendationItem = {
          id: "rec-fail-02",
          riskId: "risk-fail-102",
          title: "Emergency Reorder: Full Cream Milk 1L",
          productName: "Full Cream Milk",
          productCategory: "dairy",
          destinationStore: {
            id: destStore?.id || "st-04",
            code: "St 04",
            name: "Dadar / Lower Parel",
          },
          actionType: "reorder",
          severity: "critical",
          status: "pending",
          quantity: 30,
          unit: "units",
          stockoutInHours: 5.8,
          supplierEtaHours: 14.0,
          probability: 0.89,
          confidence: 0.88,
          reasonCodes: [
            "ORIGINAL_TRANSFER_FAILED_STALE_SOURCE",
            "ALL_NEARBY_STORES_BELOW_SAFE_EXCESS",
            "SUPPLIER_EXPEDITED_DELIVERY_AVAILABLE",
            "EMERGENCY_REORDER_COVERS_GAP",
          ],
          alternatives: [
            {
              action: "reorder",
              label: "Emergency Supplier Reorder (30 units)",
              score: 78,
              reason: "Expedited supplier can deliver in 14h. Partial stockout of ~8h but covers remaining demand.",
              isRecommended: true,
            },
            {
              action: "transfer",
              label: "Lateral Transfer (all sources depleted)",
              score: 15,
              reason: "No store has sufficient safe excess after St 02 depletion.",
            },
            {
              action: "hold",
              label: "Hold & Absorb",
              score: 8,
              reason: "Full stockout for ~28h. Estimated 52 customer failures and ₹3,432 lost GMV.",
            },
          ],
          tradeoffAnalysis: {
            spoilageAvoidanceINR: 0,
            transportCostINR: 85,
            stockoutLossAvoidedINR: 2640,
            netBenefitINR: 2555,
          },
          createdAt: new Date().toISOString(),
        };
        const remaining = _recs.filter(
          (r) => r.id !== "rec-fail-02"
        );
        // Keep the failed rec visible, add new reorder rec
        return [
          reorderRec,
          ...(failedRec ? [failedRec] : []),
          ...remaining.filter((r) => r.id !== "rec-fail-01"),
        ];
      },
      generateEvents: (i) => [
        {
          id: `fail-ev-${i}-0`,
          timestamp: stepTimestamp(14, i),
          type: "RECOMMENDATION_CREATED",
          description:
            "NEW RECOMMENDATION: Emergency Supplier Reorder (30 units Milk) to St 04. Score 78. Previous transfer invalidated — new human approval REQUIRED.",
          storeCode: "St 04",
          severity: "warning",
        },
      ],
    },

    // Step 5: Human must re-approve (scenario ends waiting)
    {
      label: "New Approval Required",
      description:
        "Scenario demonstrates the agent is NOT a happy-path automation script. Stale actions are blocked, alternatives recalculated, and human re-approval enforced.",
      advanceHours: 0,
      applyStores: (stores) => stores,
      applyRecommendations: (recs) => recs,
      generateEvents: (i) => [
        {
          id: `fail-ev-${i}-0`,
          timestamp: stepTimestamp(14, i),
          type: "SCENARIO_STEP",
          description:
            "FAILURE SCENARIO COMPLETE: Stale transfer blocked → recalculated → new reorder pending human approval. Agent safety verified.",
          severity: "success",
        },
      ],
    },
  ];

  return {
    id: "failure",
    name: "Transfer Pre-check & Safety",
    description: "Safety verification demo: transfer automatically cancels if donor store inventory changes.",
    seed,
    steps,
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const SCENARIOS: ScenarioDefinition[] = [
  buildHeroScenario(),
  buildPerishablesScenario(),
  buildFailureScenario(),
];

export function getScenario(id: string): ScenarioDefinition | undefined {
  return SCENARIOS.find((s) => s.id === id);
}

export interface ScenarioStepResult {
  stores: DarkStore[];
  recommendations: RecommendationItem[];
  newEvents: SimulationEvent[];
  advanceHours: number;
  label: string;
  description: string;
}

/**
 * Run a single step of a scenario, returning the new state.
 * Uses seeded PRNG for deterministic replay.
 */
export function runScenarioStep(
  scenarioId: string,
  stepIndex: number,
  currentStores: DarkStore[],
  currentRecommendations: RecommendationItem[]
): ScenarioStepResult | null {
  const scenario = getScenario(scenarioId);
  if (!scenario || stepIndex >= scenario.steps.length) return null;

  const rng = mulberry32(scenario.seed + stepIndex * 1000);
  const step = scenario.steps[stepIndex];

  const newStores = step.applyStores([...currentStores.map((s) => ({ ...s }))], rng);
  const newRecs = step.applyRecommendations(
    [...currentRecommendations.map((r) => ({ ...r }))],
    newStores,
    rng
  );
  const newEvents = step.generateEvents(stepIndex);

  return {
    stores: newStores,
    recommendations: newRecs,
    newEvents,
    advanceHours: step.advanceHours,
    label: step.label,
    description: step.description,
  };
}

/**
 * Get initial stores state for a scenario (reset to INITIAL_STORES).
 */
export function getScenarioInitialStores(): DarkStore[] {
  return INITIAL_STORES.map((s) => ({ ...s }));
}

/**
 * Get initial recommendations for a scenario (reset to INITIAL_RECOMMENDATIONS).
 */
export function getScenarioInitialRecommendations(): RecommendationItem[] {
  return INITIAL_RECOMMENDATIONS.map((r) => ({ ...r }));
}
