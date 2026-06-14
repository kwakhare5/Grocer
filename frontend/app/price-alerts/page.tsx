'use client';
/* ─────────────────────────────────────────────────────────
   Price Intelligence — Demo Scene 4 (hydrated)
   "Show the tomato price chart with a visible spike.
    Show the alert message. This demonstrates you've thought
    beyond restocking — you've thought about price."
   — CLAUDE.md Part 7

   Key visual: SVG sparkline showing tomato price spike.
   The chart is hand-drawn data — no Recharts needed.
 ───────────────────────────────────────────────────────── */
import { useEffect, useState } from 'react';
import { pricesApi } from '../../lib/api';

type PricePoint = { day: string; price: number };

type CommodityData = {
  id: string;
  name: string;
  unit: string;
  current: number;
  avg30d: number;
  signal: 'SPIKE' | 'DIP' | 'STABLE' | 'WATCH';
  history: PricePoint[];
  suggestion?: string | null;
};

const FALLBACK_COMMODITIES: CommodityData[] = [
  {
    id:      "tomatoes",
    name:    "Tomatoes 500g",
    unit:    "per 500g",
    current: 48,
    avg30d:  20,
    signal:  "SPIKE",
    suggestion: "Use canned tomatoes for this week. Spike typically lasts 8-12 days based on past patterns.",
    history: [
      { day: "Apr 18", price: 19 }, { day: "Apr 21", price: 21 },
      { day: "Apr 24", price: 20 }, { day: "Apr 27", price: 22 },
      { day: "Apr 30", price: 23 }, { day: "May 3",  price: 25 },
      { day: "May 6",  price: 29 }, { day: "May 9",  price: 35 },
      { day: "May 12", price: 41 }, { day: "May 15", price: 48 },
    ],
  },
  {
    id:      "oil",
    name:    "Fortune Sunflower Oil 1L",
    unit:    "per litre",
    current: 98,
    avg30d:  127,
    signal:  "DIP",
    suggestion: "Good time to stock 2-3 bottles. Currently 23% below your 30-day average.",
    history: [
      { day: "Apr 18", price: 130 }, { day: "Apr 21", price: 128 },
      { day: "Apr 24", price: 127 }, { day: "Apr 27", price: 125 },
      { day: "Apr 30", price: 120 }, { day: "May 3",  price: 115 },
      { day: "May 6",  price: 110 }, { day: "May 9",  price: 105 },
      { day: "May 12", price: 100 }, { day: "May 15", price: 98  },
    ],
  },
  {
    id:      "onions",
    name:    "Onions 1kg",
    unit:    "per kg",
    current: 42,
    avg30d:  38,
    signal:  "WATCH",
    history: [
      { day: "Apr 18", price: 35 }, { day: "Apr 21", price: 36 },
      { day: "Apr 24", price: 38 }, { day: "Apr 27", price: 37 },
      { day: "Apr 30", price: 39 }, { day: "May 3",  price: 40 },
      { day: "May 6",  price: 41 }, { day: "May 9",  price: 40 },
      { day: "May 12", price: 42 }, { day: "May 15", price: 42 },
    ],
  },
  {
    id:      "milk",
    name:    "Amul Taza Milk 1L",
    unit:    "per litre",
    current: 28,
    avg30d:  28,
    signal:  "STABLE",
    history: [
      { day: "Apr 18", price: 28 }, { day: "Apr 21", price: 28 },
      { day: "Apr 24", price: 28 }, { day: "Apr 27", price: 28 },
      { day: "Apr 30", price: 28 }, { day: "May 3",  price: 28 },
      { day: "May 6",  price: 28 }, { day: "May 9",  price: 28 },
      { day: "May 12", price: 28 }, { day: "May 15", price: 28 },
    ],
  },
];

const SIGNAL_STYLES = {
  SPIKE:  { pill: "pill-danger",  label: "SPIKE ↑",      color: "#dc2626" },
  DIP:    { pill: "pill-ok",      label: "DIP — BUY ↓",  color: "#16a34a" },
  WATCH:  { pill: "pill-accent",  label: "WATCH →",      color: "#ff5a00" },
  STABLE: { pill: "pill-muted",   label: "STABLE",        color: "#6b6560" },
};

/* Render an inline SVG sparkline from price history */
function Sparkline({ data, signal }: { data: PricePoint[]; signal: CommodityData['signal'] }) {
  if (!data || data.length === 0) return null;
  const prices = data.map((d) => d.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;
  const W = 200, H = 48, pad = 4;

  const points = prices
    .map((p, i) => {
      const x = pad + (i / (prices.length - 1)) * (W - pad * 2);
      const y = pad + ((max - p) / range) * (H - pad * 2);
      return `${x},${y}`;
    })
    .join(' ');

  const color = SIGNAL_STYLES[signal].color;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="sparkline">
      {/* Fill area */}
      <polygon
        points={`${pad},${H - pad} ${points} ${W - pad},${H - pad}`}
        fill={color}
        fillOpacity={0.1}
      />
      {/* Line */}
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
      {/* Last dot */}
      {(() => {
        const last = points.split(' ').pop()!.split(',');
        return <circle cx={last[0]} cy={last[1]} r="3" fill={color} />;
      })()}
    </svg>
  );
}

