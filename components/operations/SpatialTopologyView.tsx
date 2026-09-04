import React from "react";
import { DarkStore } from "../../lib/types";
import { ShieldCheck, AlertTriangle, AlertOctagon } from "lucide-react";

interface SpatialTopologyViewProps {
  stores: DarkStore[];
  selectedStoreId: string | null;
  onSelectStore: (storeId: string) => void;
  activeTransfer: { from: string; to: string } | null;
}

export function SpatialTopologyView({
  stores,
  selectedStoreId,
  onSelectStore,
  activeTransfer,
}: SpatialTopologyViewProps) {
  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-zinc-950 tracking-tight font-sans">
            Mumbai Dark Store Network Topology
          </h2>
          <p className="text-xs text-zinc-500 font-medium">5 Dark Stores · Mumbai Quick-Commerce Cluster</p>
        </div>
        <span className="text-[11px] font-mono bg-zinc-100 text-zinc-700 font-semibold px-2 py-0.5 rounded-md border border-zinc-200">
          Radius ~14 km
        </span>
      </div>

      {/* Interactive SVG Network Map */}
      <div className="relative w-full bg-white rounded-xl border border-zinc-200 p-4 shadow-2xs overflow-hidden">
        <div className="absolute top-3 left-3 text-[10px] font-mono text-zinc-400 uppercase tracking-wider z-10">
          Live Mesh Telemetry (SVG)
        </div>

        <svg viewBox="0 0 340 330" className="w-full h-[220px] select-none">
          {/* Subtle Grid Background */}
          <defs>
            <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#F4F4F5" strokeWidth="1" />
            </pattern>
            {/* Animated Gradient for Transfer Line */}
            <linearGradient id="transferGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#0284C7" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#38BDF8" stopOpacity="1" />
            </linearGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Static Mesh Inter-store Connection Lines */}
          {stores.map((s1, i) =>
            stores.slice(i + 1).map((s2) => (
              <line
                key={`${s1.id}-${s2.id}`}
                x1={s1.x}
                y1={s1.y}
                x2={s2.x}
                y2={s2.y}
                stroke="#E4E4E7"
                strokeWidth="1.2"
                strokeDasharray="3 3"
              />
            ))
          )}

          {/* Active Lateral Transfer Animated Flow Line */}
          {activeTransfer && (
            (() => {
              const fromStore = stores.find((s) => s.code === activeTransfer.from || s.id === activeTransfer.from);
              const toStore = stores.find((s) => s.code === activeTransfer.to || s.id === activeTransfer.to);
              if (!fromStore || !toStore) return null;

              return (
                <g>
                  {/* Glowing Track */}
                  <line
                    x1={fromStore.x}
                    y1={fromStore.y}
                    x2={toStore.x}
                    y2={toStore.y}
                    stroke="#0284C7"
                    strokeWidth="3"
                    strokeOpacity="0.4"
                  />
                  {/* Pulsing Animated Transfer Line */}
                  <line
                    x1={fromStore.x}
                    y1={fromStore.y}
                    x2={toStore.x}
                    y2={toStore.y}
                    stroke="url(#transferGrad)"
                    strokeWidth="2.5"
                    strokeDasharray="6 4"
                    className="animate-pulse"
                  />
                  {/* Moving Particle Circle */}
                  <circle
                    cx={(fromStore.x + toStore.x) / 2}
                    cy={(fromStore.y + toStore.y) / 2}
                    r="4"
                    fill="#0284C7"
                    className="animate-ping"
                  />
                </g>
              );
            })()
          )}

          {/* Store Nodes */}
          {stores.map((store) => {
            const isSelected = selectedStoreId === store.id;
            const hasCritical = store.stockoutRiskCount > 0 || store.status === "critical";
            const hasWarning = store.spoilageRiskCount > 0;

            return (
              <g
                key={store.id}
                className="cursor-pointer transition-transform duration-150 hover:scale-105"
                onClick={() => onSelectStore(store.id)}
              >
                {/* Outer Ring Pulse for Critical */}
                {hasCritical && (
                  <circle
                    cx={store.x}
                    cy={store.y}
                    r="16"
                    fill="#F43F5E"
                    fillOpacity="0.18"
                    className="animate-ping"
                  />
                )}

                {/* Outer Selection Highlight */}
                {isSelected && (
                  <circle
                    cx={store.x}
                    cy={store.y}
                    r="15"
                    fill="none"
                    stroke="#09090B"
                    strokeWidth="2"
                  />
                )}

                {/* Node Solid Circle */}
                <circle
                  cx={store.x}
                  cy={store.y}
                  r="10"
                  fill={hasCritical ? "#F43F5E" : hasWarning ? "#F59E0B" : "#10B981"}
                  stroke="#FFFFFF"
                  strokeWidth="2.5"
                  className="shadow-sm"
                />

                {/* Node Label Badge */}
                <rect
                  x={store.x - 22}
                  y={store.y + 13}
                  width="44"
                  height="16"
                  rx="4"
                  fill={isSelected ? "#09090B" : "#FFFFFF"}
                  stroke={isSelected ? "#09090B" : "#E4E4E7"}
                  strokeWidth="1"
                />
                <text
                  x={store.x}
                  y={store.y + 24}
                  textAnchor="middle"
                  fill={isSelected ? "#FFFFFF" : "#18181B"}
                  fontSize="8.5"
                  fontWeight="600"
                  fontFamily="sans-serif"
                >
                  {store.code}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Live Legend */}
        <div className="flex items-center justify-between pt-2 border-t border-zinc-100 text-[10px] font-mono text-zinc-500">
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Optimal</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span>Spoilage Warning</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            <span>Stockout Risk</span>
          </div>
        </div>
      </div>

      {/* Dark Store Network Cards List */}
      <div className="flex flex-col gap-2.5 overflow-y-auto pr-1">
        {stores.map((store) => {
          const isSelected = selectedStoreId === store.id;
          const isCritical = store.status === "critical" || store.stockoutRiskCount > 0;
          const isWarning = store.spoilageRiskCount > 0;

          return (
            <div
              key={store.id}
              onClick={() => onSelectStore(store.id)}
              className={`p-3.5 rounded-xl border transition-all duration-150 cursor-pointer active:scale-98 ${
                isSelected
                  ? "bg-emerald-50/70 border-emerald-500 ring-1 ring-emerald-500 text-zinc-950 shadow-xs"
                  : "bg-white text-zinc-900 border-zinc-200 hover:border-zinc-300 shadow-2xs"
              }`}
            >
              {/* Header row */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded ${
                      isSelected
                        ? "bg-emerald-100 text-emerald-900 border border-emerald-200"
                        : "bg-zinc-100 text-zinc-800 border border-zinc-200"
                    }`}
                  >
                    {store.code}
                  </span>
                  <span className="text-xs font-semibold tracking-tight">{store.name}</span>
                </div>

                {/* Status indicator */}
                {isCritical ? (
                  <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
                    <AlertOctagon className="w-3 h-3" />
                    Critical
                  </span>
                ) : isWarning ? (
                  <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                    <AlertTriangle className="w-3 h-3" />
                    Warning
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                    <ShieldCheck className="w-3 h-3" />
                    Healthy
                  </span>
                )}
              </div>

              {/* Inventory category health meters */}
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between text-[10.5px] font-medium">
                  <span className="text-zinc-500">Dairy & Perishables</span>
                  <span className="font-mono text-zinc-800">{store.inventoryHealth.dairy}%</span>
                </div>
                <div className="w-full h-1.5 rounded-full overflow-hidden bg-zinc-100">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      store.inventoryHealth.dairy < 50
                        ? "bg-rose-500"
                        : store.inventoryHealth.dairy < 75
                        ? "bg-amber-500"
                        : "bg-emerald-500"
                    }`}
                    style={{ width: `${store.inventoryHealth.dairy}%` }}
                  />
                </div>

                <div className="flex items-center justify-between text-[10px] text-zinc-400 pt-1 font-mono">
                  <span>Capacity Excess: +{store.excessCapacityUnits} u</span>
                  <span>{store.activeBatches} Active Batches</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
