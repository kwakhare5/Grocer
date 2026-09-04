import React, { useState } from "react";
import { DarkStore, RecommendationItem, SimulationEvent, SimulationState, ScenarioState } from "../../lib/types";
import { SpatialTopologyView } from "./SpatialTopologyView";
import { RecommendationStream } from "./RecommendationStream";
import { SkuInventoryTable } from "./SkuInventoryTable";
import { WhyInspectorPanel } from "./WhyInspectorPanel";
import { StoreDetailModal } from "./StoreDetailModal";
import { MetricsComparisonPanel } from "./MetricsComparisonPanel";
import { Table2, ArrowRightLeft, MapPin } from "lucide-react";
import { toast } from "sonner";

interface OperationsDashboardProps {
  stores: DarkStore[];
  recommendations: RecommendationItem[];
  events: SimulationEvent[];
  simulation: SimulationState;
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
  const [activeOperationsTab, setActiveOperationsTab] = useState<"replenish" | "stream" | "map">("replenish");

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
          <span>10-min Service Level Target</span>
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
              />
            </div>
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
    </div>
  );
}


