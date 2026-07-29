"use client";

import { useState, useEffect, useMemo, useSyncExternalStore } from "react";
import {
  Zap,
  Calendar,
  Users,
  Coffee,
  Loader2,
  BarChart3,
  TrendingUp,
  DollarSign,
  Clock,
  MessageSquare
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine
} from "recharts";
import { householdApi, predictionsApi, APIPrediction } from "../lib/api";
import { toast } from "sonner";
import clsx from "clsx";

interface ExecutivePanelProps {
  activeScenario: string;
  onScenarioChange: (scenario: string) => void;
}

const GMV_RECOVERY_DATA = [
  { month: "Month 1", baseline: 3200, recovered: 450 },
  { month: "Month 2", baseline: 3400, recovered: 820 },
  { month: "Month 3", baseline: 3300, recovered: 1250 },
  { month: "Month 4", baseline: 3500, recovered: 1450 },
];

const RETENTION_DATA = [
  { day: "Day 0", standard: 100, prefill: 100 },
  { day: "Day 15", standard: 75, prefill: 94 },
  { day: "Day 30", standard: 52, prefill: 90 },
  { day: "Day 60", standard: 34, prefill: 86 },
  { day: "Day 90", standard: 24, prefill: 82 },
];

const emptySubscribe = () => () => {};

