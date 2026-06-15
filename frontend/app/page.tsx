"use client";

import { useEffect, useState } from "react";
import Link from 'next/link';
import { predictionsApi, APIPrediction } from "../lib/api";
import { Package, ShieldCheck, Zap, Sparkles, ShoppingCart, Calendar, Bell, BellOff, ArrowRight } from "lucide-react";

interface DepletingItem {
  name: string;
  days: number;
  conf: number;
  avg: string;
  cycle: string;
  urgent: boolean;
}

const STATS = [
  { value: "34",     label: "Pantry Staples Tracked", sub: "automatic tracking active" },
  { value: "98%",    label: "Prediction Accuracy",    sub: "based on last 30 refills" },
  { value: "12",     label: "Stockouts Prevented",    sub: "automatic refills saved" },
  { value: "High",   label: "Smart Coverage",        sub: "across all kitchen essentials" },
];

const FALLBACK_DEPLETING: DepletingItem[] = [
  { name: "Amul Taza Milk 1L",        days: 1,  conf: 76, avg: "1.1L/day",  cycle: "2.1d",  urgent: true  },
  { name: "Fortune Sunflower Oil 1L",  days: 2,  conf: 87, avg: "68ml/day", cycle: "14.7d", urgent: true  },
  { name: "Nandini Eggs — Pack of 12", days: 4,  conf: 88, avg: "2.3/day",  cycle: "6.2d",  urgent: false },
  { name: "Aashirvaad Atta 5kg",       days: 12, conf: 68, avg: "280g/day", cycle: "17d",   urgent: false },
  { name: "Tata Salt 1kg",             days: 21, conf: 61, avg: "8g/day",   cycle: "28d",   urgent: false },
];

function urgencyColor(days: number) {
  if (days <= 1) return { bar: "#ff5a00", text: "text-red-500",   pill: "pill-danger"  };
  if (days <= 3) return { bar: "#d97706", text: "text-amber-500", pill: "pill-warning" };
  return             { bar: "#7c7267", text: "text-muted",      pill: "pill-muted"   };
}

function urgencyLabel(days: number) {
  if (days <= 1) return "Out tomorrow!";
  if (days <= 3) return `Out in ${days} days`;
  return `${days} days remaining`;
}

function certaintyLabel(conf: number) {
  if (conf >= 85) return "Very High Certainty";
  if (conf >= 70) return "High Certainty";
  return "Calculated Estimate";
}

function formatAvg(avg: string) {
  return `Uses ${avg.replace("/day", " daily")}`;
}

function formatCycle(cycle: string) {
  const d = parseFloat(cycle);
  if (isNaN(d)) return `Restocked every ${cycle}`;
  if (d <= 2.5) return "Restocked every 2 days";
  if (d >= 6 && d <= 7.5) return "Restocked weekly";
  if (d >= 13 && d <= 16) return "Restocked every 2 weeks";
  if (d >= 25 && d <= 30) return "Restocked monthly";
  return `Restocked every ${Math.round(d)} days`;
}

function barFill(days: number) {
  return Math.min(100, Math.max(4, Math.round((days / 30) * 100)));
}

function jarFluidStyle(name: string, days: number) {
  const lower = name.toLowerCase();
  let startColor = "rgba(255, 90, 0, 0.4)"; // default orange
  let endColor = "rgba(255, 90, 0, 0.1)";
  let border = "#ff5a00";
  
  if (days <= 1) {
    startColor = "rgba(225, 29, 72, 0.45)"; // urgent red (danger)
    endColor = "rgba(225, 29, 72, 0.1)";
    border = "var(--danger)";
  } else if (days <= 3) {
    startColor = "rgba(217, 119, 6, 0.45)"; // low warning amber (warning)
    endColor = "rgba(217, 119, 6, 0.1)";
    border = "var(--warning)";
  } else {
    if (lower.includes("milk")) {
      startColor = "rgba(255, 255, 255, 0.4)";
      endColor = "rgba(255, 255, 255, 0.1)";
      border = "rgba(255, 90, 0, 0.3)";
    } else if (lower.includes("oil")) {
      startColor = "rgba(245, 158, 11, 0.45)";
      endColor = "rgba(245, 158, 11, 0.1)";
      border = "#f59e0b";
    } else if (lower.includes("egg")) {
      startColor = "rgba(251, 191, 36, 0.45)";
      endColor = "rgba(251, 191, 36, 0.1)";
      border = "#fbbf24";
    } else {
      startColor = "rgba(16, 185, 129, 0.4)"; // ok green
      endColor = "rgba(16, 185, 129, 0.08)";
      border = "var(--ok)";
    }
  }
  return { background: `linear-gradient(180deg, ${startColor} 0%, ${endColor} 100%)`, borderTop: `1px solid ${border}` };
}

