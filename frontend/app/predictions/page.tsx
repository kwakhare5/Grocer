"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { predictionsApi, APIPrediction } from "../../lib/api";
import { Milk, Droplets, CircleDot, Package, Clock, Sparkles, ChevronDown, ChevronUp, Activity, ShoppingBag } from "lucide-react";

interface OrderHistoryEntry {
  order_id: string;
  placed_at: string;
  items: { item_name: string; quantity: number; price: number }[];
  total: number;
  status: string;
}

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
  fillPct: number;
}

const FALLBACK_ITEMS: PredictionItem[] = [
  { id: "INS_001", name: "Amul Taza Milk 1L",          category: "Dairy",    days: 1,  conf: 76, avg: "1.1 L/day",   cycle: "2.1 days",  depletes: "Tomorrow",        lastBuy: "2 days ago", fillPct: 30 },
  { id: "INS_003", name: "Fortune Sunflower Oil 1L",   category: "Staples",  days: 2,  conf: 87, avg: "68 ml/day",   cycle: "14.7 days", depletes: "In 2 days",       lastBuy: "12 days ago", fillPct: 14 },
  { id: "INS_005", name: "Nandini Eggs (Pack of 12)",  category: "Protein",  days: 4,  conf: 88, avg: "2.3 pcs/day", cycle: "6.2 days",  depletes: "In 4 days",       lastBuy: "2 days ago", fillPct: 65 },
  { id: "INS_002", name: "Aashirvaad Atta 5kg",        category: "Staples",  days: 12, conf: 68, avg: "280 g/day",   cycle: "17 days",   depletes: "In 12 days",      lastBuy: "5 days ago", fillPct: 71 },
  { id: "INS_004", name: "India Gate Basmati Rice 5kg",category: "Staples",  days: 19, conf: 71, avg: "200 g/day",   cycle: "25 days",   depletes: "In 19 days",      lastBuy: "6 days ago", fillPct: 76 },
];

function stockLabel(fillPct: number) {
  if (fillPct <= 20) return { pill: "pill-danger",  label: "Almost Empty" };
  if (fillPct <= 45) return { pill: "pill-warning", label: "Running Low"  };
  return                    { pill: "pill-ok",      label: "Well Stocked" };
}

function getCategoryIcon(cat: string) {
  const c = cat.toLowerCase();
  if (c.includes("dairy") || c.includes("milk")) return <Milk className="h-5 w-5 text-accent/80" />;
  if (c.includes("oil") || c.includes("staples")) return <Droplets className="h-5 w-5 text-accent/80" />;
  if (c.includes("protein") || c.includes("egg")) return <CircleDot className="h-5 w-5 text-accent/80" />;
  return <Package className="h-5 w-5 text-accent/80" />;
}

function barColor(fillPct: number) {
  if (fillPct <= 20) return "#ff5a00";
  if (fillPct <= 45) return "#d97706";
  return "#10b981";
}

function timeAgo(dateStr: string) {
  const d = new Date(dateStr);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000 / 60 / 60 / 24);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  if (diff < 7)  return `${diff} days ago`;
  if (diff < 14) return "Last week";
  if (diff < 30) return `${Math.floor(diff / 7)} weeks ago`;
  return d.toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}

const predFetcher = (userId: string) => predictionsApi.getForHousehold(userId).then(res => res.data);
const orderFetcher = (url: string) => fetch(url).then(r => r.json());

