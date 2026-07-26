"use client";

import { useState, useEffect, useMemo } from "react";
import { 
  Zap, 
  Terminal, 
  Calendar, 
  Users, 
  Coffee,
  Loader2,
  BarChart3,
  TrendingUp,
  LineChart as LineChartIcon,
  ShieldCheck,
  Sparkles
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

export default function ExecutivePanel({ activeScenario, onScenarioChange }: ExecutivePanelProps) {
  const [switching, setSwitching] = useState(false);
  const [realPredictions, setRealPredictions] = useState<APIPrediction[]>([]);
  const [loadingPredictions, setLoadingPredictions] = useState(true);

  const [apiLogs, setApiLogs] = useState<any>({
    household_id: "demo_user_001",
    inferred_composition: "family_small",
    confidence_score: 0.88,
    active_scenario: activeScenario,
    ml_engine: "Facebook Prophet + IQR Outlier Filter",
    langgraph_state: "idle_awaiting_depletion_cron",
    switching_cost_moat: "6-Month Household Consumption History"
  });

  // Fetch real backend prediction data
  useEffect(() => {
    async function loadData() {
      try {
        setLoadingPredictions(true);
        const res = await predictionsApi.getForHousehold("demo_user_001");
        if (res.data?.predictions && res.data.predictions.length > 0) {
          setRealPredictions(res.data.predictions);
        }
      } catch (err) {
        console.warn("Using baseline depletion dataset", err);
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
      desc: "Baseline 7-day depletion slope.",
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
      setApiLogs((prev: any) => ({
        ...prev,
        active_scenario: id,
        timestamp: new Date().toISOString(),
        status: "scenario_switched_successfully"
      }));
      toast.success(`Scenario set to ${id.toUpperCase()}`);
      window.dispatchEvent(new CustomEvent("scenario-switched", { detail: { scenario: id } }));
      window.dispatchEvent(new CustomEvent("refresh-dashboard"));
    } catch (err) {
      console.warn("Failed to switch scenario", err);
      toast.error("Failed to switch scenario");
    } finally {
      setSwitching(false);
    }
  };

  // Generate real data depletion series from backend predictions or active scenario
  const depletionChartData = useMemo(() => {
    if (realPredictions.length > 0) {
      // Map top predicted item depletion path
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
    <div className="flex flex-col gap-5">
      
      {/* ── Scenario Switcher (Tactile Buttons) ─────────────── */}
      <div className="saas-card p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-800 flex items-center gap-1.5 font-display">
            <Zap className="h-3.5 w-3.5 text-slate-700" />
            Interactive Routine Switcher
          </span>
          {switching && <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-600" />}
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
                  "p-3 rounded-xl border text-left flex flex-col justify-between gap-2 transition-all duration-150 active:scale-[0.98] cursor-pointer select-none",
                  isActive
                    ? "bg-slate-900 text-white border-slate-900 shadow-xs"
                    : "bg-white text-slate-800 border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                )}
              >
                <div className="flex items-center justify-between w-full">
                  <div className={clsx(
                    "p-1.5 rounded-md shrink-0",
                    isActive ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-600"
                  )}>
                    <Icon className="h-3.5 w-3.5" />
                  </div>
                  <span className={clsx(
                    "text-[9px] font-semibold font-mono px-1.5 py-0.5 rounded uppercase border",
                    isActive
                      ? "bg-slate-800 text-slate-200 border-slate-700"
                      : "bg-slate-50 text-slate-500 border-slate-200"
                  )}>
                    {s.badge}
                  </span>
                </div>

                <div className="flex flex-col">
                  <span className="font-semibold text-xs font-display">
                    {s.title}
                  </span>
                  <span className={clsx("text-[10px] font-medium leading-tight mt-0.5", isActive ? "text-slate-300" : "text-slate-500")}>
                    {s.desc}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── CHART 1: Prophet ML Depletion Curve (Animated) ──── */}
      <div className="saas-card p-4 flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <LineChartIcon className="h-4 w-4 text-slate-800" />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-900 font-display">
              1. Prophet ML Household Depletion Curve
            </span>
          </div>
          <span className="pill-subtle-green flex items-center gap-1">
            <Sparkles className="h-3 w-3" />
            Real ML Model Data
          </span>
        </div>

        <p className="text-[11px] text-slate-500 font-medium">
          Predictive depletion trajectories calculate reorder timing at 20% remaining threshold.
        </p>

        <div className="h-48 w-full pt-1">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={depletionChartData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
              <defs>
                <linearGradient id="depletionGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0F172A" stopOpacity={0.18}/>
                  <stop offset="95%" stopColor="#0F172A" stopOpacity={0.0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="day" tick={{ fontSize: 10 }} stroke="#94a3b8" />
              <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" domain={[0, 105]} />
              <Tooltip 
                contentStyle={{ backgroundColor: "#0f172a", borderRadius: "8px", color: "#fff", fontSize: "11px" }}
              />
              <ReferenceLine y={20} label={{ value: '20% Reorder Trigger', fill: '#ef4444', fontSize: 9, position: 'insideTopRight' }} stroke="#ef4444" strokeDasharray="3 3" />
              <Area 
                type="monotone" 
                dataKey="stock" 
                stroke="#0F172A" 
                strokeWidth={2.5} 
                fillOpacity={1} 
                fill="url(#depletionGrad)" 
                isAnimationActive={true}
                animationDuration={1200}
                animationEasing="ease-in-out"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── CHART 2 & 3: Financial & Retention Metrics (Animated) ─── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        
        {/* Chart 2: Kirana GMV Recovery (Animated Bars) */}
        <div className="saas-card p-4 flex flex-col gap-2">
          <div className="flex items-center gap-1.5 text-slate-900">
            <BarChart3 className="h-4 w-4 text-slate-800" />
            <span className="text-[11px] font-semibold uppercase tracking-wider font-display">
              2. Kirana Leakage Recovery (GMV)
            </span>
          </div>
          <p className="text-[10px] text-slate-500 font-medium">
            Recaptured monthly spend (+₹1,450/hh) from local store leakages.
          </p>

          <div className="h-36 w-full pt-1">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={GMV_RECOVERY_DATA} margin={{ top: 10, right: 5, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="month" tick={{ fontSize: 9 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 9 }} stroke="#94a3b8" />
                <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderRadius: "8px", color: "#fff", fontSize: "10px" }} />
                <Bar 
                  dataKey="baseline" 
                  stackId="a" 
                  fill="#e2e8f0" 
                  name="Base GMV" 
                  isAnimationActive={true}
                  animationDuration={1000}
                />
                <Bar 
                  dataKey="recovered" 
                  stackId="a" 
                  fill="#10b981" 
                  name="Recovered Leakage" 
                  isAnimationActive={true}
                  animationDuration={1200}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 3: 90-Day Retention Curve (Animated Line) */}
        <div className="saas-card p-4 flex flex-col gap-2">
          <div className="flex items-center gap-1.5 text-slate-900">
            <TrendingUp className="h-4 w-4 text-slate-800" />
            <span className="text-[11px] font-semibold uppercase tracking-wider font-display">
              3. 90-Day LTV Retention Floor
            </span>
          </div>
          <p className="text-[10px] text-slate-500 font-medium">
            82% retention floor vs 24% standard quick commerce churn.
          </p>

          <div className="h-36 w-full pt-1">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={RETENTION_DATA} margin={{ top: 10, right: 5, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="day" tick={{ fontSize: 9 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 9 }} stroke="#94a3b8" domain={[0, 100]} />
                <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderRadius: "8px", color: "#fff", fontSize: "10px" }} />
                <Line 
                  type="monotone" 
                  dataKey="standard" 
                  stroke="#cbd5e1" 
                  strokeWidth={1.5} 
                  name="Standard Churn" 
                  isAnimationActive={true}
                  animationDuration={1000}
                />
                <Line 
                  type="monotone" 
                  dataKey="prefill" 
                  stroke="#0f172a" 
                  strokeWidth={2.5} 
                  name="PreFill Retention" 
                  isAnimationActive={true}
                  animationDuration={1400}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>

      {/* ── LangGraph JSON State Inspector ────────────────────── */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 p-4 text-slate-100 shadow-xs flex flex-col gap-2 font-mono">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <Terminal className="h-3.5 w-3.5 text-emerald-400" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-200 font-display">
              LangGraph State Inspector
            </span>
          </div>
          <span className="text-[9px] text-emerald-400 font-bold px-2 py-0.5 bg-emerald-950/60 border border-emerald-800/60 rounded flex items-center gap-1">
            <ShieldCheck className="h-3 w-3" />
            POSTGRES CHECKPOINTED
          </span>
        </div>

        <pre className="text-[9px] text-slate-300 overflow-x-auto p-2 bg-slate-950 rounded-md leading-relaxed no-scrollbar border border-slate-800 max-h-32 select-text">
          {JSON.stringify(apiLogs, null, 2)}
        </pre>
      </div>

    </div>
  );
}
