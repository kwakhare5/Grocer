'use client';

import { useEffect, useState } from 'react';
import { Tag, TrendingUp, TrendingDown } from 'lucide-react';
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
    suggestion: "Use canned tomatoes or tomato puree for cooking this week. This price spike typically lasts 8-12 days before returning to normal.",
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
    suggestion: "Excellent time to stock up 2-3 bottles! Cooking oil is currently 23% cheaper than your normal household purchase price.",
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
  SPIKE:  { pill: "pill-danger",  label: "Price Spiked (Expensive)", color: "#ff5a00" },
  DIP:    { pill: "pill-ok",      label: "Price Dropped (Good Deal)",  color: "#16a34a" },
  WATCH:  { pill: "pill-accent",  label: "Price Rising",               color: "#ff5a00" },
  STABLE: { pill: "pill-muted",   label: "Stable Price",               color: "#6b6560" },
};

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
      <defs>
        <linearGradient id={`grad-${signal}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0.0" />
        </linearGradient>
      </defs>
      <polygon
        points={`${pad},${H - pad} ${points} ${W - pad},${H - pad}`}
        fill={`url(#grad-${signal})`}
      />
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
      {(() => {
        const last = points.split(' ').pop()!.split(',');
        const cx = last[0];
        const cy = last[1];
        return (
          <g>
            {/* Pulsing indicator ring */}
            <circle
              cx={cx}
              cy={cy}
              r="6"
              fill={color}
              className="animate-ping"
              style={{ transformOrigin: `${cx}px ${cy}px`, opacity: 0.4 }}
            />
            {/* Solid core dot */}
            <circle cx={cx} cy={cy} r="3" fill={color} />
          </g>
        );
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
    <div className="flex flex-col gap-10">

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-2.5">
        <div className="text-accent text-[11px] font-bold tracking-wider uppercase flex items-center gap-1.5">
          <Tag className="h-4 w-4" />
          <span>Price Alerts</span>
        </div>
        <h1 className="text-4xl font-light tracking-tight leading-tight">
          Grocery Deals & <span className="font-extrabold text-accent">Price Alerts</span>
        </h1>
        <p className="text-sm text-muted max-w-lg leading-relaxed">
          Prices change every day. We track these changes and let you know when things are cheap to stock up, or expensive.
        </p>
      </div>

      {/* ── Alert Banner (Spike + DIP) ───────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {commodities.filter((c) => c.signal === 'SPIKE' || c.signal === 'DIP').map((c) => {
          const s = SIGNAL_STYLES[c.signal];
          return (
            <div
              key={c.id}
              onClick={() => setSelected(c.id)}
              className={`card p-6 cursor-pointer flex flex-col gap-4 hover:border-accent transition-all bg-surface border border-border rounded-md
                         ${selected === c.id ? 'border-accent shadow-sm' : ''}`}
            >
              <div className="flex items-center justify-between">
                <span className={`pill ${s.pill} font-semibold flex items-center gap-1`}>
                  {c.signal === 'SPIKE' ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                  <span>{s.label}</span>
                </span>
                <span className="text-xs text-muted font-medium">{c.name}</span>
              </div>
              <div className="flex items-end justify-between gap-4">
                <div>
                  <div className="text-3xl font-black text-foreground" style={{ color: s.color }}>₹{c.current}</div>
                  <div className="text-xs text-muted font-medium">{c.unit}</div>
                </div>
                <Sparkline data={c.history} signal={c.signal} />
              </div>
              <div className="text-xs text-muted font-medium">
                {pctChange(c.current, c.avg30d)} compared to your 30-day average (₹{c.avg30d})
              </div>
            </div>
          );
        })}
      </div>

      {/* ── All Commodities ─────────────────────────────────── */}
      <div className="card overflow-hidden bg-surface rounded-md">
        <div className="px-6 py-4 border-b border-border text-xs font-bold text-muted uppercase tracking-wider">
          Price History (Last 10 Days)
        </div>
        <div className="divide-y divide-border">
          {commodities.map((c) => {
            const s = SIGNAL_STYLES[c.signal];
            const pct = pctChange(c.current, c.avg30d);
            return (
              <div
                key={c.id}
                onClick={() => setSelected(c.id)}
                className={`group px-6 py-4 flex items-center gap-6 cursor-pointer hover:bg-neutral-50/50 dark:hover:bg-neutral-900/10 transition-colors
                           ${selected === c.id ? 'bg-neutral-50/40 dark:bg-neutral-900/10' : ''}`}
              >
                <Sparkline data={c.history} signal={c.signal} />
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-sm text-foreground truncate">{c.name}</div>
                  <div className="text-xs text-muted mt-1 font-medium">
                    ₹{c.current} {c.unit} · 30-day average ₹{c.avg30d}
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className={`text-sm font-bold`} style={{ color: s.color }}>
                    {pct}
                  </span>
                  <span className={`pill ${s.pill} font-semibold flex items-center gap-1`}>
                    {c.signal === 'SPIKE' || c.signal === 'WATCH' ? <TrendingUp className="h-3 w-3" /> :
                     c.signal === 'DIP' ? <TrendingDown className="h-3 w-3" /> : null}
                    <span>{s.label.split(" (")[0]}</span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Detail Panel for selected commodity ─────────────── */}
      {active && active.suggestion && (
        <div className="card p-6 flex flex-col gap-4 border-accent rounded-md bg-surface shadow-sm">
          <div className="text-xs font-bold text-accent uppercase tracking-wider">
            Refill Suggestion · {active.name}
          </div>
          <p className="text-sm leading-relaxed text-foreground">{active.suggestion}</p>
          <div className="grid grid-cols-3 gap-4 pt-4 border-t border-border">
            {[
              { label: "Today's Price",  value: `₹${active.current}` },
              { label: "Normal Price",    value: `₹${active.avg30d}`  },
              { label: "Price Change",         value: pctChange(active.current, active.avg30d) },
            ].map((s) => (
              <div key={s.label} className="flex flex-col gap-1.5">
                <span className="text-[10px] font-bold text-muted uppercase tracking-wider">{s.label}</span>
                <span className="text-base font-extrabold text-foreground">{s.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