export default function PredictionsPage() {
  const [showDetails, setShowDetails] = useState<Record<string, boolean>>({});

  const toggleDetails = (id: string) => {
    setShowDetails(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const { data: predictionsData, mutate: mutatePredictions, isLoading: predictionsLoading } = useSWR(
    "demo_user_001",
    predFetcher,
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  const { data: ordersData } = useSWR(
    "http://localhost:8000/api/orders/demo_user_001?limit=30",
    orderFetcher,
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  useEffect(() => {
    const handleRefresh = () => mutatePredictions();
    window.addEventListener("refresh-dashboard", handleRefresh);
    return () => window.removeEventListener("refresh-dashboard", handleRefresh);
  }, [mutatePredictions]);

  const loading = predictionsLoading;

  // All items, sorted low stock first
  const items: PredictionItem[] = predictionsData?.predictions && predictionsData.predictions.length > 0
    ? predictionsData.predictions
        .map((p: APIPrediction) => {
          const daysLeft = p.days_remaining !== null ? Math.round(p.days_remaining) : 10;
          const cycle = p.consumption_cycle_days || 30.0;
          const fillPct = Math.max(8, Math.min(95, Math.round((daysLeft / cycle) * 100)));
          return {
            id: p.item_id,
            name: p.item_name,
            category: p.category || "General",
            days: daysLeft,
            conf: Math.round((p.confidence_score || 0.5) * 100),
            avg: `${p.avg_daily_consumption.toFixed(2)} /day`,
            cycle: `${p.consumption_cycle_days || 7} days`,
            depletes: p.estimated_depletion_date
              ? new Date(p.estimated_depletion_date).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" })
              : "Unknown",
            lastBuy: p.last_purchase_date
              ? new Date(p.last_purchase_date).toLocaleDateString([], { day: "numeric", month: "short" })
              : "Unknown",
            fillPct,
          };
        })
        .sort((a: PredictionItem, b: PredictionItem) => a.fillPct - b.fillPct)
    : FALLBACK_ITEMS;

  // Order history: group by item name from fetched orders
  const recentOrders: OrderHistoryEntry[] = ordersData?.orders
    ? [...ordersData.orders].sort(
        (a: OrderHistoryEntry, b: OrderHistoryEntry) =>
          new Date(b.placed_at).getTime() - new Date(a.placed_at).getTime()
      ).slice(0, 20)
    : [];

  // Per-item order history
  function getItemOrders(itemName: string): { date: string; qty: number; price: number }[] {
    if (!recentOrders.length) return [];
    const results: { date: string; qty: number; price: number }[] = [];
    for (const order of recentOrders) {
      for (const oi of order.items) {
        if (oi.item_name.toLowerCase() === itemName.toLowerCase()) {
          results.push({ date: order.placed_at, qty: oi.quantity, price: oi.price });
        }
      }
    }
    return results.slice(0, 5);
  }

  const lowStockCount = items.filter(i => i.fillPct <= 45).length;

  return (
    <div className="flex flex-col gap-10 relative">
      <div className="absolute top-[-50px] left-[-100px] w-[250px] h-[250px] bg-accent/6 blur-[100px] pointer-events-none -z-10" />

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-2.5">
        <div className="text-accent text-[11px] font-bold tracking-widest uppercase font-display">
          Grocery Inventory {loading && "(LOADING...)"}
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight leading-tight font-display text-foreground">
          What's in Your <span className="text-accent">Kitchen?</span>
        </h1>
        <p className="text-sm text-muted max-w-lg leading-relaxed font-medium">
          See all your tracked groceries, how much is left, and when each one was last bought. Tap any item to see its order history.
        </p>
      </div>

      {/* ── Stats ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { value: String(items.length),     label: "Items Tracked",  sub: "actively monitored",      icon: <Activity className="h-5 w-5 text-accent/80" /> },
          { value: String(lowStockCount),    label: "Running Low",    sub: "need restocking soon",     icon: <Clock className="h-5 w-5 text-accent/80" /> },
          { value: String(recentOrders.length || "—"), label: "Recent Orders", sub: "from your history", icon: <Sparkles className="h-5 w-5 text-accent/80" /> },
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
          const { pill, label } = stockLabel(item.fillPct);
          const isOpen = !!showDetails[item.id];
          const itemOrders = getItemOrders(item.name);

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
                    <span className="text-xs text-muted/95 mt-1 font-medium">
                      {item.category} · You use about {item.avg} · Bought every {item.cycle}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-6 shrink-0">
                  <div className="flex flex-col items-start sm:items-end gap-0.5">
                    <span className="text-[10px] font-bold text-muted uppercase tracking-wider font-display">Runs Out On</span>
                    <span className="text-sm font-extrabold text-foreground font-display">{item.depletes}</span>
                  </div>
                  <div className="flex flex-col items-start sm:items-end gap-0.5">
                    <span className="text-[10px] font-bold text-muted uppercase tracking-wider font-display">Stock Level</span>
                    <span className={`pill ${pill} font-semibold font-display`}>{label}</span>
                  </div>
                </div>
              </div>

              {/* Full-width stock bar */}
              <div className="depletion-bar h-1.5 bg-neutral-200/50 dark:bg-neutral-800/40">
                <div
                  className="depletion-bar-fill"
                  style={{
                    width: `${item.fillPct}%`,
                    background: `linear-gradient(90deg, ${barColor(item.fillPct)} 0%, ${barColor(item.fillPct)}99 100%)`
                  }}
                />
              </div>

              {/* Details Toggle */}
              <button
                onClick={() => toggleDetails(item.id)}
                className="text-xs text-accent hover:text-accent/95 font-bold flex items-center justify-between px-6 h-11 border-t border-border/60 bg-neutral-50/20 dark:bg-neutral-900/10 cursor-pointer font-display transition-colors"
              >
                <span>{isOpen ? "Hide order history" : "See past orders for this item"}</span>
                {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </button>

              {/* Order History Panel */}
              {isOpen && (
                <div className="border-t border-border/60 animate-in fade-in duration-300">
                  {/* Quick stats */}
                  <div className="px-6 py-5 bg-white/40 dark:bg-neutral-900/10 grid grid-cols-2 sm:grid-cols-4 gap-6 text-xs border-b border-border/60">
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[10px] text-muted uppercase tracking-wider font-bold font-display">You use</span>
                      <span className="font-extrabold text-foreground font-display text-sm">{item.avg}</span>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[10px] text-muted uppercase tracking-wider font-bold font-display">Buy every</span>
                      <span className="font-extrabold text-foreground font-display text-sm">{item.cycle}</span>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[10px] text-muted uppercase tracking-wider font-bold font-display">Days left</span>
                      <span className="font-extrabold text-foreground font-display text-sm">{item.days} days</span>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[10px] text-muted uppercase tracking-wider font-bold font-display">Stock left</span>
                      <span className="font-extrabold text-foreground font-display text-sm">{item.fillPct}%</span>
                    </div>
                  </div>

                  {/* Past Orders */}
                  <div className="bg-white/10 dark:bg-neutral-900/5">
                    <div className="px-6 py-4 flex items-center gap-2 text-[10px] text-muted uppercase tracking-wider font-bold font-display">
                      <ShoppingBag className="h-3.5 w-3.5" />
                      Past Purchases
                    </div>
                    <div className="px-6 pb-5">
                      {itemOrders.length > 0 ? (
                        <div className="flex flex-col gap-2">
                          {itemOrders.map((o, i) => (
                            <div key={i} className="flex items-center justify-between py-2.5 border-b border-border/30 last:border-0">
                              <div className="flex items-center gap-3">
                                <div className="h-7 w-7 rounded-full bg-accent/10 flex items-center justify-center text-accent text-[10px] font-extrabold font-display shrink-0">
                                  {i + 1}
                                </div>
                                <div className="flex flex-col">
                                  <span className="text-xs font-bold text-foreground font-display">{timeAgo(o.date)}</span>
                                  <span className="text-[10px] text-muted font-medium">
                                    {new Date(o.date).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" })}
                                  </span>
                                </div>
                              </div>
                              <div className="flex items-center gap-4">
                                <span className="text-[11px] text-muted font-medium">Qty: {o.qty}</span>
                                <span className="text-xs font-extrabold text-foreground font-display">₹{o.price.toFixed(0)}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="py-4 text-center text-xs text-muted font-medium">
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

    </div>
  );
}
