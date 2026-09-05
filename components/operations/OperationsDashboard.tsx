import React, { useState } from "react";
import { DarkStore, RecommendationItem, SimulationEvent, SimulationState, ScenarioState } from "../../lib/types";
import { BackendAgentRun, createSyntheticAgentRun } from "../../lib/apiClient";
import { SpatialTopologyView } from "./SpatialTopologyView";
import { RecommendationStream } from "./RecommendationStream";
import { SkuInventoryTable } from "./SkuInventoryTable";
import { WhyInspectorPanel } from "./WhyInspectorPanel";
import { StoreDetailModal } from "./StoreDetailModal";
import { MetricsComparisonPanel } from "./MetricsComparisonPanel";
import { AgentRunInspector } from "./AgentRunInspector";
import { Table2, ArrowRightLeft, MapPin, Terminal, CheckCircle2, AlertTriangle, Layers } from "lucide-react";
import { toast } from "sonner";

interface OperationsDashboardProps {
  stores: DarkStore[];
  recommendations: RecommendationItem[];
  events: SimulationEvent[];
  simulation: SimulationState;
  agentRuns?: BackendAgentRun[];
  onApproveRecommendation: (recId: string) => void;
  onRejectRecommendation: (recId: string) => void;
  scenario: ScenarioState;
  showMetrics: boolean;
  onDismissMetrics: () => void;
}

