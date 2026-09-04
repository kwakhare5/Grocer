"use client";

import React, { useState } from "react";
import { DarkStore } from "../../lib/types";
import {
  Search,
  AlertTriangle,
  CheckCircle2,
  Flame,
  Truck,
  PlusCircle,
  TrendingDown,
  Building2,
} from "lucide-react";

import { INITIAL_STORES } from "../../lib/mockData";

interface SkuInventoryTableProps {
  stores?: DarkStore[];
  onQuickRestock?: (storeCode: string, skuName: string) => void;
}

interface SkuRowItem {
  id: string;
  sku: string;
  name: string;
  category: "Dairy" | "Produce" | "Bakery" | "Poultry" | "Pantry";
  storeName: string;
  storeCode: string;
  availableStock: number;
  desiredStock: number;
  dailyDemand: number;
  leadTimeHours: number;
  suggestedRestock: number;
  unitCostINR: number;
  status: "critical" | "warning" | "healthy" | "excess";
  daysOfStock: number;
}

interface SkuCatalogItem {
  sku: string;
  name: string;
  category: "Dairy" | "Produce" | "Bakery" | "Poultry" | "Pantry";
  desiredStock: number;
  dailyDemand: number;
  leadTimeHours: number;
  unitCostINR: number;
  categoryKey: "dairy" | "produce" | "bakery" | "staples" | "packaged";
}

const CATALOG_ITEMS: SkuCatalogItem[] = [
  {
    sku: "AMUL-TZ-1L",
    name: "Amul Taaza Homogenised Toned Milk 1L",
    category: "Dairy",
    categoryKey: "dairy",
    desiredStock: 80,
    dailyDemand: 48,
    leadTimeHours: 14,
    unitCostINR: 66,
  },
  {
    sku: "TOMATO-HYB-500",
    name: "Fresh Farm Hybrid Tomatoes 500g",
    category: "Produce",
    categoryKey: "produce",
    desiredStock: 60,
    dailyDemand: 32,
    leadTimeHours: 12,
    unitCostINR: 32,
  },
  {
    sku: "BREAD-WHT-400",
    name: "Harvest Gold Whole Wheat Bread 400g",
    category: "Bakery",
    categoryKey: "bakery",
    desiredStock: 40,
    dailyDemand: 18,
    leadTimeHours: 8,
    unitCostINR: 50,
  },
  {
    sku: "EGGS-FRM-12",
    name: "Farm Fresh Table Eggs (12 pcs tray)",
    category: "Poultry",
    categoryKey: "staples",
    desiredStock: 50,
    dailyDemand: 22,
    leadTimeHours: 16,
    unitCostINR: 90,
  },
  {
    sku: "AMUL-TZ-500",
    name: "Amul Taaza Toned Milk Pouch 500ml",
    category: "Dairy",
    categoryKey: "dairy",
    desiredStock: 90,
    dailyDemand: 55,
    leadTimeHours: 14,
    unitCostINR: 34,
  },
  {
    sku: "PANEER-FRSH-200",
    name: "Malai Fresh Paneer Vacuum Pack 200g",
    category: "Dairy",
    categoryKey: "dairy",
    desiredStock: 35,
    dailyDemand: 20,
    leadTimeHours: 10,
    unitCostINR: 95,
  },
  {
    sku: "CURD-AMUL-400",
    name: "Amul Masti Dahi Tub 400g",
    category: "Dairy",
    categoryKey: "dairy",
    desiredStock: 30,
    dailyDemand: 14,
    leadTimeHours: 12,
    unitCostINR: 45,
  },
  {
    sku: "ONION-RED-1KG",
    name: "Nashik Red Onions 1kg Mesh Bag",
    category: "Produce",
    categoryKey: "produce",
    desiredStock: 50,
    dailyDemand: 25,
    leadTimeHours: 12,
    unitCostINR: 38,
  },
  {
    sku: "BUTTER-AMUL-500",
    name: "Amul Pasteurised Butter 500g Block",
    category: "Dairy",
    categoryKey: "dairy",
    desiredStock: 40,
    dailyDemand: 16,
    leadTimeHours: 10,
    unitCostINR: 275,
  },
  {
    sku: "OIL-SUN-1L",
    name: "Fortune Sunflower Oil Pouch 1L",
    category: "Pantry",
    categoryKey: "staples",
    desiredStock: 45,
    dailyDemand: 15,
    leadTimeHours: 14,
    unitCostINR: 165,
  },
];