export default function Home() {
  const [depleting, setDepleting] = useState<DepletingItem[]>(FALLBACK_DEPLETING);
  const [loading, setLoading] = useState(true);
  
  // Interactive Local UI states
  const [addedItems, setAddedItems] = useState<Set<string>>(new Set());
  const [pinnedItems, setPinnedItems] = useState<Set<string>>(new Set());
  const [snoozedItems, setSnoozedItems] = useState<Set<string>>(new Set());
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    async function loadDashboardData() {
      try {
        const res = await predictionsApi.getForHousehold("demo_user_001");
        if (res.data && res.data.predictions && res.data.predictions.length > 0) {
          const apiItems = res.data.predictions.map((p: APIPrediction) => ({
            name: p.item_name,
            days: p.days_remaining !== null ? Math.round(p.days_remaining) : 10,
            conf: Math.round((p.confidence_score || 0.5) * 100),
            avg: `${p.avg_daily_consumption.toFixed(2)}/day`,
            cycle: `${p.consumption_cycle_days || 7}d`,
            urgent: p.days_remaining !== null && p.days_remaining <= 3
          }));
          setDepleting(apiItems);
        }
      } catch (err) {
        console.warn("Failed to load dashboard live predictions from API, using static fallbacks.", err);
      } finally {
        setLoading(false);
      }
    }
    loadDashboardData();
  }, []);

  const triggerToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 3000);
  };

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
        triggerToast(`Added ${name.split(" — ")[0]} to your Instamart Cart!`);
      }
      return next;
    });
  };

  const handlePinToSunday = (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setPinnedItems((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
        triggerToast(`Removed ${name.split(" — ")[0]} from Sunday Meal Plan`);
      } else {
        next.add(name);
        triggerToast(`Pinned ${name.split(" — ")[0]} to Sunday Meal Plan checklist`);
      }
      return next;
    });
  };

  const handleSnoozeAlert = (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setSnoozedItems((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
        triggerToast(`Restored alerts for ${name.split(" — ")[0]}`);
      } else {
        next.add(name);
        triggerToast(`Paused refilling reminders for ${name.split(" — ")[0]} (snoozed)`);
      }
      return next;
    });
  };

  const STATS_ICONS = [
    <Package className="h-5 w-5 text-accent/80" />,
    <ShieldCheck className="h-5 w-5 text-accent/80" />,
    <Zap className="h-5 w-5 text-accent/80" />,
    <Sparkles className="h-5 w-5 text-accent/80" />
  ];

  return (
    <div className="flex flex-col gap-10 relative">
      
      {/* Ambient decorative blobs for premium editorial depth */}
      <div className="absolute top-[-50px] right-[-100px] w-[250px] h-[250px] bg-accent/8 blur-[100px] pointer-events-none -z-10" />

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-2.5">
        <div className="text-accent text-[11px] font-bold tracking-widest uppercase font-display">
          Instamart Assistant {loading && "(LOADING...)"}
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight leading-tight font-display text-foreground">
          My Kitchen <span className="text-accent">Pantry Checker</span>
        </h1>
        <p className="text-sm text-muted max-w-lg leading-relaxed font-medium">
          Predicts when your staples are running low. Tap to instantly add to your Instamart checkout cart, pin to meal planner, or adjust settings.
        </p>
      </div>

      {/* ── 4 Stat Blocks ───────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STATS.map((s, idx) => (
          <div key={s.label} className="glass-card p-6 rounded-2xl flex flex-col gap-3.5 hover:-translate-y-1 hover:shadow-[0_8px_30px_rgba(255,90,0,0.06)] transition-all duration-300">
            <div className="flex items-center justify-between">
              <div className="stat-value text-accent font-display">{s.value}</div>
              {STATS_ICONS[idx]}
            </div>
            <div className="flex flex-col gap-0.5">
              <div className="text-xs font-bold text-foreground tracking-wide font-display">{s.label}</div>
              <div className="text-[11px] text-muted font-medium leading-normal">{s.sub}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Virtual Pantry Shelf (Visual Anchor) ──────────────── */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="text-xs font-bold text-muted uppercase tracking-wider font-display">
            Virtual Kitchen Shelf
          </div>
          <span className="text-[11px] text-muted font-semibold hidden sm:inline">
            Visual level represents remaining stock
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
          {depleting.slice(0, 5).map((item) => {
            const isAdded = addedItems.has(item.name);
            const fillPercent = Math.max(8, Math.min(95, Math.round((item.days / 30) * 100)));
            const style = jarFluidStyle(item.name, item.days);

            return (
              <div
                key={item.name}
                className="relative w-full h-48 rounded-2xl glass-card overflow-hidden group hover:border-accent hover:shadow-[0_8px_30px_rgba(255,90,0,0.06)] transition-all duration-300 flex flex-col justify-between p-4 cursor-pointer"
                onClick={(e) => handleAddToCart(item.name, e)}
              >
                {/* Jar Lid detail */}
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-12 h-2 bg-neutral-300/80 dark:bg-neutral-700/80 rounded-b-md z-20" />

                {/* Liquid Fill */}
                <div
                  className="absolute bottom-0 left-0 w-full transition-all duration-1000 ease-out z-10"
                  style={{
                    height: `${fillPercent}%`,
                    ...style
                  }}
                />

                {/* Content Overlay */}
                <div className="relative z-20 flex flex-col h-full justify-between pointer-events-none">
                  {/* Top: Name and category */}
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[10px] uppercase font-bold text-muted font-display tracking-wider">
                      {item.name.toLowerCase().includes("milk") ? "Dairy" :
                       item.name.toLowerCase().includes("oil") ? "Oils" :
                       item.name.toLowerCase().includes("egg") ? "Proteins" : "Staple"}
                    </span>
                    <span className="font-extrabold text-xs text-foreground tracking-tight line-clamp-2 leading-tight font-display">
                      {item.name.split(" — ")[0]}
                    </span>
                  </div>

                  {/* Middle: Big Countdown */}
                  <div className="flex flex-col items-start my-auto">
                    <span className="text-2xl font-black text-foreground font-display leading-none">
                      {item.days}
                    </span>
                    <span className="text-[10px] font-bold text-muted uppercase tracking-wider font-display mt-0.5">
                      {item.days === 1 ? "day left" : "days left"}
                    </span>
                  </div>

                  {/* Bottom Info */}
                  <div className="text-[9px] font-bold text-muted/90 uppercase tracking-widest font-display">
                    {fillPercent}% full
                  </div>
                </div>

                {/* Circular Add-To-Cart Plus Button (44px target) */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleAddToCart(item.name, e);
                  }}
                  className={`absolute bottom-3 right-3 w-11 h-11 rounded-full flex items-center justify-center transition-all duration-300 z-30 cursor-pointer shadow-md border ${
                    isAdded
                      ? "bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-500"
                      : "bg-white dark:bg-neutral-800 text-muted hover:text-accent hover:border-accent border-border"
                  }`}
                  aria-label={`Add ${item.name} to cart`}
                >
                  <ShoppingCart className="h-4.5 w-4.5" />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Live Depletion Timeline ─────────────────────────── */}
      <div className="glass-card overflow-hidden rounded-2xl shadow-sm border border-border/80">
        <div className="px-6 py-4.5 border-b border-border/60 flex items-center justify-between bg-white/40 dark:bg-neutral-900/20">
          <div className="flex items-center gap-3">
            <div className="dot-pulse" />
            <span className="text-xs font-bold uppercase tracking-wider text-foreground font-display">Running Out Soon</span>
          </div>
          <Link href="/predictions" className="text-xs font-bold text-accent hover:text-accent/85 hover:underline transition-colors flex items-center gap-1">
            View Full Timeline <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        <div className="divide-y divide-border/60">
          {depleting.map((item) => {
            const u = urgencyColor(item.days);
            const isAdded = addedItems.has(item.name);
            const isPinned = pinnedItems.has(item.name);
            const isSnoozed = snoozedItems.has(item.name);

            return (
              <div
                key={item.name}
                className={`group px-6 py-5.5 flex flex-col gap-4 hover:bg-white/40 dark:hover:bg-neutral-900/10 transition-all ${
                  isSnoozed ? "opacity-35" : ""
                }`}
              >
                {/* Top row */}
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className={`pill ${u.pill} font-semibold font-display`}>
                      {urgencyLabel(item.days)}
                    </span>
                    <span className="font-extrabold text-sm tracking-wide text-foreground font-display truncate">
                      {item.name}
                    </span>
                  </div>
                  <div className="text-xs text-muted/80 shrink-0 font-semibold font-display">
                    {certaintyLabel(item.conf)}
                  </div>
                </div>

                {/* Depletion bar */}
                <div className="depletion-bar rounded-full h-1.5 bg-neutral-200/50 dark:bg-neutral-800/40">
                  <div
                    className="depletion-bar-fill rounded-full"
                    style={{
                      width: `${barFill(item.days)}%`,
                      background: isSnoozed
                        ? "#9ca3af"
                        : `linear-gradient(90deg, ${u.bar} 0%, #ff8a00 100%)`
                    }}
                  />
                </div>

                {/* Bottom stats & Quick Actions */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-0.5">
                  <div className="text-xs text-muted/90 flex gap-4 font-medium">
                    <span>{formatAvg(item.avg)}</span>
                    <span className="text-border">|</span>
                    <span>{formatCycle(item.cycle)}</span>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <button
                      onClick={(e) => handleAddToCart(item.name, e)}
                      className={`h-11 px-4.5 rounded-full text-xs font-bold tracking-wide transition-all duration-200 flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.98] ${
                        isAdded
                          ? "bg-emerald-600 text-white hover:bg-emerald-700"
                          : "bg-accent text-white hover:bg-accent/90"
                      }`}
                    >
                      <ShoppingCart className="h-4 w-4" />
                      {isAdded ? "Added to Cart" : "Add to Cart"}
                    </button>
                    <button
                      onClick={(e) => handlePinToSunday(item.name, e)}
                      className={`h-11 px-4.5 rounded-full text-xs font-bold border transition-all duration-200 flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.98] ${
                        isPinned
                          ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-200"
                          : "bg-white/80 dark:bg-neutral-800 text-muted hover:text-foreground border-border hover:border-muted-foreground"
                      }`}
                    >
                      <Calendar className="h-4 w-4" />
                      {isPinned ? "Pinned to Sunday" : "Pin to Sunday"}
                    </button>
                    <button
                      onClick={(e) => handleSnoozeAlert(item.name, e)}
                      className={`h-11 px-4.5 rounded-full text-xs font-bold border transition-all duration-200 flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.98] ${
                        isSnoozed
                          ? "bg-neutral-800 text-neutral-200 border-neutral-700"
                          : "bg-white/80 dark:bg-neutral-800 text-muted hover:text-red-500 border-border hover:border-red-200"
                      }`}
                    >
                      {isSnoozed ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
                      {isSnoozed ? "Unpause Alerts" : "Pause Alerts"}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {/* ── Toast Notification ─────────────────────────────── */}
      {toastMessage && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 bg-neutral-900/95 dark:bg-neutral-100/95 backdrop-blur-md text-white dark:text-neutral-900 px-5 py-3 rounded-full shadow-[0_12px_40px_rgba(0,0,0,0.25)] flex items-center gap-2 border border-neutral-800 dark:border-neutral-200 animate-in fade-in slide-in-from-bottom-4 duration-300">
          <span className="text-xs font-bold tracking-wide font-display">{toastMessage}</span>
        </div>
      )}

    </div>
  );
}

