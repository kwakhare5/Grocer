import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { DarkStore } from "../../lib/types";
import { X, MapPin } from "lucide-react";

interface StoreDetailModalProps {
  store: DarkStore | null;
  onClose: () => void;
}

export function StoreDetailModal({ store, onClose }: StoreDetailModalProps) {
  if (!store) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
        onClick={onClose}
        className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ type: "spring", damping: 30, stiffness: 400 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-white w-full max-w-2xl rounded-2xl border border-zinc-200 shadow-xl overflow-hidden flex flex-col max-h-[85vh]"
        >
        
        {/* Modal Header */}
        <div className="p-5 border-b border-zinc-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono font-bold px-2 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-md">
              {store.code}
            </span>
            <div>
              <h2 className="text-base font-bold text-zinc-950">{store.name}</h2>
              <div className="flex items-center gap-1 text-xs text-zinc-500 font-mono">
                <MapPin className="w-3 h-3 text-zinc-400" />
                <span>{store.location}</span>
                <span>·</span>
                <span>{store.lat}, {store.lng}</span>
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto space-y-5">
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-4 gap-3 text-center">
            <div className="p-3 rounded-xl bg-zinc-50 border border-zinc-100">
              <span className="text-[10.5px] font-mono text-zinc-500 block">Total Catalog</span>
              <span className="text-base font-bold text-zinc-950 font-mono">{store.totalSkus} SKUs</span>
            </div>
            <div className="p-3 rounded-xl bg-zinc-50 border border-zinc-100">
              <span className="text-[10.5px] font-mono text-zinc-500 block">Active Batches</span>
              <span className="text-base font-bold text-zinc-950 font-mono">{store.activeBatches}</span>
            </div>
            <div className="p-3 rounded-xl bg-zinc-50 border border-zinc-100">
              <span className="text-[10.5px] font-mono text-zinc-500 block">Stockout Risk</span>
              <span className={`text-base font-bold font-mono ${store.stockoutRiskCount > 0 ? "text-rose-600" : "text-emerald-600"}`}>
                {store.stockoutRiskCount} SKUs
              </span>
            </div>
            <div className="p-3 rounded-xl bg-zinc-50 border border-zinc-100">
              <span className="text-[10.5px] font-mono text-zinc-500 block">Excess Transfer</span>
              <span className="text-base font-bold text-sky-600 font-mono">+{store.excessCapacityUnits} u</span>
            </div>
          </div>

          {/* Category Inventory Breakdown */}
          <div className="space-y-2.5">
            <h3 className="text-xs font-bold text-zinc-900 uppercase tracking-wider font-mono">
              Category Fill Rates & Freshness
            </h3>
            <div className="space-y-2">
              {Object.entries(store.inventoryHealth).map(([cat, health]) => (
                <div key={cat} className="space-y-1">
                  <div className="flex justify-between text-xs font-medium">
                    <span className="capitalize text-zinc-700">{cat}</span>
                    <span className="font-mono text-zinc-900 font-semibold">{health}%</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-zinc-100 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${
                        health < 50 ? "bg-rose-500" : health < 75 ? "bg-amber-500" : "bg-emerald-500"
                      }`}
                      style={{ width: `${health}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Active Perishable Batch Inventory Sample */}
          <div className="space-y-2.5">
            <h3 className="text-xs font-bold text-zinc-900 uppercase tracking-wider font-mono">
              Active Perishable Batches & Expiry Countdown
            </h3>
            <div className="border border-zinc-200 rounded-xl overflow-hidden text-xs">
              <table className="w-full text-left">
                <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-500 font-mono text-[11px]">
                  <tr>
                    <th className="p-2.5 pl-3">Product</th>
                    <th className="p-2.5">Batch ID</th>
                    <th className="p-2.5">Stock</th>
                    <th className="p-2.5 pr-3">Hours Left</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 font-mono text-zinc-800 text-[11.5px]">
                  <tr>
                    <td className="p-2.5 pl-3 font-sans font-medium text-zinc-900">Full Cream Milk 1L</td>
                    <td className="p-2.5 text-zinc-500">BATCH-482</td>
                    <td className="p-2.5">8 units</td>
                    <td className="p-2.5 pr-3 text-rose-600 font-bold">5.2h (Critical)</td>
                  </tr>
                  <tr>
                    <td className="p-2.5 pl-3 font-sans font-medium text-zinc-900">Artisan Sourdough</td>
                    <td className="p-2.5 text-zinc-500">BATCH-391</td>
                    <td className="p-2.5">14 loaves</td>
                    <td className="p-2.5 pr-3 text-amber-600 font-bold">8.5h (20% Off)</td>
                  </tr>
                  <tr>
                    <td className="p-2.5 pl-3 font-sans font-medium text-zinc-900">Farm Fresh Eggs 6pk</td>
                    <td className="p-2.5 text-zinc-500">BATCH-512</td>
                    <td className="p-2.5">22 packs</td>
                    <td className="p-2.5 pr-3 text-emerald-600">48h (Healthy)</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-zinc-50 border-t border-zinc-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-white hover:bg-zinc-100 text-zinc-700 border border-zinc-200 shadow-2xs rounded-xl font-semibold text-xs transition-colors cursor-pointer"
          >
            Close Inspector
          </button>
        </div>

      </motion.div>
    </motion.div>
  </AnimatePresence>
);
}