function pctChange(current: number, avg: number) {
  const pct = Math.round(((current - avg) / avg) * 100);
  return pct > 0 ? `+${pct}%` : `${pct}%`;
}

export default function PriceAlertsPage() {
  const [selected, setSelected] = useState<string | null>("tomatoes");
  const [commodities, setCommodities] = useState<CommodityData[]>(FALLBACK_COMMODITIES);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadPrices() {
      try {
        const res = await pricesApi.getFeed();
        if (res.data && res.data.length > 0) {
          setCommodities(res.data);
        }
      } catch (err) {
        console.warn("Failed to load live price feeds, using fallbacks.", err);
      } finally {
        setLoading(false);
      }
    }
    loadPrices();
  }, []);

  const active = commodities.find((c) => c.id === selected) ?? null;

  return (
    <div className="flex flex-col gap-12">

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-3">
        <div className="font-data text-accent text-[10px] tracking-widest uppercase">
          M-04 · Price Intelligence {loading && "(LOADING...)"}
        </div>
        <h1 className="text-5xl font-light tracking-tight uppercase leading-none">
          Price<br />
          <span className="font-black">Intelligence</span>
        </h1>
        <p className="font-data text-sm text-muted max-w-lg">
          Daily commodity price tracking vs your 30-day purchase baseline.
          India&apos;s grocery prices are volatile — this gives you a 1-2 day edge.
        </p>
      </div>

      {/* ── Alert Banner (Spike + DIP) ───────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-border">
        {commodities.filter((c) => c.signal === 'SPIKE' || c.signal === 'DIP').map((c) => {
          const s = SIGNAL_STYLES[c.signal];
          return (
            <div
              key={c.id}
              onClick={() => setSelected(c.id)}
              className={`card p-6 cursor-pointer flex flex-col gap-4 hover:border-accent transition-all
                         ${selected === c.id ? 'border-accent' : ''}`}
            >
              <div className="flex items-center justify-between">
                <span className={`pill ${s.pill}`}>{s.label}</span>
                <span className="font-data text-xs text-muted">{c.name}</span>
              </div>
              <div className="flex items-end justify-between gap-4">
                <div>
                  <div className="stat-value" style={{ color: s.color }}>₹{c.current}</div>
                  <div className="stat-label">{c.unit}</div>
                </div>
                <Sparkline data={c.history} signal={c.signal} />
              </div>
              <div className="font-data text-xs text-muted">
                {pctChange(c.current, c.avg30d)} vs 30-day avg (₹{c.avg30d})
              </div>
            </div>
          );
        })}
      </div>

      {/* ── All Commodities ─────────────────────────────────── */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-border font-data text-[10px] text-muted uppercase tracking-widest">
          Price Feed — 10-Day History
        </div>
        <div className="divide-y divide-border">
          {commodities.map((c) => {
            const s = SIGNAL_STYLES[c.signal];
            const pct = pctChange(c.current, c.avg30d);
            return (
              <div
                key={c.id}
                onClick={() => setSelected(c.id)}
                className={`group px-6 py-4 flex items-center gap-6 cursor-pointer hover:bg-accent-dim transition-colors
                           ${selected === c.id ? 'bg-accent-dim' : ''}`}
              >
                <Sparkline data={c.history} signal={c.signal} />
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm truncate">{c.name}</div>
                  <div className="font-data text-xs text-muted mt-1">
                    ₹{c.current} {c.unit} · 30d avg ₹{c.avg30d}
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className={`font-data text-sm font-bold`} style={{ color: s.color }}>
                    {pct}
                  </span>
                  <span className={`pill ${s.pill}`}>{s.label}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Detail Panel for selected commodity ─────────────── */}
      {active && active.suggestion && (
        <div className="card p-6 flex flex-col gap-4 border-accent">
          <div className="font-data text-[10px] text-accent uppercase tracking-widest">
            AI Recommendation · {active.name}
          </div>
          <p className="text-sm leading-relaxed">{active.suggestion}</p>
          <div className="grid grid-cols-3 gap-4 pt-2 border-t border-border">
            {[
              { label: "Current Price",  value: `₹${active.current}` },
              { label: "30d Average",    value: `₹${active.avg30d}`  },
              { label: "Change",         value: pctChange(active.current, active.avg30d) },
            ].map((s) => (
              <div key={s.label} className="flex flex-col gap-1">
                <span className="font-data text-[10px] text-muted uppercase tracking-widest">{s.label}</span>
                <span className="font-data text-lg font-bold">{s.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