export function SkuInventoryTable({ stores, onQuickRestock }: SkuInventoryTableProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [activeStoreTab, setActiveStoreTab] = useState<string>("ALL");
  const [categoryFilter, setCategoryFilter] = useState<string>("All");
  const [statusFilter, setStatusFilter] = useState<string>("All");

  const storeList = stores && stores.length > 0 ? stores : INITIAL_STORES;

  const storeTabs = React.useMemo(() => {
    return [
      { id: "ALL", name: `All Fleet Nodes (${storeList.length})` },
      ...storeList.map((s) => ({ id: s.name, name: s.name })),
    ];
  }, [storeList]);

  const allItems: SkuRowItem[] = React.useMemo(() => {
    const generated: SkuRowItem[] = [];

    storeList.forEach((store) => {
      CATALOG_ITEMS.forEach((catItem) => {
        const health = store.inventoryHealth?.[catItem.categoryKey] ?? 85;

        // Dynamic available stock derived from real-time health %
        let availableStock = Math.round((health / 100) * catItem.desiredStock);

        // Store-specific risk adjustments matching simulation triggers
        if (store.status === "critical" && catItem.categoryKey === "dairy") {
          availableStock = Math.min(availableStock, 2);
        } else if (health < 40) {
          availableStock = Math.max(1, Math.min(availableStock, 5));
        } else if (health > 90 && store.excessCapacityUnits > 35 && catItem.sku === "BREAD-WHT-400") {
          availableStock = Math.round(catItem.desiredStock * 1.5);
        }

        const daysOfStock = Number((availableStock / Math.max(1, catItem.dailyDemand)).toFixed(1));

        let status: "critical" | "warning" | "healthy" | "excess" = "healthy";
        if (availableStock <= 5 || daysOfStock < 0.25 || health < 45) {
          status = "critical";
        } else if (availableStock < catItem.desiredStock * 0.45 || daysOfStock < 0.65 || health < 65) {
          status = "warning";
        } else if (availableStock > catItem.desiredStock * 1.35) {
          status = "excess";
        }

        const suggestedRestock =
          status === "critical" || status === "warning"
            ? Math.max(0, catItem.desiredStock - availableStock)
            : 0;

        generated.push({
          id: `${store.id}-${catItem.sku}`,
          sku: catItem.sku,
          name: catItem.name,
          category: catItem.category,
          storeName: store.name,
          storeCode: store.code,
          availableStock,
          desiredStock: catItem.desiredStock,
          dailyDemand: catItem.dailyDemand,
          leadTimeHours: catItem.leadTimeHours,
          suggestedRestock,
          unitCostINR: catItem.unitCostINR,
          status,
          daysOfStock,
        });
      });
    });

    return generated;
  }, [storeList]);

  const filteredItems = allItems.filter((item) => {
    const matchesSearch =
      item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.storeName.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStore = activeStoreTab === "ALL" || item.storeName === activeStoreTab;
    const matchesCategory = categoryFilter === "All" || item.category === categoryFilter;
    const matchesStatus = statusFilter === "All" || item.status === statusFilter;

    return matchesSearch && matchesStore && matchesCategory && matchesStatus;
  });

  const totalCriticalValue = filteredItems
    .filter((i) => i.status === "critical" || i.status === "warning")
    .reduce((acc, curr) => acc + curr.suggestedRestock * curr.unitCostINR, 0);

  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-2xs flex flex-col h-full overflow-hidden">
      {/* Top Header & Store Fleet Filter Tabs */}
      <div className="p-4 border-b border-zinc-200 flex flex-col gap-3.5 bg-white">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <h2 className="text-sm sm:text-base font-bold text-zinc-950 font-sans tracking-tight">
                Dark Store Stock Replenishment
              </h2>
              <span className="text-[10px] font-mono font-bold bg-zinc-100 text-zinc-700 px-2 py-0.5 rounded border border-zinc-200">
                {filteredItems.length} SKUs Active
              </span>
            </div>
            <p className="text-xs text-zinc-500 font-normal">
              Continuous consumption velocity tracking and safety buffer forecasting across Mumbai network
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-zinc-500 font-medium">Pending Restock:</span>
            <span className="text-xs font-mono font-bold text-orange-900 bg-orange-50 px-2.5 py-1 rounded border border-orange-200">
              ₹{totalCriticalValue.toLocaleString("en-IN")}
            </span>
          </div>
        </div>

        {/* Store Fleet Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 border-b border-zinc-100 text-xs">
          {storeTabs.map((tab) => {
            const isSelected = activeStoreTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveStoreTab(tab.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                  isSelected
                    ? "bg-blue-600 text-white shadow-xs font-bold"
                    : "text-zinc-600 hover:text-zinc-950 hover:bg-zinc-100"
                }`}
              >
                {tab.name}
              </button>
            );
          })}
        </div>

        {/* Search & Quick Filters Bar */}
        <div className="flex flex-wrap items-center gap-2.5 pt-0.5">
          {/* Search Box */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search product, SKU ID, or store..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-zinc-50 border border-zinc-200 rounded-lg text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-1 focus:ring-zinc-950 focus:bg-white transition-all font-sans"
            />
          </div>

          {/* Category Dropdown */}
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="text-xs bg-zinc-50 border border-zinc-200 rounded-lg px-2.5 py-1.5 text-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-950 cursor-pointer"
          >
            <option value="All">All Categories</option>
            <option value="Dairy">Dairy</option>
            <option value="Produce">Produce</option>
            <option value="Bakery">Bakery</option>
            <option value="Poultry">Poultry</option>
          </select>

          {/* Status Dropdown */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs bg-zinc-50 border border-zinc-200 rounded-lg px-2.5 py-1.5 text-zinc-700 focus:outline-none focus:ring-1 focus:ring-zinc-950 cursor-pointer"
          >
            <option value="All">All Stock Levels</option>
            <option value="critical">Critical (&lt;4h)</option>
            <option value="warning">Low Stock (&lt;12h)</option>
            <option value="healthy">Healthy Stock</option>
            <option value="excess">Excess Stock</option>
          </select>
        </div>
      </div>

      {/* High-Density Replenishment Matrix Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead className="sticky top-0 bg-zinc-50/95 backdrop-blur-xs border-b border-zinc-200 text-zinc-500 font-mono text-[11px] uppercase tracking-wider z-10">
            <tr>
              <th className="py-2.5 px-4 font-semibold">Product & SKU</th>
              <th className="py-2.5 px-3 font-semibold">Dark Store</th>
              <th className="py-2.5 px-3 text-right font-semibold">Avail / Target</th>
              <th className="py-2.5 px-3 text-right font-semibold">Daily Demand</th>
              <th className="py-2.5 px-3 text-right font-semibold">Lead Time</th>
              <th className="py-2.5 px-3 text-right font-semibold">Suggested Restock</th>
              <th className="py-2.5 px-3 font-semibold">Status</th>
              <th className="py-2.5 px-4 text-right font-semibold">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 font-sans">
            {filteredItems.map((item) => (
              <tr key={item.id} className="hover:bg-zinc-50/70 transition-colors">
                {/* Product Name & SKU */}
                <td className="py-3 px-4">
                  <div className="font-semibold text-zinc-950 max-w-[240px] truncate" title={item.name}>
                    {item.name}
                  </div>
                  <div className="text-[10.5px] font-mono text-zinc-400 flex items-center gap-1.5 pt-0.5">
                    <span>{item.sku}</span>
                    <span>·</span>
                    <span className="text-zinc-600 font-semibold">₹{item.unitCostINR}</span>
                  </div>
                </td>

                {/* Dark Store Node */}
                <td className="py-3 px-3">
                  <div className="flex items-center gap-1.5">
                    <Building2 className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                    <div>
                      <span className="font-semibold text-zinc-800 text-[11.5px] block">
                        {item.storeName}
                      </span>
                      <span className="font-mono text-[10px] text-zinc-400 block">
                        {item.storeCode}
                      </span>
                    </div>
                  </div>
                </td>

                {/* Available vs Target Ratio Bar */}
                <td className="py-3 px-3 text-right font-mono">
                  <div className="flex flex-col items-end gap-1">
                    <div>
                      <span
                        className={`font-bold ${
                          item.availableStock <= 5
                            ? "text-rose-600"
                            : item.availableStock > item.desiredStock
                            ? "text-purple-700"
                            : "text-zinc-900"
                        }`}
                      >
                        {item.availableStock}
                      </span>
                      <span className="text-zinc-400 text-[10.5px]"> / {item.desiredStock}</span>
                    </div>
                    <div className="w-16 h-1 bg-zinc-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          item.status === "critical"
                            ? "bg-rose-500"
                            : item.status === "warning"
                            ? "bg-amber-500"
                            : item.status === "excess"
                            ? "bg-purple-600"
                            : "bg-emerald-600"
                        }`}
                        style={{
                          width: `${Math.min(100, (item.availableStock / item.desiredStock) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                </td>

                {/* Daily Demand Velocity */}
                <td className="py-3 px-3 text-right font-mono text-zinc-700">
                  <span className="font-semibold">{item.dailyDemand}</span>
                  <span className="text-[10px] text-zinc-400 ml-1">u/day</span>
                </td>

                {/* Lead Time */}
                <td className="py-3 px-3 text-right font-mono text-zinc-600">
                  <span>{item.leadTimeHours}h</span>
                </td>

                {/* Suggested Restock (Delta) */}
                <td className="py-3 px-3 text-right font-mono">
                  {item.suggestedRestock > 0 ? (
                    <div>
                      <span className="font-bold text-blue-900">+{item.suggestedRestock} units</span>
                      <div className="text-[10px] text-zinc-400">
                        ₹{(item.suggestedRestock * item.unitCostINR).toLocaleString("en-IN")}
                      </div>
                    </div>
                  ) : (
                    <span className="text-zinc-400">—</span>
                  )}
                </td>

                {/* Status Badge */}
                <td className="py-3 px-3">
                  {item.status === "critical" ? (
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                      <Flame className="w-2.5 h-2.5" />
                      Critical (&lt;4h)
                    </span>
                  ) : item.status === "warning" ? (
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                      <AlertTriangle className="w-2.5 h-2.5" />
                      Low Stock
                    </span>
                  ) : item.status === "excess" ? (
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold text-purple-700 bg-purple-50 px-2 py-0.5 rounded border border-purple-200">
                      Excess ({item.daysOfStock}d)
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
                      Healthy
                    </span>
                  )}
                </td>

                {/* Action Trigger */}
                <td className="py-3 px-4 text-right">
                  {item.suggestedRestock > 0 ? (
                    <button
                      type="button"
                      onClick={() => onQuickRestock && onQuickRestock(item.storeCode, item.name)}
                      className="inline-flex items-center gap-1.5 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg transition-all cursor-pointer active:scale-95 shadow-2xs"
                    >
                      <PlusCircle className="w-3.5 h-3.5 text-blue-200" />
                      <span>Create PO</span>
                    </button>
                  ) : item.status === "excess" ? (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 text-xs font-semibold text-purple-900 bg-purple-50 hover:bg-purple-100 px-2.5 py-1.5 rounded-lg border border-purple-200 transition-all cursor-pointer"
                    >
                      <TrendingDown className="w-3 h-3 text-purple-600" />
                      <span>Markdown</span>
                    </button>
                  ) : (
                    <span className="text-[11px] text-zinc-400 font-mono">Nominal</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer Info Bar */}
      <div className="p-3 bg-zinc-50 border-t border-zinc-200 flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-zinc-500">
        <div className="flex items-center gap-2">
          <Truck className="w-3.5 h-3.5 text-zinc-400" />
          <span>Replenishment model evaluates demand velocity continuously</span>
        </div>
        <div className="flex items-center gap-3 text-zinc-700 font-medium">
          <span>Lead Time Buffer: 14h Avg</span>
          <span>·</span>
          <span>Inter-Store Couriers: Active</span>
        </div>
      </div>
    </div>
  );
}

