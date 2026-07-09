"use client";

import { useEffect, useState, useRef, Suspense, useMemo } from "react";
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { JarWave } from '../components/JarWave';

const ConfettiEffect = dynamic(() => import('../components/ConfettiEffect'), { ssr: false });
import useSWR from "swr";
import { predictionsApi, householdApi, APIPrediction } from "../lib/api";
import { getCategoryTheme } from "../lib/theme";
import { ShieldCheck, Sparkles, ShoppingCart, ArrowRight, Eye, ChefHat, Coffee, Users, Database, AlertCircle, Receipt, Layers, Cpu, Calendar, Milk, Apple, Egg, Croissant, Droplets, Package } from "lucide-react";

interface DepletingItem {
  id: string;
  name: string;
  days: number;
  rawDays: number;
  fillPct: number;
  conf: number;
  avg: string;
  cycle: string;
}

const STATS = [
  { value: "34",     label: "Groceries Monitored",   sub: "Tracked in real-time", icon: Layers },
  { value: "98%",    label: "Accuracy",              sub: "Based on habits", icon: Cpu },
  { value: "12",     label: "Stockouts Avoided",      sub: "Saved by assistant", icon: ShieldCheck },
];

const FALLBACK_DEPLETING: DepletingItem[] = [
  { id: "fallback-milk", name: "Amul Taza Milk 1L",         days: 1, rawDays: 1, fillPct: 30, conf: 76, avg: "0.48L/day",  cycle: "1.8d" },
  { id: "fallback-tomatoes", name: "Tomatoes (500g)",       days: 1, rawDays: 1, fillPct: 14, conf: 78, avg: "140g/day",   cycle: "3.1d" },
  { id: "fallback-eggs", name: "Nandini Eggs (Pack of 12)", days: 2, rawDays: 2, fillPct: 43, conf: 88, avg: "2.4/day",    cycle: "4.6d" },
  { id: "fallback-bread", name: "Britannia Whole Wheat Bread", days: 3, rawDays: 3, fillPct: 77, conf: 82, avg: "0.24/day",  cycle: "3.9d" },
  { id: "fallback-onions", name: "Onions (1kg)",            days: 5, rawDays: 5, fillPct: 53, conf: 72, avg: "130g/day",   cycle: "7.7d" },
];


function urgencyLabel(days: number, fillPercent: number) {
  if (fillPercent <= 20) return "Out tomorrow!";
  if (fillPercent <= 45) return `Out in ${days} days`;
  return `${days} days left (${fillPercent}%)`;
}

function certaintyLabel(conf: number) {
  if (conf >= 85) return "Very sure";
  if (conf >= 70) return "Pretty sure";
  return "Guessing";
}

function formatAvg(avg: string) {
  return `Uses ${avg.replace("/day", " per day")}`;
}

function formatCycle(cycle: string) {
  const d = parseFloat(cycle);
  if (isNaN(d)) return `Bought every ${cycle}`;
  if (d <= 2.5) return "Bought every 2 days";
  if (d >= 6 && d <= 7.5) return "Bought weekly";
  if (d >= 13 && d <= 16) return "Bought every 2 weeks";
  if (d >= 25 && d <= 30) return "Bought monthly";
  return `Bought every ${Math.round(d)} days`;
}

