"use client";

import { useEffect, useState } from "react";
import { predictionsApi, APIPrediction } from "../../lib/api";
import { Milk, Droplets, CircleDot, Package, Clock, Sparkles, ChevronDown, ChevronUp, Activity, Calendar } from "lucide-react";

interface PredictionItem {
  id: string;
  name: string;
  category: string;
  days: number;
  conf: number;
  avg: string;
  cycle: string;
  depletes: string;
  lastBuy: string;
  qty: string;
  history: { predicted: string; actual: string; error: number }[];
}

const FALLBACK_ITEMS: PredictionItem[] = [
  {
    id:       "INS_001",
    name:     "Amul Taza Milk 1L",
    category: "Dairy",
    days:     1,
    conf:     76,
    avg:      "1.1 L/day",
    cycle:    "2.1 days",
    depletes: "May 18, 2026",
    lastBuy:  "May 17",
    qty:      "1 L",
    history: [
      { predicted: "Apr 15", actual: "Apr 15", error: 0  },
      { predicted: "Apr 17", actual: "Apr 18", error: 1  },
      { predicted: "Apr 20", actual: "Apr 19", error: -1 },
      { predicted: "Apr 22", actual: "Apr 23", error: 1  },
      { predicted: "Apr 25", actual: "Apr 24", error: -1 },
    ],
  },
  {
    id:       "INS_003",
    name:     "Fortune Sunflower Oil 1L",
    category: "Staples",
    days:     2,
    conf:     87,
    avg:      "68 ml/day",
    cycle:    "14.7 days",
    depletes: "May 19, 2026",
    lastBuy:  "May 5",
    qty:      "1 L",
    history: [
      { predicted: "Mar 20", actual: "Mar 21", error: 1  },
      { predicted: "Apr 3",  actual: "Apr 4",  error: 1  },
      { predicted: "Apr 18", actual: "Apr 17", error: -1 },
      { predicted: "May 2",  actual: "May 3",  error: 1  },
      { predicted: "May 18", actual: "—",      error: 0  },
    ],
  },
  {
    id:       "INS_005",
    name:     "Nandini Eggs — Pack of 12",
    category: "Protein",
    days:     4,
    conf:     88,
    avg:      "2.3 pcs/day",
    cycle:    "6.2 days",
    depletes: "May 21, 2026",
    lastBuy:  "May 13",
    qty:      "12 pcs",
    history: [
      { predicted: "Apr 27", actual: "Apr 28", error: 1  },
      { predicted: "May 3",  actual: "May 3",  error: 0  },
      { predicted: "May 9",  actual: "May 10", error: 1  },
      { predicted: "May 15", actual: "May 14", error: -1 },
      { predicted: "May 21", actual: "—",      error: 0  },
    ],
  },
  {
    id:       "INS_002",
    name:     "Aashirvaad Atta 5kg",
    category: "Staples",
    days:     12,
    conf:     68,
    avg:      "280 g/day",
    cycle:    "17 days",
    depletes: "May 29, 2026",
    lastBuy:  "Apr 30",
    qty:      "5 kg",
    history: [
      { predicted: "Jan 17", actual: "Jan 18", error: 1  },
      { predicted: "Feb 3",  actual: "Feb 4",  error: 1  },
      { predicted: "Feb 21", actual: "Feb 20", error: -1 },
      { predicted: "Mar 9",  actual: "Mar 11", error: 2  },
      { predicted: "Mar 28", actual: "Mar 27", error: -1 },
    ],
  },
  {
    id:       "INS_004",
    name:     "India Gate Basmati Rice 5kg",
    category: "Staples",
    days:     19,
    conf:     71,
    avg:      "200 g/day",
    cycle:    "25 days",
    depletes: "Jun 5, 2026",
    lastBuy:  "Apr 15",
    qty:      "5 kg",
    history: [
      { predicted: "Mar 11", actual: "Mar 12", error: 1  },
      { predicted: "Apr 5",  actual: "Apr 5",  error: 0  },
      { predicted: "Apr 30", actual: "May 2",  error: 2  },
      { predicted: "May 27", actual: "—",      error: 0  },
      { predicted: "Jun 21", actual: "—",      error: 0  },
    ],
  },
];

function urgencyStyle(days: number) {
  if (days <= 2) return { pill: "pill-danger",  bar: "#ff5a00", label: "Needs Reorder" };
  if (days <= 5) return { pill: "pill-warning", bar: "#d97706", label: "Running Low"   };
  return             { pill: "pill-muted",    bar: "#7c7267", label: "In Stock"      };
}

function certaintyLabel(conf: number) {
  if (conf >= 85) return "Very High";
  if (conf >= 70) return "High";
  return "Moderate";
}