export default function ExecutivePanel({ activeScenario, onScenarioChange }: ExecutivePanelProps) {
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false);
  const [switching, setSwitching] = useState(false);
  const [realPredictions, setRealPredictions] = useState<APIPrediction[]>([]);
  const [loadingPredictions, setLoadingPredictions] = useState(true);
  const [activeChartView, setActiveChartView] = useState<"gmv" | "retention" | "depletion">("gmv");

  // Fetch real backend prediction data
  useEffect(() => {
    async function loadData() {
      try {
        setLoadingPredictions(true);
        const res = await predictionsApi.getForHousehold("demo_user_001");
        if (res.data?.predictions && res.data.predictions.length > 0) {
          setRealPredictions(res.data.predictions);
        }
      } catch {
        // Silently use baseline prediction dataset when backend is unpowered
      } finally {
        setLoadingPredictions(false);
      }
    }
    loadData();
  }, [activeScenario]);

  const scenarios = [
    {
      id: "standard",
      title: "Standard Staples",
      desc: "7-day depletion slope.",
      icon: Calendar,
      badge: "Baseline"
    },
    {
      id: "party",
      title: "Party Spike Anomaly",
      desc: "Consumption accelerates 2.5x.",
      icon: Users,
      badge: "Spike Anomaly"
    },
    {
      id: "vacation",
      title: "Vacation Travel Mode",
      desc: "Zero stock consumption.",
      icon: Coffee,
      badge: "Travel Pause"
    }
  ];

  const handleSwitch = async (id: string) => {
    if (switching || activeScenario === id) return;
    setSwitching(true);

    try {
      await householdApi.switchScenario("demo_user_001", id);
      onScenarioChange(id);
      toast.success(`Scenario set to ${id.toUpperCase()}`);
      window.dispatchEvent(new CustomEvent("scenario-switched", { detail: { scenario: id } }));
      window.dispatchEvent(new CustomEvent("refresh-dashboard"));
    } catch {
      toast.error("Failed to switch scenario");
    } finally {
      setSwitching(false);
    }
  };

  // Generate real data depletion series from backend predictions or active scenario
  const depletionChartData = useMemo(() => {
    if (realPredictions.length > 0) {
      const topItem = realPredictions[0];
      const stock = topItem.stock_fill_percent ?? 100;
      const days = topItem.days_remaining ?? 7;
      const step = stock / Math.max(days, 1);

      return Array.from({ length: 7 }, (_, i) => ({
        day: `Day ${i + 1}`,
        stock: Math.max(0, Math.round(stock - step * i)),
        threshold: 20
      }));
    }

    if (activeScenario === "party") {
      return [
        { day: "Day 1", stock: 100, threshold: 20 },
        { day: "Day 2", stock: 65, threshold: 20 },
        { day: "Day 3", stock: 30, threshold: 20 },
        { day: "Day 4", stock: 8, threshold: 20 },
        { day: "Day 5", stock: 0, threshold: 20 },
        { day: "Day 6", stock: 0, threshold: 20 },
        { day: "Day 7", stock: 0, threshold: 20 },
      ];
    } else if (activeScenario === "vacation") {
      return [
        { day: "Day 1", stock: 100, threshold: 20 },
        { day: "Day 2", stock: 100, threshold: 20 },
        { day: "Day 3", stock: 100, threshold: 20 },
        { day: "Day 4", stock: 100, threshold: 20 },
        { day: "Day 5", stock: 100, threshold: 20 },
        { day: "Day 6", stock: 100, threshold: 20 },
        { day: "Day 7", stock: 100, threshold: 20 },
      ];
    }

    return [
      { day: "Day 1", stock: 100, threshold: 20 },
      { day: "Day 2", stock: 85, threshold: 20 },
      { day: "Day 3", stock: 68, threshold: 20 },
      { day: "Day 4", stock: 50, threshold: 20 },
      { day: "Day 5", stock: 32, threshold: 20 },
      { day: "Day 6", stock: 16, threshold: 20 },
      { day: "Day 7", stock: 4, threshold: 20 },
    ];
  }, [realPredictions, activeScenario]);

  return (
    <div className="flex flex-col gap-6">

      {/* ── 4 Top KPI Summary Cards ───────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4">
        
        {/* KPI 1 */}
        <div className="p-4 rounded-2xl bg-white border border-stone-200/90 shadow-2xs flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-stone-500 font-mono uppercase">Recaptured GMV</span>
            <span className="p-1.5 rounded-lg bg-emerald-50 text-emerald-700">
              <DollarSign className="h-3.5 w-3.5" />
            </span>
          </div>
          <div className="text-2xl font-extrabold text-[#252525] font-sans tracking-tight">+₹1,450</div>
          <div className="text-[10px] font-semibold text-emerald-700 font-mono">↑ 38.4% monthly per household</div>
        </div>

        {/* KPI 2 */}
        <div className="p-4 rounded-2xl bg-white border border-stone-200/90 shadow-2xs flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-stone-500 font-mono uppercase">90-Day Retention</span>
            <span className="p-1.5 rounded-lg bg-blue-50 text-blue-700">
              <TrendingUp className="h-3.5 w-3.5" />
            </span>
          </div>
          <div className="text-2xl font-extrabold text-[#252525] font-sans tracking-tight">82.4%</div>
          <div className="text-[10px] font-semibold text-blue-700 font-mono">vs 24.0% standard quick commerce</div>
        </div>

        {/* KPI 3 */}
        <div className="p-4 rounded-2xl bg-white border border-stone-200/90 shadow-2xs flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-stone-500 font-mono uppercase">Restock SLA Latency</span>
            <span className="p-1.5 rounded-lg bg-amber-50 text-amber-700">
              <Clock className="h-3.5 w-3.5" />
            </span>
          </div>
          <div className="text-2xl font-extrabold text-[#252525] font-sans tracking-tight">140ms</div>
          <div className="text-[10px] font-semibold text-amber-700 font-mono">99.9% uptime checkpoint graph</div>
        </div>

        {/* KPI 4 */}
        <div className="p-4 rounded-2xl bg-white border border-stone-200/90 shadow-2xs flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-stone-500 font-mono uppercase">WhatsApp Conversion</span>
            <span className="p-1.5 rounded-lg bg-rose-50 text-rose-700">
              <MessageSquare className="h-3.5 w-3.5" />
            </span>
          </div>
          <div className="text-2xl font-extrabold text-[#252525] font-sans tracking-tight">94.2%</div>
          <div className="text-[10px] font-semibold text-rose-700 font-mono">1-tap confirmation rate</div>
        </div>

      </div>

      {/* ── Routine Switcher ─────────────────────────────────────── */}
      <div className="p-4 rounded-2xl bg-white border border-stone-200/90 shadow-2xs flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-stone-700 flex items-center gap-1.5 font-mono">
            <Zap className="h-3.5 w-3.5 text-stone-700" />
            Interactive Routine Switcher
          </span>
          {(switching || loadingPredictions) && <Loader2 className="h-3.5 w-3.5 animate-spin text-stone-600" />}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          {scenarios.map((s) => {
            const Icon = s.icon;
            const isActive = activeScenario === s.id;
            return (
              <button
                key={s.id}
                disabled={switching}
                onClick={() => handleSwitch(s.id)}
                className={clsx(
                  "p-3 rounded-xl border text-left flex flex-col justify-between gap-2 transition-all duration-150 cursor-pointer select-none active:scale-[0.98]",
                  isActive
                    ? "bg-[#252525] text-white border-[#252525] shadow-xs"
                    : "bg-stone-50/70 text-stone-800 border-stone-200 hover:border-stone-300 hover:bg-white"
                )}
              >
                <div className="flex items-center justify-between w-full">
                  <div className={clsx(
                    "p-1.5 rounded-md shrink-0",
                    isActive ? "bg-stone-800 text-white" : "bg-white text-stone-600 border border-stone-200"
                  )}>
                    <Icon className="h-3.5 w-3.5" />
                  </div>
                  <span className={clsx(
                    "text-[9px] font-bold font-mono px-2 py-0.5 rounded-full uppercase border",
                    isActive
                      ? "bg-stone-800 text-white border-stone-700"
                      : "bg-white text-stone-600 border-stone-200"
                  )}>
                    {s.badge}
                  </span>
                </div>

                <div className="flex flex-col">
                  <span className="font-bold text-xs font-sans">
                    {s.title}
                  </span>
                  <span className={clsx("text-[10px] font-medium leading-tight mt-0.5", isActive ? "text-stone-300" : "text-stone-500")}>
                    {s.desc}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Main Chart View Switcher & Graph Display ────────────── */}
      <div className="p-5 rounded-2xl bg-white border border-stone-200/90 shadow-2xs flex flex-col gap-4">
        
        {/* Chart View Switcher Tabs */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-stone-200 pb-3">
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-[#252525] text-white">
              <BarChart3 className="h-4 w-4" />
            </span>
            <h3 className="text-base font-extrabold text-[#252525] font-sans">
              Unit Economics & Telemetry Curves
            </h3>
          </div>

          <div className="flex items-center gap-1.5 bg-stone-100 p-1 rounded-full text-[9.5px] font-mono font-bold border border-stone-200/80">
            <button
              onClick={() => setActiveChartView("gmv")}
              className={clsx(
                "px-3 py-1 rounded-full transition-all cursor-pointer active:scale-95",
                activeChartView === "gmv" ? "bg-[#252525] text-white shadow-2xs" : "text-stone-600 hover:text-stone-900"
              )}
            >
              GMV Recovery
            </button>
            <button
              onClick={() => setActiveChartView("retention")}
              className={clsx(
                "px-3 py-1 rounded-full transition-all cursor-pointer active:scale-95",
                activeChartView === "retention" ? "bg-[#252525] text-white shadow-2xs" : "text-stone-600 hover:text-stone-900"
              )}
            >
              Retention Floor
            </button>
            <button
              onClick={() => setActiveChartView("depletion")}
              className={clsx(
                "px-3 py-1 rounded-full transition-all cursor-pointer active:scale-95",
                activeChartView === "depletion" ? "bg-[#252525] text-white shadow-2xs" : "text-stone-600 hover:text-stone-900"
              )}
            >
              Depletion Curve
            </button>
          </div>
        </div>

        {/* Dynamic Chart Display based on Tab */}
        <div className="h-64 w-full pt-2 min-h-[256px]">
          {mounted ? (
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
              {activeChartView === "gmv" ? (
                <AreaChart data={GMV_RECOVERY_DATA} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gmvGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10B981" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#10B981" stopOpacity={0.0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="2 2" stroke="#E5E7EB" vertical={false} />
                  <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#6B7280" }} stroke="#E5E7EB" tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#6B7280" }} stroke="#E5E7EB" tickLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: "#252525", borderRadius: "10px", color: "#FFFFFF", fontSize: "11px", border: "none" }} />
                  <Area type="monotone" dataKey="recovered" stroke="#10B981" strokeWidth={3} fillOpacity={1} fill="url(#gmvGradient)" name="Recovered GMV (₹)" />
                </AreaChart>
              ) : activeChartView === "retention" ? (
                <LineChart data={RETENTION_DATA} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="2 2" stroke="#E5E7EB" vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#6B7280" }} stroke="#E5E7EB" tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#6B7280" }} stroke="#E5E7EB" domain={[0, 100]} tickLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: "#252525", borderRadius: "10px", color: "#FFFFFF", fontSize: "11px", border: "none" }} />
                  <Line type="monotone" dataKey="standard" stroke="#9CA3AF" strokeWidth={2} strokeDasharray="4 4" name="Standard Churn (%)" dot={false} />
                  <Line type="monotone" dataKey="prefill" stroke="#252525" strokeWidth={3} name="PreFill Retention (%)" dot={{ r: 4, fill: "#252525" }} />
                </LineChart>
              ) : (
                <BarChart data={depletionChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="2 2" stroke="#E5E7EB" vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#6B7280" }} stroke="#E5E7EB" tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#6B7280" }} stroke="#E5E7EB" domain={[0, 105]} tickLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: "#252525", borderRadius: "10px", color: "#FFFFFF", fontSize: "11px", border: "none" }} />
                  <ReferenceLine y={20} stroke="#EF4444" strokeDasharray="3 3" />
                  <Bar dataKey="stock" fill="#252525" radius={[6, 6, 0, 0]} name="Stock Remaining (%)" />
                </BarChart>
              )}
            </ResponsiveContainer>
          ) : (
            <div className="w-full h-full bg-stone-100/50 rounded-2xl animate-pulse" />
          )}
        </div>

      </div>

    </div>
  );
}