function getLevelColors(fillPct: number) {
  if (fillPct <= 20) {
    // Rose / Rose (Almost Empty)
    return {
      bg: "rgba(244, 63, 94, 0.03)",
      border: "rgba(244, 63, 94, 0.15)",
      text: "#be123c",
      frontStart: "rgba(254, 226, 226, 0.95)",
      frontMid: "rgba(244, 114, 182, 0.75)",
      frontEnd: "rgba(225, 29, 72, 0.9)",
      backStart: "rgba(254, 226, 226, 0.5)",
      backEnd: "rgba(190, 18, 60, 0.7)"
    };
  }
  if (fillPct <= 45) {
    // Terracotta / Orange (Running Low)
    return {
      bg: "rgba(217, 119, 6, 0.03)",
      border: "rgba(217, 119, 6, 0.15)",
      text: "#b45309",
      frontStart: "rgba(254, 243, 199, 0.95)",
      frontMid: "rgba(245, 158, 11, 0.75)",
      frontEnd: "rgba(217, 119, 6, 0.9)",
      backStart: "rgba(254, 243, 199, 0.5)",
      backEnd: "rgba(180, 83, 9, 0.7)"
    };
  }
  // Sage / Green (Well Stocked)
  return {
    bg: "rgba(16, 185, 129, 0.03)",
    border: "rgba(16, 185, 129, 0.15)",
    text: "#047857",
    frontStart: "rgba(209, 250, 229, 0.95)",
    frontMid: "rgba(52, 211, 153, 0.75)",
    frontEnd: "rgba(16, 185, 129, 0.9)",
    backStart: "rgba(209, 250, 229, 0.5)",
    backEnd: "rgba(4, 120, 87, 0.7)"
  };
}







const fetcher = (userId: string) => predictionsApi.getForHousehold(userId).then(res => res.data);