function getCategoryIcon(cat: string) {
  const c = cat.toLowerCase();
  if (c.includes("dairy") || c.includes("milk")) return <Milk className="h-5 w-5 text-accent/80" />;
  if (c.includes("oil") || c.includes("staples")) return <Droplets className="h-5 w-5 text-accent/80" />;
  if (c.includes("protein") || c.includes("egg")) return <CircleDot className="h-5 w-5 text-accent/80" />;
  return <Package className="h-5 w-5 text-accent/80" />;
}

export default function PredictionsPage() {
  const [items, setItems] = useState<PredictionItem[]>(FALLBACK_ITEMS);
  const [loading, setLoading] = useState(true);
  const [showDetails, setShowDetails] = useState<Record<string, boolean>>({});

  const toggleDetails = (id: string) => {
    setShowDetails(prev => ({ ...prev, [id]: !prev[id] }));
  };

  useEffect(() => {
    async function loadPredictions() {
      try {
        const res = await predictionsApi.getForHousehold("demo_user_001");
        if (res.data && res.data.predictions && res.data.predictions.length > 0) {
          const apiItems = res.data.predictions.map((p: APIPrediction) => {
            const daysLeft = p.days_remaining !== null ? Math.round(p.days_remaining) : 10;
            const mockHist = [
              { predicted: "3 cycles ago", actual: "3 cycles ago", error: 0 },
              { predicted: "2 cycles ago", actual: "2 cycles ago", error: 1 },
              { predicted: "Last cycle", actual: "Last cycle", error: 0 }
            ];
            
            return {
              id: p.item_id,
              name: p.item_name,
              category: p.category || "General",
              days: daysLeft,
              conf: Math.round((p.confidence_score || 0.5) * 100),
              avg: `${p.avg_daily_consumption.toFixed(2)} /day`,
              cycle: `${p.consumption_cycle_days || 7} days`,
              depletes: p.estimated_depletion_date ? new Date(p.estimated_depletion_date).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }) : "Unknown",
              lastBuy: p.last_purchase_date ? new Date(p.last_purchase_date).toLocaleDateString([], { month: 'short', day: 'numeric' }) : "Unknown",
              qty: `${p.last_purchase_quantity || 1}`,
              history: mockHist
            };
          });
          setItems(apiItems);
        }
      } catch (err) {
        console.warn("Failed to load predictions from backend, using default fallback data.", err);
      } finally {
        setLoading(false);
      }
    }
    loadPredictions();
  }, []);

  return (
    <div className="flex flex-col gap-10 relative">
      <div className="absolute top-[-50px] left-[-100px] w-[250px] h-[250px] bg-accent/6 blur-[100px] pointer-events-none -z-10" />

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-2.5">
        <div className="text-accent text-[11px] font-bold tracking-widest uppercase font-display">
          Pantry Inventory & Timeline {loading && "(LOADING...)"}
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight leading-tight font-display text-foreground">
          When Will Things <span className="text-accent">Run Out?</span>
        </h1>
        <p className="text-sm text-muted max-w-lg leading-relaxed font-medium">
          Check estimated depleting timelines and remaining stock. Tap any item to inspect historical calculations and averages.
        </p>
      </div>

      {/* ── Accuracy Banner ─────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { value: "±1 day",  label: "Prediction Delay", sub: "average error margin", icon: <Clock className="h-5 w-5 text-accent/80" /> },
          { value: String(items.length), label: "Staples Tracked", sub: "automatic profiles active", icon: <Activity className="h-5 w-5 text-accent/80" /> },
          { value: items.length > 0 ? `${items[0].conf}%` : "87%", label: "Top Tracker Accuracy", sub: items.length > 0 ? items[0].name.split(" — ")[0] : "Sunflower Oil", icon: <Sparkles className="h-5 w-5 text-accent/80" /> },
        ].map((s) => (
          <div key={s.label} className="glass-card p-5 rounded-2xl flex flex-col gap-2 hover:-translate-y-1 hover:shadow-md transition-all duration-300">
            <div className="flex items-center justify-between">
              <div className="text-2xl font-black text-accent font-display">{s.value}</div>
              {s.icon}
            </div>
            <div className="flex flex-col gap-0.5">
              <div className="text-xs font-bold text-foreground tracking-wide font-display">{s.label}</div>
              <div className="text-[11px] text-muted font-medium leading-normal">{s.sub}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Item List ───────────────────────────────────────── */}
      <div className="flex flex-col gap-4">
        {items.map((item) => {
          const u = urgencyStyle(item.days);
          const fill = Math.max(4, Math.min(100, Math.round((item.days / 30) * 100)));
          const isOpen = !!showDetails[item.id];

          return (
            <div key={item.id} className="glass-card overflow-hidden rounded-2xl border border-border/80 flex flex-col hover:shadow-sm transition-all duration-200">

              {/* Item header row */}
              <div className="px-6 py-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-4 min-w-0">
                  <div className="p-2.5 bg-neutral-100 dark:bg-neutral-800/80 rounded-xl shrink-0">
                    {getCategoryIcon(item.category)}
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="font-extrabold tracking-wide text-sm text-foreground font-display truncate">{item.name}</span>
                    <span className="text-xs text-muted/95 mt-1 font-medium">{item.category} · Last restocked {item.lastBuy} ({item.qty})</span>
                  </div>
                </div>
                <div className="flex items-center gap-6 shrink-0">
                  <div className="flex flex-col items-start sm:items-end gap-0.5">
                    <span className="text-[10px] font-bold text-muted uppercase tracking-wider font-display">Runs Out On</span>
                    <span className="text-sm font-extrabold text-foreground font-display">{item.depletes}</span>
                  </div>
                  <div className="flex flex-col items-start sm:items-end gap-0.5">
                    <span className="text-[10px] font-bold text-muted uppercase tracking-wider font-display">Refill Status</span>
                    <span className={`pill ${u.pill} font-semibold font-display`}>{u.label}</span>
                  </div>
                </div>
              </div>

              {/* Full-width depletion bar */}
              <div className="depletion-bar h-1.5 bg-neutral-200/50 dark:bg-neutral-800/40">
                <div
                  className="depletion-bar-fill"
                  style={{
                    width: `${fill}%`,
                    background: `linear-gradient(90deg, ${u.bar} 0%, #ff8a00 100%)`
                  }}
                />
              </div>

              {/* Details Toggle Button */}
              <button
                onClick={() => toggleDetails(item.id)}
                className="text-xs text-accent hover:text-accent/95 font-bold flex items-center justify-between px-6 h-11 border-t border-border/60 bg-neutral-50/20 dark:bg-neutral-900/10 cursor-pointer font-display transition-colors"
              >
                <span>{isOpen ? "Close detailed calculations & histories" : "Inspect pantry usage & refill cycles"}</span>
                {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </button>

              {/* Collapsible Details */}
              {isOpen && (
                <div className="border-t border-border/60 animate-in fade-in duration-300">
                  {/* Detail panel */}
                  <div className="px-6 py-5 bg-white/40 dark:bg-neutral-900/10 grid grid-cols-2 sm:grid-cols-4 gap-6 text-xs border-b border-border/60">
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[10px] text-muted uppercase tracking-wider font-bold font-display">Daily Usage</span>
                      <span className="font-extrabold text-foreground font-display text-sm">{item.avg}</span>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[10px] text-muted uppercase tracking-wider font-bold font-display">Average Cycle</span>
                      <span className="font-extrabold text-foreground font-display text-sm">{item.cycle}</span>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[10px] text-muted uppercase tracking-wider font-bold font-display">Remaining Days</span>
                      <span className="font-extrabold text-foreground font-display text-sm">{item.days} days</span>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[10px] text-muted uppercase tracking-wider font-bold font-display">History Logs</span>
                      <span className="font-extrabold text-foreground font-display text-sm">{item.history.length} purchases</span>
                    </div>
                  </div>

                  {/* Prediction accuracy table */}
                  <div className="bg-white/10 dark:bg-neutral-900/5">
                    <div className="px-6 py-4 text-[10px] text-muted uppercase tracking-wider font-bold font-display">
                      Refill Timing Analysis (Historical Checks)
                    </div>
                    <div className="px-6 pb-5 overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-muted border-b border-border/40">
                            <th className="text-left pb-2.5 pr-6 font-bold uppercase tracking-wider text-[10px] font-display">Predicted Date</th>
                            <th className="text-left pb-2.5 pr-6 font-bold uppercase tracking-wider text-[10px] font-display">Actual Refill</th>
                            <th className="text-left pb-2.5 font-bold uppercase tracking-wider text-[10px] font-display">Delay/Advance</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/40 font-medium">
                          {item.history.map((h, i) => (
                            <tr key={i} className="hover:bg-neutral-50/50 dark:hover:bg-neutral-900/10 transition-colors">
                              <td className="py-3 pr-6 text-foreground">{h.predicted}</td>
                              <td className="py-3 pr-6 text-foreground">{h.actual}</td>
                              <td className={`py-3 font-extrabold font-display ${
                                h.actual === "—" ? "text-muted" :
                                Math.abs(h.error) <= 1 ? "text-ok" : "text-warning"
                              }`}>
                                {h.actual === "—" ? "In progress" : h.error === 0 ? "Perfect" : `${h.error > 0 ? "Late by " : "Early by "}${Math.abs(h.error)}d`}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

            </div>
          );
        })}
      </div>

    </div>
  );
}
