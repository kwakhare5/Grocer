"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { AppGlobalHeader } from "../components/navigation/AppGlobalHeader";
import { OperationsDashboard } from "../components/operations/OperationsDashboard";
import { CustomerReplenishmentView } from "../components/customer/CustomerReplenishmentView";
import {
  INITIAL_STORES,
  INITIAL_RECOMMENDATIONS,
  INITIAL_EVENTS,
  DEFAULT_CUSTOMER_PERSONA,
} from "../lib/mockData";
import {
  DarkStore,
  RecommendationItem,
  SimulationEvent,
  SimulationState,
  ScenarioState,
  CustomerPersona,
  CustomerOrderPayload,
} from "../lib/types";
import {
  grocerApi,
  transformStores,
  transformRecommendation,
  BackendAgentRun,
  createSyntheticAgentRun,
} from "../lib/apiClient";
import {
  runScenarioStep,
  getScenario,
  getScenarioInitialStores,
  getScenarioInitialRecommendations,
} from "../lib/scenarioEngine";
import {
  emptyMetrics,
  computeGrocerMetrics,
  computeBaselineMetrics,
} from "../lib/metricsEngine";
import { toast } from "sonner";
import { SimulationFloatingIsland } from "../components/operations/SimulationFloatingIsland";

// ---------------------------------------------------------------------------
// Default scenario state
// ---------------------------------------------------------------------------

function defaultScenarioState(): ScenarioState {
  return {
    activeScenarioId: null,
    currentStep: 0,
    totalSteps: 0,
    isAutoPlaying: false,
    isComplete: false,
    seed: 0,
    grocerMetrics: emptyMetrics(),
    baselineMetrics: emptyMetrics(),
  };
}

// ---------------------------------------------------------------------------
// Main Application
// ---------------------------------------------------------------------------