function DashboardContent() {
  // Interactive Local UI states
  const [addedItems, setAddedItems] = useState<Set<string>>(new Set());
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const [showConfetti, setShowConfetti] = useState(false);
  const [refilledItems, setRefilledItems] = useState<Set<string>>(new Set());
  
  const [activeScenario, setActiveScenario] = useState("standard");
  const [switchingScenario, setSwitchingScenario] = useState(false);

  // Hoisted Toast handler
  function triggerToast(msg: string) {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 3000);
  }

  const { data: predictionsData, mutate: mutatePredictions, isLoading: predictionsLoading } = useSWR(
    "demo_user_001",
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000,
    }
  );

  // Listen to refresh-dashboard event to trigger revalidation of predictions
  useEffect(() => {
    const handleRefresh = () => {
      mutatePredictions();
    };
    window.addEventListener("refresh-dashboard", handleRefresh);
    return () => window.removeEventListener("refresh-dashboard", handleRefresh);
  }, [mutatePredictions]);

  const loading = predictionsLoading || switchingScenario;

  const depleting = useMemo(() => {
    return predictionsData?.predictions && predictionsData.predictions.length > 0
      ? predictionsData.predictions.map((p: APIPrediction) => ({
          id: p.item_id,
          name: p.item_name,
          days: p.days_remaining !== null ? Math.round(p.days_remaining) : 10,
          rawDays: p.days_remaining !== null ? p.days_remaining : 10,
          fillPct: p.stock_fill_percent !== undefined ? Math.round(p.stock_fill_percent) : 100,
          conf: Math.round((p.confidence_score || 0.5) * 100),
          avg: `${p.avg_daily_consumption.toFixed(2)}/day`,
          cycle: `${p.consumption_cycle_days || 7}d`,
        }))
      : FALLBACK_DEPLETING;
  }, [predictionsData]);


  const handleScenarioChange = async (scenario: string) => {
    if (switchingScenario) return;
    setSwitchingScenario(true);
    
    // Optimistic Update
    const previousScenario = activeScenario;
    setActiveScenario(scenario);
    
    try {
      await householdApi.switchScenario("demo_user_001", scenario);
      triggerToast(`Switched to ${scenario === "standard" ? "Standard Staples" : scenario === "party" ? "Party Spike" : "Vacation Mode"}!`);
      window.dispatchEvent(new CustomEvent("scenario-switched"));
      await mutatePredictions();
    } catch (err) {
      console.warn("Failed to switch scenario", err);
      // Revert on failure
      setActiveScenario(previousScenario);
      triggerToast("⚠️ Failed to switch demo scenario.");
    } finally {
      setSwitchingScenario(false);
    }
  };

  // Listen to order-placed event to trigger confetti and shelf replenish animation
  useEffect(() => {
    const handleOrderPlaced = () => {
      setShowConfetti(true);
      setTimeout(() => setShowConfetti(false), 5000); // confetti runs for 5s

      // Visually replenish all kitchen shelf jars back to full (95%)
      const allNames = depleting.map(i => i.name);
      setRefilledItems(new Set(allNames));
      
      // Keep shelf visuals refilled for 12 seconds
      setTimeout(() => {
        setRefilledItems(new Set());
      }, 12000);

      triggerToast("🎉 PreFill Order Confirmed!");
    };

    window.addEventListener("order-placed", handleOrderPlaced);
    return () => window.removeEventListener("order-placed", handleOrderPlaced);
  }, [depleting]);


  const handleAddToCart = (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setAddedItems((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
        triggerToast(`Removed ${name.split(" — ")[0]} from Cart`);
      } else {
        next.add(name);
        triggerToast(`Added ${name.split(" — ")[0]} to your PreFill Cart!`);
      }
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-10 relative">
      <ConfettiEffect active={showConfetti} />

      {/* ── App Header ──────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-border/40 pb-8">
        <div className="flex flex-col gap-2.5">
          <div className="text-accent text-[11px] font-bold tracking-widest uppercase font-display flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Pantry Checker</span>
          </div>
          <h1 className="text-4xl font-bold tracking-tight leading-none font-display text-foreground">
            My Kitchen <span className="title-accent">Dashboard</span>
          </h1>
          <p className="text-sm text-muted max-w-md leading-relaxed font-medium mt-1">
            Real-time grocery monitoring and automated depletion forecasts.
          </p>
        </div>

        {/* Quick Links inside App */}
        <div className="flex items-center gap-3.5 shrink-0">
          <Link
            href="/predictions"
            className="h-10 px-4.5 bg-accent/8 hover:bg-accent/12 text-accent border border-accent/15 font-extrabold text-[11px] tracking-wider uppercase rounded-md transition-all duration-200 flex items-center gap-1.5 font-display cursor-pointer"
          >
            <Eye className="h-4 w-4" />
            Predictions
          </Link>
          <Link
            href="/recipes"
            className="h-10 px-5 bg-white border border-border text-foreground hover:bg-neutral-50 hover:border-muted font-extrabold text-[11px] tracking-wider uppercase rounded-md transition-all duration-200 flex items-center gap-1.5 font-display cursor-pointer"
          >
            <ChefHat className="h-4 w-4 text-muted" />
            Recipes
          </Link>
        </div>
      </div>

      {/* ── App Dashboard Grid ─────────────────────────────── */}
      <div className="grid grid-cols-12 gap-8 items-start">
        
        {/* LEFT COLUMN: Main Dashboard Content (col-span-8) */}
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-8">
          
          {/* Virtual Kitchen Shelf (Jars) */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-muted uppercase tracking-wider font-display">Virtual Kitchen Shelf</span>
              <span className="text-[10px] text-muted font-medium hidden sm:inline">Jars show actual fill levels</span>
            </div>
            
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3.5">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="relative w-full h-44 glass-card animate-pulse p-4 flex flex-col justify-between">
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-12 h-2 bg-neutral-200/50 rounded-b-md" />
                    <div className="h-3 w-12 bg-neutral-200/50 rounded" />
                    <div className="h-8 w-8 bg-neutral-200/50 rounded-full" />
                    <div className="h-3 w-16 bg-neutral-200/50 rounded" />
                  </div>
                ))
              ) : (
                [...depleting]
                  .map((item) => {
                    const isRefilled = refilledItems.has(item.name);
                    const fillPercent = isRefilled ? 95 : Math.max(0, item.fillPct);
                    return { ...item, fillPercent, isRefilled };
                  })
                  .sort((a, b) => a.fillPercent - b.fillPercent)
                  .slice(0, 5)
                  .map((item, idx) => {
                     const isAdded = addedItems.has(item.name);
                     const fp = item.fillPercent;
                     const waveDelay = `${idx * -1.2}s`;
 
                     // Retrieve badge theme (Airtable-style)
                     const theme = getCategoryTheme(item.name);
 
                     // Retrieve wave & card colors (Variant A level-based)
                     const waveColors = getLevelColors(fp);
 
                     return (
                      <div
                        key={item.id || item.name}
                        className="relative w-full h-44 glass-card overflow-hidden group hover:shadow-sm transition-all duration-300 flex flex-col justify-between p-5 cursor-pointer hover:border-accent"
                        onClick={(e) => handleAddToCart(item.name, e)}
                      >
                        {/* Jar Lid */}
                        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-12 h-2 bg-gradient-to-b from-neutral-300 to-neutral-400 rounded-b z-20 shadow-sm" />

                        {/* Liquid body */}
                        <div
                          className="absolute bottom-0 left-0 w-full z-10 transition-all duration-1000 ease-out liquid-fill-animate"
                          style={{ height: `${fp}%` }}
                        >
                          <JarWave idx={idx} waveDelay={waveDelay} waveColors={waveColors} />
                        </div>

                        {/* Content */}
                        <div className="relative z-20 flex flex-col h-full justify-between pointer-events-none">
                          <div className="flex flex-col gap-1.5 items-start">
                            <span
                              className="text-[9px] uppercase font-bold px-1.5 py-0.5 rounded font-display tracking-wider border font-medium"
                              style={{
                                color: theme.text,
                                backgroundColor: theme.bg,
                                borderColor: theme.border
                              }}
                            >
                              {theme.label}
                            </span>
                            <span className="font-extrabold text-[11px] text-foreground tracking-tight line-clamp-2 leading-snug font-display">
                              {item.name.split(" — ")[0]}
                            </span>
                          </div>
                          <div className="flex flex-col items-start my-auto">
                            <span className="text-xl font-black text-foreground font-display leading-none">
                              {item.isRefilled ? "✓" : item.days}
                            </span>
                            <span className="text-[9px] font-bold text-foreground/80 uppercase tracking-wider font-display mt-0.5">
                              {item.isRefilled ? "Refilled" : item.days === 1 ? "day left" : "days left"}
                            </span>
                          </div>
                          <div className="text-[8px] font-bold text-foreground/85 uppercase tracking-wider font-display">
                            {item.isRefilled ? "95% full" : `${fp}% full`}
                          </div>
                        </div>

                        {/* Add-to-cart button */}
                        <button
                          onClick={(e) => { e.stopPropagation(); handleAddToCart(item.name, e); }}
                          className={`absolute bottom-2.5 right-2.5 w-8 h-8 rounded-md flex items-center justify-center transition-all duration-200 z-30 cursor-pointer shadow-sm border ${
                            isAdded
                              ? "bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-500"
                              : "bg-white/95 text-muted hover:text-accent hover:border-accent border-border"
                          }`}
                          aria-label={`Add ${item.name} to cart`}
                        >
                          <ShoppingCart className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    );
                  })
              )}
            </div>
          </div>

          {/* Timeline Checker List */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-muted uppercase tracking-wider font-display">Timeline Checker</span>
              <Link href="/predictions" className="text-[10px] font-extrabold text-accent hover:underline transition-all flex items-center gap-0.5">
                View Full List <ArrowRight className="h-2.5 w-2.5" />
              </Link>
            </div>

            <div className="glass-card overflow-hidden">
              <div className="divide-y divide-border/60">
                {loading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="px-5 py-3.5 flex items-center justify-between gap-4 animate-pulse">
                      <div className="flex items-center gap-3">
                        <div className="h-5.5 w-16 bg-neutral-200/50 rounded-md" />
                        <div className="h-4 w-32 bg-neutral-200/50 rounded" />
                      </div>
                      <div className="h-8 w-24 bg-neutral-200/50 rounded-md" />
                    </div>
                  ))
                ) : (
                  [...depleting]
                    .map((item) => {
                      const isRefilled = refilledItems.has(item.name);
                      const fillPct = isRefilled ? 95 : Math.max(0, item.fillPct);
                      return { ...item, fillPct, isRefilled };
                    })
                    .sort((a, b) => a.fillPct - b.fillPct)
                    .slice(0, 5)
                    .map((item) => {
                      const isAdded = addedItems.has(item.name);
                      const level = item.isRefilled ? "ok" : item.days <= 2 ? "danger" : item.days <= 5 ? "warning" : "ok";
                      const label = item.isRefilled ? "Stocked" : urgencyLabel(item.days, item.fillPct);

                      return (
                        <div
                          key={item.id || item.name}
                          className="px-5 py-3.5 flex items-center justify-between gap-4 hover:bg-neutral-50/50 transition-colors"
                        >
                          <div className="flex items-center gap-4 min-w-0">
                            <span className={`pill font-semibold font-display shrink-0 ${
                              level === "danger" ? "pill-danger" : level === "warning" ? "pill-warning" : "pill-ok"
                            }`}>
                              {label}
                            </span>
                            <div className="flex flex-col min-w-0">
                              <span className="font-extrabold text-xs tracking-wide text-foreground font-display truncate">
                                {item.name}
                              </span>
                              <span className="text-[9px] text-muted font-medium mt-0.5 flex items-center gap-1.5">
                                <span>{formatAvg(item.avg)}</span>
                                <span className="text-border/60">•</span>
                                <span>{formatCycle(item.cycle)}</span>
                                <span className="text-border/60">•</span>
                                <span className="font-semibold text-accent/80">{certaintyLabel(item.conf)}</span>
                              </span>
                            </div>
                          </div>

                          <button
                            disabled={item.isRefilled}
                            onClick={(e) => handleAddToCart(item.name, e)}
                            className={`h-8 px-3.5 rounded-md text-[10px] font-extrabold tracking-wider transition-all flex items-center gap-1 shrink-0 ${
                              item.isRefilled
                                ? "bg-emerald-100 text-emerald-600 border border-emerald-200/50 cursor-not-allowed"
                                : isAdded
                                ? "bg-gradient-to-b from-[#16A34A] to-[#15803D] border border-[#16A34A] text-white shadow-[0_1px_2px_rgba(0,0,0,0.15),inset_0_1px_0_rgba(255,255,255,0.15)] hover:from-[#15803D] hover:to-[#166534] cursor-pointer"
                                : "btn-premium-dark cursor-pointer"
                            }`}
                          >
                            {item.isRefilled ? (
                              <>
                                <ShieldCheck className="h-3.5 w-3.5" />
                                Stocked
                              </>
                            ) : isAdded ? (
                              <>
                                <ShoppingCart className="h-3.5 w-3.5" />
                                Added
                              </>
                            ) : (
                              <>
                                <ShoppingCart className="h-3.5 w-3.5" />
                                Add
                              </>
                            )}
                          </button>
                        </div>
                      );
                    })
                )}
              </div>
            </div>
          </div>

        </div>

        {/* RIGHT COLUMN: App Sidebar Settings & Stats (col-span-4) */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
          
          {/* Quick Stats Panel */}
          <div className="glass-card p-6 flex flex-col gap-4">
            <span className="font-extrabold text-xs text-foreground font-display uppercase tracking-wider">Quick Metrics</span>
            <div className="flex flex-col gap-3">
              {STATS.map((s) => {
                const Icon = s.icon;
                const c = 
                  s.label.includes("Monitored") ? { text: "#0066CC", bg: "#E6F5FF", border: "rgba(0,102,204,0.15)" } :
                  s.label.includes("Avoided") ? { text: "#D96B27", bg: "#FFF3E6", border: "rgba(217,107,39,0.15)" } :
                  { text: "#4B5563", bg: "#F3F4F6", border: "rgba(75, 85, 99, 0.15)" }; // Slate Gray for Accuracy to minimize violet
                return (
                  <div key={s.label} className="flex items-center gap-3.5 border-b border-border/40 pb-3 last:border-0 last:pb-0">
                    <div 
                      className="p-2 rounded-lg border shrink-0"
                      style={{ backgroundColor: c.bg, borderColor: c.border, color: c.text }}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex flex-col min-w-0">
                      <span className="text-[9px] text-muted font-bold tracking-wider uppercase font-display leading-none">{s.label}</span>
                      <div className="flex items-baseline gap-1.5 mt-0.5">
                        <span className="text-xl font-black font-display leading-none text-foreground">{s.value}</span>
                        <span className="text-[9px] text-muted/70 font-semibold truncate">{s.sub}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Reviewer Settings / Scenario Control */}
          <div className="glass-card p-6 flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <span className="font-extrabold text-xs text-foreground font-display uppercase tracking-wider">Demo Scenario</span>
              <p className="text-[10px] leading-relaxed text-muted font-medium mt-0.5">
                Toggle scenario routines to simulate pantry depletions.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              {[
                { id: "standard", label: "Regular Week", desc: "Standard household routines.", icon: <Calendar className="h-4 w-4" />, colors: { text: "#0F9940", bg: "#E8F8EE", border: "rgba(15,153,64,0.15)" } },
                { id: "party",    label: "Weekend Party", desc: "Milk & butter usage spikes.", icon: <Users className="h-4 w-4" />, colors: { text: "#615FFF", bg: "#EBE8FF", border: "rgba(97,95,255,0.15)" } },
                { id: "vacation", label: "On Vacation", desc: "No depletion occurs.", icon: <Coffee className="h-4 w-4" />, colors: { text: "#D96B27", bg: "#FFF3E6", border: "rgba(217,107,39,0.15)" } },
              ].map((s) => {
                const isActive = activeScenario === s.id;
                const c = s.colors;
                return (
                  <button
                    key={s.id}
                    disabled={switchingScenario}
                    onClick={() => handleScenarioChange(s.id)}
                    className="flex items-start gap-3 p-3 rounded-lg border text-left cursor-pointer transition-all duration-200 w-full relative disabled:opacity-50"
                    style={
                      isActive
                        ? { backgroundColor: c.bg, borderColor: c.border, color: c.text }
                        : { backgroundColor: "rgba(255,255,255,0.8)", borderColor: "var(--border)" }
                    }
                  >
                    <div 
                      className="p-1.5 rounded-md shrink-0 border"
                      style={{
                        backgroundColor: c.bg,
                        color: c.text,
                        borderColor: c.border
                      }}
                    >
                      {s.icon}
                    </div>
                    <div className="flex flex-col">
                      <span 
                        className="font-extrabold text-xs font-display transition-colors"
                        style={{ color: isActive ? c.text : "var(--foreground)" }}
                      >
                        {s.label}
                      </span>
                      <span className="text-[9px] text-muted/80 font-medium leading-normal mt-0.5">{s.desc}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

        </div>

      </div>

      {/* ── Toast Notification ─────────────────────────────── */}
      {toastMessage && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 bg-neutral-900/95 text-white px-5 py-3 rounded-md shadow-[0_12px_40px_rgba(0,0,0,0.25)] flex items-center gap-2 border border-neutral-800 animate-in fade-in slide-in-from-bottom-4 duration-300">
          <span className="text-xs font-bold tracking-wide font-display">{toastMessage}</span>
        </div>
      )}
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={
      <div className="mx-auto max-w-7xl px-4 md:px-8 py-10 text-center text-xs font-bold uppercase tracking-wider text-muted font-display">
        Loading Pantry Dashboard...
      </div>
    }>
      <DashboardContent />
    </Suspense>
  );
}
