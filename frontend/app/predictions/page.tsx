"use client";

import { useState, useEffect } from "react";
import { APIPrediction, APIOrder } from "../../lib/api";
import { usePredictions, useOrders } from "../../lib/hooks";
import { transformPredictionsData, PredictionItem, timeAgo } from "../../lib/utils";
import { getCategoryTheme } from "../../lib/theme";
import { Milk, Droplets, CircleDot, Package, Clock, Sparkles, ChevronDown, ChevronUp, Activity, ShoppingBag, Database, AlertCircle, Receipt, Apple, Egg, Croissant } from "lucide-react";

function stockLabel(fillPct: number) {
  if (fillPct <= 20) return { pill: "pill-danger",  label: "Almost Empty" };
  if (fillPct <= 45) return { pill: "pill-warning", label: "Running Low"  };
  return                    { pill: "pill-ok",      label: "Well Stocked" };
}

function barColor(fillPct: number) {
  if (fillPct <= 20) return "var(--danger)";
  if (fillPct <= 45) return "var(--warning)";
  return "var(--ok)";
}





export default function PredictionsPage() {
  const [showDetails, setShowDetails] = useState<Record<string, boolean>>({});

  const toggleDetails = (id: string) => {
    setShowDetails(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const { predictionsData, mutatePredictions, isLoading: predictionsLoading } = usePredictions("demo_user_001");
  const { ordersData } = useOrders("demo_user_001");

  useEffect(() => {
    const handleRefresh = () => mutatePredictions();
    window.addEventListener("refresh-dashboard", handleRefresh);
    return () => window.removeEventListener("refresh-dashboard", handleRefresh);
  }, [mutatePredictions]);

  const loading = predictionsLoading;

  // All items, sorted low stock first
  const items: PredictionItem[] = transformPredictionsData(predictionsData?.predictions);

  // Order history: group by item name from fetched orders
  const recentOrders: APIOrder[] = ordersData?.orders
    ? [...ordersData.orders].sort(
        (a: APIOrder, b: APIOrder) =>
          new Date(b.placed_at).getTime() - new Date(a.placed_at).getTime()
      ).slice(0, 20)
    : [];

  // Per-item order history
  function getItemOrders(itemName: string): { date: string; qty: number; price: number; platform?: string }[] {
    if (!recentOrders.length) return [];
    const results: { date: string; qty: number; price: number; platform?: string }[] = [];
    for (const order of recentOrders) {
      for (const oi of order.items) {
        if (oi.item_name.toLowerCase() === itemName.toLowerCase()) {
          results.push({ date: order.placed_at, qty: oi.quantity, price: oi.price, platform: order.platform });
        }
      }
    }
    return results.slice(0, 5);
  }

  const lowStockCount = items.filter(i => i.fillPct <= 45).length;

  return (
    <div className="flex flex-col gap-10 relative">

      {/* ── App Header ──────────────────────────────────────── */}
      <div className="flex flex-col gap-2.5 border-b border-border/40 pb-8">
        <div className="text-accent text-[11px] font-bold tracking-widest uppercase font-display flex items-center gap-1.5">
          <Activity className="h-3.5 w-3.5" />
          <span>My Groceries {loading && "(LOADING...)"}</span>
        </div>
        <h1 className="text-4xl font-bold tracking-tight leading-none font-display text-foreground">
          {"What's in Your "}
          <span className="title-accent">Kitchen?</span>
        </h1>
        <p className="text-sm text-muted max-w-lg leading-relaxed font-medium mt-1">
          Detailed stock predictions, usage trends, and order history for all tracked groceries.
        </p>
      </div>

      {/* ── 2-Column App Grid ────────────────────────────────── */}
      <div className="grid grid-cols-12 gap-8 items-start">
        
        {/* Main List Column (Left, col-span-8) */}
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-4">
          {items.map((item) => {
            const { pill, label } = stockLabel(item.fillPct);
            const isOpen = !!showDetails[item.id];
            const itemOrders = getItemOrders(item.name);
            const theme = getCategoryTheme(item.category);
            const CatIcon = theme.icon;

            return (
              <div key={item.id} className="glass-card overflow-hidden flex flex-col transition-all duration-200">

                {/* Item header row */}
                <div className="px-5 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div 
                      style={{ color: theme.text, backgroundColor: theme.bg, borderColor: theme.border }}
                      className="p-2 rounded-lg border shrink-0"
                    >
                      <CatIcon className="h-4 w-4" />
                    </div>
                    <div className="flex flex-col min-w-0">
                      <span className="font-extrabold tracking-wide text-xs text-foreground font-display truncate">{item.name}</span>
                      <span className="text-[10px] text-muted font-medium mt-0.5">
                        {item.category} · Uses {item.avg} · Cycle: {item.cycle}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-5 shrink-0">
                    <div className="flex flex-col items-start sm:items-end gap-0.5">
                      <span className="text-[9px] font-bold text-muted uppercase tracking-wider font-display">Runs Out On</span>
                      <span className="text-xs font-extrabold text-foreground font-display">{item.depletes}</span>
                    </div>
                    <div className="flex flex-col items-start sm:items-end gap-0.5">
                      <span className="text-[9px] font-bold text-muted uppercase tracking-wider font-display">Stock Level</span>
                      <span className={`pill ${pill} font-semibold font-display`}>{label}</span>
                    </div>
                  </div>
                </div>

                {/* Full-width stock bar */}
                <div className="depletion-bar h-1 bg-neutral-200/50">
                  <div
                    className="depletion-bar-fill"
                    style={{
                      width: `${item.fillPct}%`,
                      backgroundColor: barColor(item.fillPct)
                    }}
                  />
                </div>

                {/* Details Toggle Button */}
                <button
                  onClick={() => toggleDetails(item.id)}
                  className="text-[10px] text-accent hover:text-accent/95 font-extrabold flex items-center justify-between px-5 h-9 border-t border-border/40 bg-neutral-50/20 cursor-pointer font-display transition-colors"
                >
                  <span>{isOpen ? "HIDE PURCHASE HISTORY" : "SEE DETAILED HISTORY"}</span>
                  {isOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>

                {/* Order History Panel */}
                {isOpen && (
                  <div className="border-t border-border/40 animate-in fade-in duration-200 bg-neutral-50/5">
                    {/* Quick Stats Grid */}
                    <div className="px-5 py-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs border-b border-border/40">
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[9px] text-muted uppercase tracking-wider font-bold font-display">You use</span>
                        <span className="font-extrabold text-foreground font-display text-[11px]">{item.avg}</span>
                      </div>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[9px] text-muted uppercase tracking-wider font-bold font-display">Buy every</span>
                        <span className="font-extrabold text-foreground font-display text-[11px]">{item.cycle}</span>
                      </div>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[9px] text-muted uppercase tracking-wider font-bold font-display">Days left</span>
                        <span className="font-extrabold text-foreground font-display text-[11px]">{item.days} days</span>
                      </div>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[9px] text-muted uppercase tracking-wider font-bold font-display">Stock left</span>
                        <span className="font-extrabold text-foreground font-display text-[11px]">{item.fillPct}%</span>
                      </div>
                    </div>

                    {/* Past Purchases History List */}
                    <div className="bg-neutral-50/10">
                      <div className="px-5 py-3 flex items-center gap-1.5 text-[9px] text-muted uppercase tracking-wider font-bold font-display border-b border-border/30">
                        <ShoppingBag className="h-3 w-3" />
                        <span>Past Purchases</span>
                      </div>
                      <div className="px-5 pb-3">
                        {itemOrders.length > 0 ? (
                          <div className="flex flex-col">
                            {itemOrders.map((o, i) => (
                              <div key={i} className="flex items-center justify-between py-2 border-b border-border/30 last:border-0">
                                <div className="flex items-center gap-3">
                                  <div className="h-6 w-6 rounded-md bg-accent/8 text-accent text-[9px] font-extrabold font-display flex items-center justify-center shrink-0">
                                    {i + 1}
                                  </div>
                                  <div className="flex flex-col">
                                    <span className="text-xs font-bold text-foreground font-display">{timeAgo(o.date)}</span>
                                    <span className="text-[9px] text-muted font-medium">
                                      {new Date(o.date).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" })}
                                    </span>
                                  </div>
                                </div>
                                <div className="flex items-center gap-4">
                                  <span className="text-[10px] text-muted font-medium">Qty: {o.qty}</span>
                                  <span className="text-xs font-extrabold text-foreground font-display">₹{o.price.toFixed(0)}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="py-4 text-center text-[10px] text-muted font-medium">
                            No order history found for this item yet.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Stats Column (Right, col-span-4) */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-4">
          <div className="glass-card p-6 flex flex-col gap-4">
            <span className="font-extrabold text-xs text-foreground font-display uppercase tracking-wider">Metrics Overview</span>
            <div className="flex flex-col gap-3.5">
              {[
                { value: String(items.length),     label: "Items Tracked",  sub: "actively monitored",      icon: Database },
                { value: String(lowStockCount),    label: "Running Low",    sub: "need restocking soon",     icon: AlertCircle },
                { value: String(recentOrders.length || "—"), label: "Recent Orders", sub: "from your history", icon: Receipt },
              ].map((s) => {
                const Icon = s.icon;
                const c = 
                  s.label.includes("Tracked") ? { text: "#0066CC", bg: "#E6F5FF", border: "rgba(0,102,204,0.15)" } :
                  s.label.includes("Low") ? { text: "#D96B27", bg: "#FFF3E6", border: "rgba(217,107,39,0.15)" } :
                  { text: "#4B5563", bg: "#F3F4F6", border: "rgba(75, 85, 99, 0.15)" }; // Slate Gray for Recent Orders to minimize violet
                return (
                  <div key={s.label} className="flex items-center gap-3.5 border-b border-border/40 pb-3 last:border-0 last:pb-0">
                    <div 
                      className="p-2 rounded-lg border shrink-0"
                      style={{ backgroundColor: c.bg, borderColor: c.border, color: c.text }}
                    >
                      <Icon className="h-4.5 w-4.5" />
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
        </div>

      </div>
    </div>
  );
}