function GrocerApp() {
  const [mode, setMode] = useState<"operations" | "customer">("operations");
  const [stores, setStores] = useState<DarkStore[]>(INITIAL_STORES);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>(
    INITIAL_RECOMMENDATIONS
  );
  const [events, setEvents] = useState<SimulationEvent[]>(INITIAL_EVENTS);
  const [isLiveApiConnected, setIsLiveApiConnected] = useState<boolean>(false);
  const [activeSimulationId, setActiveSimulationId] = useState<string | null>(null);
  const [simulation, setSimulation] = useState<SimulationState>({
    isRunning: false,
    currentDay: 7,
    currentHour: 12,
    activeScenario: "mumbai_fleet_rush",
    totalOrdersDelivered: 1420,
    wasteAvoidedINR: 4890,
    stockoutMitigatedCount: 14,
    avgTransferTimeMinutes: 22,
  });
  const [scenario, setScenario] = useState<ScenarioState>(defaultScenarioState());
  const [metricsDismissed, setMetricsDismissed] = useState(false);
  const [activeCustomer, setActiveCustomer] = useState<CustomerPersona>(DEFAULT_CUSTOMER_PERSONA);
  const [agentRuns, setAgentRuns] = useState<BackendAgentRun[]>([]);

  // Derived: show metrics panel when scenario completes (unless user dismissed)
  const showMetrics = scenario.isComplete && !!scenario.activeScenarioId && !metricsDismissed;

  // Calculate live critical risk count
  const criticalRiskCount = stores.reduce(
    (acc, s) => acc + (s.stockoutRiskCount > 0 ? 1 : 0),
    0
  );

  // -------------------------------------------------------------------------
  // FastAPI Backend Sync
  // -------------------------------------------------------------------------

  const syncWithBackend = useCallback(async () => {
    try {
      const isHealthy = await grocerApi.checkHealth();
      if (!isHealthy) {
        setIsLiveApiConnected(false);
        return;
      }

      setIsLiveApiConnected(true);

      const [backendStores, backendProducts, backendRisks, backendRecs, activeSim, runs] = await Promise.all([
        grocerApi.getStores(),
        grocerApi.getProducts(),
        grocerApi.getRisks(),
        grocerApi.getRecommendations(),
        grocerApi.getActiveSimulation(),
        grocerApi.getAgentRuns(),
      ]);

      if (runs && runs.length > 0) {
        setAgentRuns(runs);
      }

      if (activeSim && activeSim.simulation_id) {
        setActiveSimulationId(activeSim.simulation_id);
        if (activeSim.current_time) {
          const simDate = new Date(activeSim.current_time);
          setSimulation((prev) => ({
            ...prev,
            currentDay: (Math.floor(simDate.getTime() / (1000 * 60 * 60 * 24)) % 30) + 1,
            currentHour: simDate.getUTCHours(),
          }));
        }
      }

      if (backendStores && backendStores.length > 0) {
        const transformedStores = transformStores(backendStores, backendRisks || []);
        setStores(transformedStores);

        if (backendRecs && backendRecs.length > 0 && backendProducts) {
          const transformedRecs = backendRecs.map((r) =>
            transformRecommendation(r, transformedStores, backendProducts, backendRisks || [])
          );
          setRecommendations(transformedRecs);
        }
      }
    } catch {
      setIsLiveApiConnected(false);
    }
  }, []);

  // Initial load check
  useEffect(() => {
    let mounted = true;
    async function probeBackend() {
      try {
        const isHealthy = await grocerApi.checkHealth();
        if (!mounted) return;
        if (isHealthy) {
          setIsLiveApiConnected(true);
          const [backendStores, backendProducts, backendRisks, backendRecs, activeSim, runs] = await Promise.all([
            grocerApi.getStores(),
            grocerApi.getProducts(),
            grocerApi.getRisks(),
            grocerApi.getRecommendations(),
            grocerApi.getActiveSimulation(),
            grocerApi.getAgentRuns(),
          ]);
          if (!mounted) return;

          if (runs && runs.length > 0) {
            setAgentRuns(runs);
          }

          if (activeSim && activeSim.simulation_id) {
            setActiveSimulationId(activeSim.simulation_id);
            if (activeSim.current_time) {
              const simDate = new Date(activeSim.current_time);
              setSimulation((prev) => ({
                ...prev,
                currentDay: (Math.floor(simDate.getTime() / (1000 * 60 * 60 * 24)) % 30) + 1,
                currentHour: simDate.getUTCHours(),
              }));
            }
          }

          if (backendStores && backendStores.length > 0) {
            const transformedStores = transformStores(backendStores, backendRisks || []);
            setStores(transformedStores);
            if (backendRecs && backendRecs.length > 0 && backendProducts) {
              const transformedRecs = backendRecs.map((r) =>
                transformRecommendation(r, transformedStores, backendProducts, backendRisks || [])
              );
              setRecommendations(transformedRecs);
            }
          }
        }
      } catch {
        if (mounted) setIsLiveApiConnected(false);
      }
    }
    probeBackend();
    return () => {
      mounted = false;
    };
  }, []);

  // -------------------------------------------------------------------------
  // Time Advancement
  // -------------------------------------------------------------------------

  const handleAdvanceTime = useCallback(async (hours: number) => {
    const nowStamp = new Date().toTimeString().substring(0, 8);

    if (isLiveApiConnected && activeSimulationId) {
      try {
        const advanced = await grocerApi.advanceSimulation(activeSimulationId, hours);
        if (advanced && advanced.current_time) {
          const simDate = new Date(advanced.current_time);
          setSimulation((prev) => ({
            ...prev,
            currentDay: (Math.floor(simDate.getTime() / (1000 * 60 * 60 * 24)) % 30) + 1,
            currentHour: simDate.getUTCHours(),
            totalOrdersDelivered: prev.totalOrdersDelivered + (hours * 18),
          }));
        }
        await grocerApi.evaluateRisks();
        await syncWithBackend();

        const newEvent: SimulationEvent = {
          id: `ev-${Date.now()}`,
          timestamp: nowStamp,
          type: "INVENTORY_UPDATED",
          description: `Authoritative Backend: +${hours}h simulated across 5 dark stores.`,
          severity: "info",
        };
        setEvents((prev) => [newEvent, ...prev.slice(0, 29)]);
        toast.success(`Backend advanced +${hours}h`);
        return;
      } catch {
        toast.error("Failed to advance backend simulation");
      }
    }

    setSimulation((prev) => {
      const nextHour = prev.currentHour + hours;
      const nextDay = prev.currentDay + Math.floor(nextHour / 24);
      return {
        ...prev,
        currentDay: nextDay,
        currentHour: nextHour % 24,
        totalOrdersDelivered: prev.totalOrdersDelivered + hours * 18,
      };
    });

    const newEvent: SimulationEvent = {
      id: `ev-${Date.now()}`,
      timestamp: nowStamp,
      type: "INVENTORY_UPDATED",
      description: `Simulated ${hours}h demand across Mumbai dark stores. Orders processed: +${hours * 18}.`,
      severity: "info",
    };
    setEvents((prev) => [newEvent, ...prev.slice(0, 29)]);
    toast.success(`Advanced simulation clock by +${hours}h`);
  }, [isLiveApiConnected, activeSimulationId, syncWithBackend]);


  // Run/Pause loop
  const handleToggleRun = () => {
    setSimulation((prev) => {
      const nextState = !prev.isRunning;
      if (nextState) {
        toast.info("Simulation Engine running in live mode");
      } else {
        toast.info("Simulation Engine paused");
      }
      return { ...prev, isRunning: nextState };
    });
  };

  useEffect(() => {
    if (!simulation.isRunning) return;
    const interval = setInterval(() => {
      handleAdvanceTime(1);
    }, 4000);
    return () => clearInterval(interval);
  }, [simulation.isRunning, handleAdvanceTime]);

  // -------------------------------------------------------------------------
  // Scenario Engine
  // -------------------------------------------------------------------------

  const handleSelectScenario = useCallback((scenarioId: string) => {
    const def = getScenario(scenarioId);
    if (!def) return;

    const initialStores = getScenarioInitialStores();
    const initialRecs = getScenarioInitialRecommendations();

    setStores(initialStores);
    setRecommendations(initialRecs);
    setEvents(INITIAL_EVENTS);
    setSimulation((prev) => ({
      ...prev,
      isRunning: false,
      currentDay: 7,
      currentHour: 12,
    }));
    setScenario({
      activeScenarioId: scenarioId,
      currentStep: 0,
      totalSteps: def.steps.length,
      isAutoPlaying: false,
      isComplete: false,
      seed: def.seed,
      grocerMetrics: emptyMetrics(),
      baselineMetrics: emptyMetrics(),
    });

    setMetricsDismissed(false);
    toast.info(`Scenario loaded: ${def.name}`);
  }, []);

  const handleStepScenario = useCallback(() => {
    if (!scenario.activeScenarioId || scenario.isComplete) return;

    const result = runScenarioStep(
      scenario.activeScenarioId,
      scenario.currentStep,
      stores,
      recommendations
    );
    if (!result) return;

    setStores(result.stores);
    setRecommendations(result.recommendations);
    setEvents((prev) => [...result.newEvents, ...prev.slice(0, 30 - result.newEvents.length)]);

    if (result.advanceHours > 0) {
      setSimulation((prev) => {
        const nextHour = prev.currentHour + result.advanceHours;
        const nextDay = prev.currentDay + Math.floor(nextHour / 24);
        return {
          ...prev,
          currentDay: nextDay,
          currentHour: nextHour % 24,
          totalOrdersDelivered: prev.totalOrdersDelivered + result.advanceHours * 18,
        };
      });
    }

    const nextStep = scenario.currentStep + 1;
    const def = getScenario(scenario.activeScenarioId);
    const isComplete = def ? nextStep >= def.steps.length : true;

    const updatedGrocerMetrics = isComplete
      ? computeGrocerMetrics(
          [...result.newEvents, ...events],
          result.stores,
          result.recommendations
        )
      : scenario.grocerMetrics;

    const updatedBaselineMetrics = isComplete && def
      ? computeBaselineMetrics(scenario.activeScenarioId, def.steps.length, result.stores)
      : scenario.baselineMetrics;

    setScenario((prev) => ({
      ...prev,
      currentStep: nextStep,
      isComplete,
      isAutoPlaying: isComplete ? false : prev.isAutoPlaying,
      grocerMetrics: updatedGrocerMetrics,
      baselineMetrics: updatedBaselineMetrics,
    }));

    toast.success(`Step ${nextStep}/${scenario.totalSteps}: ${result.label}`);

    if (isComplete) {
      toast.info("Scenario complete. Metrics comparison available.");
    }
  }, [scenario, stores, recommendations, events]);

  const handleToggleAutoPlay = useCallback(() => {
    setScenario((prev) => ({ ...prev, isAutoPlaying: !prev.isAutoPlaying }));
  }, []);

  // Auto-play interval
  useEffect(() => {
    if (!scenario.isAutoPlaying || scenario.isComplete) return;
    const interval = setInterval(() => {
      handleStepScenario();
    }, 4000);
    return () => clearInterval(interval);
  }, [scenario.isAutoPlaying, scenario.isComplete, handleStepScenario]);

  const handleDemoMode = useCallback(() => {
    setMode("operations");
    handleSelectScenario("hero_transfer");
    setScenario((prev) => ({ ...prev, isAutoPlaying: true }));
    toast.success("1-Click Demo Started: Hero Stockout & Inter-Store Transfer Scenario");
  }, [handleSelectScenario]);

  const handleReset = async () => {
    if (isLiveApiConnected && activeSimulationId) {
      try {
        const res = await grocerApi.resetSimulation(activeSimulationId);
        if (res && res.simulation_id) {
          setActiveSimulationId(res.simulation_id);
          if (res.current_time) {
            const simDate = new Date(res.current_time);
            setSimulation((prev) => ({
              ...prev,
              isRunning: false,
              currentDay: 1,
              currentHour: simDate.getUTCHours(),
            }));
          }
        }
        await syncWithBackend();
        setScenario(defaultScenarioState());
        toast.success("Backend simulation reset to initial seed state");
        return;
      } catch {
        toast.error("Failed to reset backend simulation");
      }
    }

    setStores(INITIAL_STORES);
    setRecommendations(INITIAL_RECOMMENDATIONS);
    setEvents(INITIAL_EVENTS);
    setSimulation({
      isRunning: false,
      currentDay: 7,
      currentHour: 12,
      activeScenario: "mumbai_fleet_rush",
      totalOrdersDelivered: 1420,
      wasteAvoidedINR: 4890,
      stockoutMitigatedCount: 14,
      avgTransferTimeMinutes: 22,
    });
    setScenario(defaultScenarioState());
    toast.info("Simulation reset to baseline state");
  };

  // -------------------------------------------------------------------------
  // Approval / Rejection Handlers
  // -------------------------------------------------------------------------

  const handleApproveRecommendation = async (recId: string) => {
    const rec = recommendations.find((r) => r.id === recId);
    if (!rec) return;

    // 1. Immediately enter executing state
    setRecommendations((prev) =>
      prev.map((r) => (r.id === recId ? { ...r, status: "executing" as const } : r))
    );

    const nowStamp = new Date().toTimeString().substring(0, 8);
    let runResult: BackendAgentRun | null = null;

    if (isLiveApiConnected) {
      try {
        await grocerApi.approveRecommendation(recId);
        runResult = await grocerApi.executeAgent(recId);
        await syncWithBackend();
      } catch (err) {
        console.error("Backend agent execution failed, generating fallback trace:", err);
      }
    }

    // 2. If offline or backend did not return runResult, generate synthetic 5-node trace
    if (!runResult) {
      runResult = createSyntheticAgentRun(rec);
    }

    // Append to live agent runs log
    setAgentRuns((prev) => [runResult!, ...prev.filter((r) => r.run_id !== runResult!.run_id)]);

    const isCompleted = runResult.status === "completed";

    // 3. Update recommendation final status
    setRecommendations((prev) =>
      prev.map((r) =>
        r.id === recId
          ? {
              ...r,
              status: isCompleted ? ("completed" as const) : ("failed" as const),
            }
          : r
      )
    );

    // 4. Update local inventory buffers if offline
    if (!isLiveApiConnected && isCompleted) {
      if (rec.actionType === "transfer" && rec.sourceStore) {
        setStores((prev) =>
          prev.map((s) => {
            if (s.code === rec.destinationStore.code) {
              return {
                ...s,
                status: "active",
                stockoutRiskCount: Math.max(0, s.stockoutRiskCount - 1),
                inventoryHealth: {
                  ...s.inventoryHealth,
                  dairy: Math.min(100, s.inventoryHealth.dairy + 40),
                },
              };
            }
            if (s.code === rec.sourceStore?.code) {
              return {
                ...s,
                excessCapacityUnits: Math.max(0, s.excessCapacityUnits - rec.quantity),
              };
            }
            return s;
          })
        );
      } else if (rec.actionType === "discount") {
        setStores((prev) =>
          prev.map((s) =>
            s.code === rec.destinationStore.code
              ? { ...s, spoilageRiskCount: Math.max(0, s.spoilageRiskCount - 1) }
              : s
          )
        );
      }
    }

    const approvedEvent: SimulationEvent = {
      id: `ev-${Date.now()}-1`,
      timestamp: nowStamp,
      type: "HUMAN_APPROVED",
      description: `Operator APPROVED ${rec.actionType.toUpperCase()}: ${rec.title}`,
      storeCode: rec.destinationStore.code,
      severity: "success",
    };
    const executedEvent: SimulationEvent = {
      id: `ev-${Date.now()}-2`,
      timestamp: nowStamp,
      type: isCompleted
        ? rec.actionType === "transfer"
          ? "TRANSFER_COMPLETED"
          : "INVENTORY_UPDATED"
        : "INVENTORY_UPDATED",
      description: isCompleted
        ? `LangGraph Executed: ${rec.quantity} ${rec.unit} verified across 5 nodes.`
        : `LangGraph Recovery: ${runResult.error || "Alternative recalculated."}`,
      storeCode: rec.destinationStore.code,
      severity: isCompleted ? "info" : "warning",
    };

    setEvents((prev) => [executedEvent, approvedEvent, ...prev.slice(0, 28)]);

    if (isCompleted) {
      toast.success(`LangGraph Executed: ${rec.title}`);
    } else {
      toast.warning(`Recovery Triggered: Human Review Required`);
    }
  };

  const handleRejectRecommendation = async (recId: string) => {
    const rec = recommendations.find((r) => r.id === recId);
    if (!rec) return;

    setRecommendations((prev) =>
      prev.map((r) => (r.id === recId ? { ...r, status: "rejected" as const } : r))
    );

    if (isLiveApiConnected) {
      try {
        await grocerApi.rejectRecommendation(recId);
        await syncWithBackend();
      } catch {
        // Continue
      }
    }

    const nowStamp = new Date().toTimeString().substring(0, 8);
    const rejectEvent: SimulationEvent = {
      id: `ev-${Date.now()}`,
      timestamp: nowStamp,
      type: "INVENTORY_UPDATED",
      description: `Operator DISMISSED recommendation for ${rec.productName}.`,
      storeCode: rec.destinationStore.code,
      severity: "warning",
    };
    setEvents((prev) => [rejectEvent, ...prev.slice(0, 29)]);
    toast.info(`Recommendation dismissed for ${rec.productName}`);
  };

  // -------------------------------------------------------------------------
  // Customer WhatsApp Replenishment Handlers
  // -------------------------------------------------------------------------

  const handleCustomerOrder = useCallback(
    async (payload: CustomerOrderPayload) => {
      setStores((prevStores) =>
        prevStores.map((store) => {
          if (
            store.code === payload.homeStoreCode ||
            store.name.toLowerCase().includes(payload.homeStoreName.toLowerCase())
          ) {
            const hasDairy = payload.items.some(
              (i) => i.productId.includes("milk") || i.productName.toLowerCase().includes("milk")
            );
            const hasBakery = payload.items.some(
              (i) => i.productId.includes("bread") || i.productName.toLowerCase().includes("bread")
            );

            return {
              ...store,
              inventoryHealth: {
                ...store.inventoryHealth,
                dairy: hasDairy
                  ? Math.max(10, store.inventoryHealth.dairy - 4)
                  : store.inventoryHealth.dairy,
                bakery: hasBakery
                  ? Math.max(10, store.inventoryHealth.bakery - 5)
                  : store.inventoryHealth.bakery,
              },
            };
          }
          return store;
        })
      );

      setSimulation((prev) => ({
        ...prev,
        totalOrdersDelivered: prev.totalOrdersDelivered + 1,
      }));

      const nowStamp = new Date().toTimeString().substring(0, 8);
      const itemSummary = payload.items
        .map((i) => `${i.quantity}× ${i.productName}`)
        .join(", ");
      const orderEvent: SimulationEvent = {
        id: `ev-${Date.now()}`,
        timestamp: nowStamp,
        type: "ORDER_CREATED",
        description: `WhatsApp 1-Tap Restock: ${payload.customerName} ordered ${itemSummary} from ${payload.homeStoreName} (₹${payload.totalINR} via ${payload.paymentMethod}).`,
        storeCode: payload.homeStoreCode,
        severity: "info",
      };

      setEvents((prev) => [orderEvent, ...prev.slice(0, 29)]);

      if (isLiveApiConnected) {
        try {
          await grocerApi.reorderCustomer(
            payload.customerId,
            payload.items.map((it) => ({
              product_id: it.productId,
              quantity: it.quantity,
            }))
          );
        } catch {
          // Continue
        }
      }
    },
    [isLiveApiConnected]
  );

  const handleCustomerReminder = useCallback(
    async (customerId: string, delayHours: number) => {
      const nowStamp = new Date().toTimeString().substring(0, 8);
      const reminderEvent: SimulationEvent = {
        id: `ev-${Date.now()}`,
        timestamp: nowStamp,
        type: "SCENARIO_STEP",
        description: `Customer ${activeCustomer.name} scheduled restock reminder (+${delayHours}h).`,
        storeCode: activeCustomer.homeStoreCode,
        severity: "info",
      };
      setEvents((prev) => [reminderEvent, ...prev.slice(0, 29)]);

      if (isLiveApiConnected) {
        try {
          await grocerApi.remindCustomer(customerId, delayHours);
        } catch {
          // Fallback
        }
      }
    },
    [activeCustomer, isLiveApiConnected]
  );

  const handleCustomerSkip = useCallback(
    async (customerId: string, reason?: string) => {
      const nowStamp = new Date().toTimeString().substring(0, 8);
      const skipEvent: SimulationEvent = {
        id: `ev-${Date.now()}`,
        timestamp: nowStamp,
        type: "SCENARIO_STEP",
        description: `Customer ${activeCustomer.name} skipped restock proposal (${reason || "user_skipped"}).`,
        storeCode: activeCustomer.homeStoreCode,
        severity: "warning",
      };
      setEvents((prev) => [skipEvent, ...prev.slice(0, 29)]);

      if (isLiveApiConnected) {
        try {
          await grocerApi.skipCustomer(customerId, reason);
        } catch {
          // Fallback
        }
      }
    },
    [activeCustomer, isLiveApiConnected]
  );

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-zinc-900 font-sans flex flex-col antialiased selection:bg-emerald-600 selection:text-white">
      {/* 1. Persistent Unified Global Header */}
      <AppGlobalHeader
        mode={mode}
        setMode={setMode}
        criticalRiskCount={criticalRiskCount}
        isLiveApiConnected={isLiveApiConnected}
        onDemoMode={handleDemoMode}
      />

      {/* 2. Main Dual-Workflow View Content */}
      <main className="flex-1 flex flex-col w-full pb-16">
        {mode === "operations" ? (
          <OperationsDashboard
            stores={stores}
            recommendations={recommendations}
            events={events}
            simulation={simulation}
            agentRuns={agentRuns}
            onApproveRecommendation={handleApproveRecommendation}
            onRejectRecommendation={handleRejectRecommendation}
            scenario={scenario}
            showMetrics={showMetrics}
            onDismissMetrics={() => setMetricsDismissed(true)}
          />
        ) : (
          <CustomerReplenishmentView
            activeCustomer={activeCustomer}
            onCustomerChange={setActiveCustomer}
            onPlaceOrder={handleCustomerOrder}
            onScheduleReminder={handleCustomerReminder}
            onSkipRestock={handleCustomerSkip}
            stores={stores}
            isLiveApiConnected={isLiveApiConnected}
          />
        )}
      </main>

      {/* 3. Floating Simulation Control Dock (Only shown during store operations) */}
      {mode === "operations" && (
        <SimulationFloatingIsland
          simulation={simulation}
          onToggleRun={handleToggleRun}
          onAdvanceTime={handleAdvanceTime}
          onReset={handleReset}
          scenario={scenario}
          onSelectScenario={handleSelectScenario}
          onStepScenario={handleStepScenario}
          onToggleAutoPlay={handleToggleAutoPlay}
          onDemoMode={handleDemoMode}
          isLiveApiConnected={isLiveApiConnected}
        />
      )}
    </div>
  );
}


export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen w-screen items-center justify-center bg-[#FAFAFA] text-xs font-mono text-zinc-400">
          INITIALIZING GROCER COCKPIT...
        </div>
      }
    >
      <GrocerApp />
    </Suspense>
  );
}
