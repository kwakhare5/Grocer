import React from "react";
import { motion } from "framer-motion";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { ScenarioState } from "../../lib/types";
import { computeDeltas, MetricDelta } from "../../lib/metricsEngine";
import { SCENARIOS } from "../../lib/scenarioEngine";
import { TrendingDown, TrendingUp, ArrowRight, Info } from "lucide-react";

interface MetricsComparisonPanelProps {
  scenario: ScenarioState;
  onClose: () => void;
}

export function MetricsComparisonPanel({
  scenario,
  onClose,
}: MetricsComparisonPanelProps) {
  const activeScenario = SCENARIOS.find((s) => s.id === scenario.activeScenarioId);
  const deltas = computeDeltas(scenario.baselineMetrics, scenario.grocerMetrics);

  // Prepare chart data for recharts
  const chartData = deltas.map((d) => ({
    name: d.label,
    Baseline: d.baseline,
    GROCER: d.grocer,
    delta: d.delta,
    lowerIsBetter: d.lowerIsBetter,
    unit: d.unit,
  }));

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
      className="bg-white rounded-2xl border border-zinc-200 shadow-md overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 bg-zinc-50/50">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold text-zinc-950 uppercase tracking-wider font-sans">
            Baseline vs GROCER Comparison
          </h3>
          <span className="text-[10px] font-mono text-zinc-500">Benchmark Evaluation</span>
        </div>
        <div className="flex items-center gap-2">
          {activeScenario && (
            <span className="text-[10px] font-mono font-bold bg-emerald-50 text-emerald-800 border border-emerald-200 px-2.5 py-0.5 rounded-full">
              {activeScenario.name}
            </span>
          )}
          <button
            onClick={onClose}
            className="text-xs text-zinc-500 hover:text-zinc-900 font-semibold px-2 py-1 hover:bg-zinc-100 rounded-lg transition-colors cursor-pointer active:scale-97"
          >
            Close
          </button>
        </div>
      </div>

      {/* Metrics Chart */}
      <div className="px-4 py-4">
        <div className="h-[240px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 4, right: 20, left: 100, bottom: 4 }}
              barGap={2}
              barCategoryGap="25%"
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#E4E4E7" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10, fontFamily: "monospace" }} stroke="#A1A1AA" />
              <YAxis
                dataKey="name"
                type="category"
                tick={{ fontSize: 10, fontFamily: "monospace", fill: "#3F3F46" }}
                width={95}
                stroke="transparent"
              />
              <Tooltip
                contentStyle={{
                  fontSize: 11,
                  fontFamily: "monospace",
                  borderRadius: 10,
                  border: "1px solid #E4E4E7",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                }}
                formatter={(value) => [String(value ?? 0), undefined]}
              />
              <Bar dataKey="Baseline" radius={[0, 4, 4, 0]} maxBarSize={14}>
                {chartData.map((_, index) => (
                  <Cell key={`baseline-${index}`} fill="#D4D4D8" />
                ))}
              </Bar>
              <Bar dataKey="GROCER" radius={[0, 4, 4, 0]} maxBarSize={14}>
                {chartData.map((entry, index) => {
                  const isImproved = entry.lowerIsBetter
                    ? entry.GROCER < entry.Baseline
                    : entry.GROCER > entry.Baseline;
                  return <Cell key={`grocer-${index}`} fill={isImproved ? "#10B981" : "#F59E0B"} />;
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Delta Badges Grid */}
      <div className="px-4 pb-4">
        <div className="grid grid-cols-4 gap-2">
          {deltas.map((d) => (
            <DeltaBadge key={d.key} delta={d} />
          ))}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="px-4 py-2.5 bg-zinc-50 border-t border-zinc-100 flex items-start gap-2">
        <Info className="w-3.5 h-3.5 text-zinc-400 shrink-0 mt-0.5" />
        <div className="text-[10px] text-zinc-500 leading-snug">
          <span className="font-semibold">Disclaimer:</span> All numbers are simulation results, not
          real-world company claims. The baseline uses a simple reorder-point policy (reorder at ≤20% stock,
          no inter-store transfers, no discounts, fixed supplier lead times) and is not tuned to make GROCER
          look artificially favorable.
        </div>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Delta Badge Sub-Component
// ---------------------------------------------------------------------------

function DeltaBadge({ delta }: { delta: MetricDelta }) {
  const isImproved = delta.delta > 0;
  const isNeutral = delta.delta === 0;

  return (
    <div
      className={`p-2 rounded-xl border text-center ${
        isNeutral
          ? "bg-zinc-50 border-zinc-200"
          : isImproved
          ? "bg-emerald-50/70 border-emerald-200"
          : "bg-amber-50/70 border-amber-200"
      }`}
    >
      <div className="text-[10px] text-zinc-500 font-mono font-medium truncate">{delta.label}</div>
      <div className="flex items-center justify-center gap-1 mt-1">
        {isNeutral ? (
          <ArrowRight className="w-3 h-3 text-zinc-400" />
        ) : isImproved ? (
          <TrendingDown className="w-3 h-3 text-emerald-600" />
        ) : (
          <TrendingUp className="w-3 h-3 text-amber-600" />
        )}
        <span
          className={`text-sm font-bold font-mono ${
            isNeutral
              ? "text-zinc-600"
              : isImproved
              ? "text-emerald-700"
              : "text-amber-700"
          }`}
        >
          {isNeutral ? "—" : `${isImproved ? "↓" : "↑"} ${Math.abs(delta.delta)}%`}
        </span>
      </div>
      <div className="text-[9px] font-mono text-zinc-400 mt-0.5">
        {delta.baseline} → {delta.grocer} {delta.unit}
      </div>
    </div>
  );
}