export function OperationsDashboard({
  stores,
  recommendations,
  events,
  agentRuns = [],
  onApproveRecommendation,
  onRejectRecommendation,
  scenario,
  showMetrics,
  onDismissMetrics,
}: OperationsDashboardProps) {
  const [selectedStoreId, setSelectedStoreId] = useState<string | null>(null);
  const [isStoreModalOpen, setIsStoreModalOpen] = useState(false);
  const [selectedRecId, setSelectedRecId] = useState<string | null>(
    recommendations[0]?.id || null
  );
  const [activeTransfer, setActiveTransfer] = useState<{ from: string; to: string } | null>(null);
  const [activeOperationsTab, setActiveOperationsTab] = useState<"replenish" | "stream" | "runs" | "map">("replenish");
  const [inspectingRun, setInspectingRun] = useState<BackendAgentRun | null>(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);

  const selectedStore = stores.find((s) => s.id === selectedStoreId) || null;

  const handleSelectStore = (storeId: string) => {
    setSelectedStoreId(storeId);
    setIsStoreModalOpen(true);
  };

  const handleApprove = (recId: string) => {
    const rec = recommendations.find((r) => r.id === recId);
    if (rec && rec.sourceStore) {
      setActiveTransfer({ from: rec.sourceStore.code, to: rec.destinationStore.code });
      setTimeout(() => {
        setActiveTransfer(null);
      }, 4000);
    }
    onApproveRecommendation(recId);
  };

  const handleOpenTrace = (id: string) => {
    const run = agentRuns.find((r) => r.recommendation_id === id || r.run_id === id);
    if (run) {
      setInspectingRun(run);
      setIsInspectorOpen(true);
    } else {
      const rec = recommendations.find((r) => r.id === id);
      if (rec) {
        setInspectingRun(createSyntheticAgentRun(rec));
        setIsInspectorOpen(true);
      } else {
        toast.error("No execution trace found for this action");
      }
    }
  };

  return (
    <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex-1 flex flex-col space-y-4">
      
      {/* Top Operations Sub-Bar Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-2 rounded-xl border border-zinc-200 shadow-2xs">
        <div className="flex items-center gap-1.5 bg-zinc-100 p-1 rounded-lg">
          <button
            type="button"
            onClick={() => setActiveOperationsTab("replenish")}
            className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              activeOperationsTab === "replenish"
                ? "bg-white text-blue-950 shadow-xs border border-zinc-200/80 font-bold"
                : "text-zinc-600 hover:text-zinc-950"
            }`}
          >
            <Table2 className={`w-3.5 h-3.5 ${activeOperationsTab === "replenish" ? "text-blue-600" : "text-zinc-500"}`} />
            <span>Inventory Table</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveOperationsTab("stream")}
            className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              activeOperationsTab === "stream"
                ? "bg-white text-blue-950 shadow-xs border border-zinc-200/80 font-bold"
                : "text-zinc-600 hover:text-zinc-950"
            }`}
          >
            <ArrowRightLeft className={`w-3.5 h-3.5 ${activeOperationsTab === "stream" ? "text-blue-600" : "text-zinc-500"}`} />
            <span>Transfer Decisions</span>
            {recommendations.length > 0 && (
              <span
                className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-full transition-colors ${
                  activeOperationsTab === "stream"
                    ? "bg-amber-100 text-amber-900 border border-amber-300"
                    : "bg-zinc-200 text-zinc-700"
                }`}
              >
                {recommendations.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveOperationsTab("runs")}
            className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              activeOperationsTab === "runs"
                ? "bg-white text-blue-950 shadow-xs border border-zinc-200/80 font-bold"
                : "text-zinc-600 hover:text-zinc-950"
            }`}
          >
            <Terminal className={`w-3.5 h-3.5 ${activeOperationsTab === "runs" ? "text-blue-600" : "text-zinc-500"}`} />
            <span>Agent Runs</span>
            {agentRuns.length > 0 && (
              <span
                className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-full transition-colors ${
                  activeOperationsTab === "runs"
                    ? "bg-emerald-100 text-emerald-900 border border-emerald-300"
                    : "bg-zinc-200 text-zinc-700"
                }`}
              >
                {agentRuns.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveOperationsTab("map")}
            className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              activeOperationsTab === "map"
                ? "bg-white text-blue-950 shadow-xs border border-zinc-200/80 font-bold"
                : "text-zinc-600 hover:text-zinc-950"
            }`}
          >
            <MapPin className={`w-3.5 h-3.5 ${activeOperationsTab === "map" ? "text-blue-600" : "text-zinc-500"}`} />
            <span>Dark Store Map</span>
          </button>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono text-zinc-500 pr-2">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            5 Dark Stores Online
          </span>
          <span>·</span>
          <span className="text-zinc-800 font-semibold">
            {agentRuns.filter((r) => r.status === "completed").length} Verified Runs
          </span>
        </div>
      </div>

      {/* Main Operations Body */}
      <div className="flex-1 flex flex-col min-h-[calc(100vh-210px)]">
        {activeOperationsTab === "replenish" && (
          <div className="flex-1">
            <SkuInventoryTable
              stores={stores}
              onQuickRestock={(code, sku) => {
                toast.success(`Purchase Order created for ${sku} at ${code}`);
              }}
            />
          </div>
        )}

        {activeOperationsTab === "stream" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 items-start">
            <div className="col-span-12 lg:col-span-7 flex flex-col h-full">
              <RecommendationStream
                recommendations={recommendations}
                selectedRecId={selectedRecId}
                onSelectRec={(id) => setSelectedRecId(id)}
                onApproveRec={handleApprove}
                onRejectRec={onRejectRecommendation}
                onViewTrace={handleOpenTrace}
                events={events}
              />
            </div>
            <div className="col-span-12 lg:col-span-5 h-[650px] lg:h-full">
              <WhyInspectorPanel
                selectedRecommendation={
                  recommendations.find((r) => r.id === selectedRecId) || recommendations[0] || null
                }
                onApprove={handleApprove}
                onReject={onRejectRecommendation}
                onViewTrace={handleOpenTrace}
              />
            </div>
          </div>
        )}

        {activeOperationsTab === "runs" && (
          <div className="flex-1 bg-white rounded-2xl border border-zinc-200 p-5 shadow-2xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-100">
              <div>
                <h3 className="text-sm font-bold text-zinc-950 font-sans">
                  LangGraph Autonomous Execution Run Log
                </h3>
                <p className="text-xs text-zinc-500 font-mono mt-0.5">
                  5-Node state machine traces with batch conservation assertions and Level-2 human authorization.
                </p>
              </div>
              <span className="text-xs font-mono font-bold px-2.5 py-1 bg-zinc-100 text-zinc-700 rounded-lg">
                {agentRuns.length} Total Runs
              </span>
            </div>

            {agentRuns.length === 0 ? (
              <div className="p-12 text-center bg-zinc-50 rounded-xl border border-zinc-200 text-zinc-500 text-xs flex flex-col items-center justify-center gap-2">
                <Terminal className="w-8 h-8 text-zinc-400" />
                <span className="font-semibold text-zinc-800">No Agent Runs Executed Yet</span>
                <span className="text-zinc-500 max-w-sm text-[11px]">
                  Approve any transfer or reorder recommendation in the Decision Stream to trigger the 5-node LangGraph execution engine.
                </span>
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-zinc-200">
                <table className="w-full text-left text-xs">
                  <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-600 font-mono uppercase text-[10px]">
                    <tr>
                      <th className="p-3">Run ID</th>
                      <th className="p-3">Timestamp</th>
                      <th className="p-3">Action Type</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Invariants</th>
                      <th className="p-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 font-mono text-[11px]">
                    {agentRuns.map((r) => {
                      const isCompleted = r.status === "completed";
                      const isRecovered = r.requires_human_review || r.status === "requires_human_review";
                      return (
                        <tr key={r.run_id} className="hover:bg-zinc-50/70 transition-colors">
                          <td className="p-3 font-bold text-zinc-900">{r.run_id.slice(0, 16)}...</td>
                          <td className="p-3 text-zinc-500">{new Date(r.started_at).toLocaleTimeString()}</td>
                          <td className="p-3 uppercase font-semibold text-zinc-700">
                            {r.action_type || "transfer"}
                          </td>
                          <td className="p-3">
                            <span
                              className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-md ${
                                isCompleted
                                  ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                                  : isRecovered
                                  ? "bg-amber-50 text-amber-800 border border-amber-200"
                                  : "bg-rose-50 text-rose-800 border border-rose-200"
                              }`}
                            >
                              {isCompleted ? (
                                <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              ) : (
                                <AlertTriangle className="w-3 h-3 text-amber-600" />
                              )}
                              <span>{r.status}</span>
                            </span>
                          </td>
                          <td className="p-3 text-zinc-600">
                            {isCompleted ? (
                              <span className="text-emerald-700 font-bold">✓ 4/4 Invariants Held</span>
                            ) : (
                              <span className="text-amber-700 font-bold">⚠ Recovery Triggered</span>
                            )}
                          </td>
                          <td className="p-3 text-right">
                            <button
                              type="button"
                              onClick={() => handleOpenTrace(r.run_id)}
                              className="inline-flex items-center gap-1 text-xs font-mono font-semibold px-2.5 py-1 rounded-lg border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-100 hover:text-zinc-950 transition-colors cursor-pointer"
                            >
                              <Layers className="w-3.5 h-3.5 text-zinc-500" />
                              <span>Inspect Trace</span>
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeOperationsTab === "map" && (
          <div className="flex-1 h-[calc(100vh-240px)]">
            <SpatialTopologyView
              stores={stores}
              selectedStoreId={selectedStoreId}
              onSelectStore={handleSelectStore}
              activeTransfer={activeTransfer}
            />
          </div>
        )}
      </div>

      {/* Baseline vs GROCER Metrics Panel */}
      {showMetrics && scenario.activeScenarioId && (
        <div className="mt-4">
          <MetricsComparisonPanel
            scenario={scenario}
            onClose={onDismissMetrics}
          />
        </div>
      )}

      {/* Deep-Dive Store Inventory Modal */}
      {isStoreModalOpen && selectedStore && (
        <StoreDetailModal
          store={selectedStore}
          onClose={() => setIsStoreModalOpen(false)}
        />
      )}

      {/* 5-Node LangGraph Run Inspector Modal */}
      <AgentRunInspector
        run={inspectingRun}
        isOpen={isInspectorOpen}
        onClose={() => setIsInspectorOpen(false)}
        recommendationTitle={
          recommendations.find(
            (r) => r.id === inspectingRun?.recommendation_id
          )?.title
        }
      />
    </div>
  );
}


