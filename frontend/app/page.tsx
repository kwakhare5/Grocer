"use client";

import { useEffect, useState } from "react";
import Link from 'next/link';
import { predictionsApi, APIPrediction } from "../lib/api";

interface DepletingItem {
  name: string;
  days: number;
  conf: number;
  avg: string;
  cycle: string;
  urgent: boolean;
}

const STATS = [
  { value: "34",     label: "Items Modeled",         sub: "across 4 months of orders" },
  { value: "±1.4d",  label: "Avg Prediction Error",  sub: "last 30 days" },
  { value: "12",     label: "Stockouts Prevented",   sub: "since January 2026" },
  { value: "87%",    label: "Peak Confidence",        sub: "Fortune Sunflower Oil" },
];

const FALLBACK_DEPLETING: DepletingItem[] = [
  { name: "Amul Taza Milk 1L",        days: 1,  conf: 76, avg: "1.1L/day",  cycle: "2.1d",  urgent: true  },
  { name: "Fortune Sunflower Oil 1L",  days: 2,  conf: 87, avg: "68ml/day", cycle: "14.7d", urgent: true  },
  { name: "Nandini Eggs — Pack of 12", days: 4,  conf: 88, avg: "2.3/day",  cycle: "6.2d",  urgent: false },
  { name: "Aashirvaad Atta 5kg",       days: 12, conf: 68, avg: "280g/day", cycle: "17d",   urgent: false },
  { name: "Tata Salt 1kg",             days: 21, conf: 61, avg: "8g/day",   cycle: "28d",   urgent: false },
];

function urgencyColor(days: number) {
  if (days <= 1) return { bar: "#dc2626", text: "text-red-500",   pill: "pill-danger"  };
  if (days <= 3) return { bar: "#d97706", text: "text-amber-500", pill: "pill-warning" };
  return             { bar: "#6b6560", text: "text-muted",      pill: "pill-muted"   };
}

function barFill(days: number) {
  return Math.min(100, Math.max(4, Math.round((days / 30) * 100)));
}

export default function Home() {
  const [depleting, setDepleting] = useState<DepletingItem[]>(FALLBACK_DEPLETING);
  const [loading, setLoading] = useState(true);

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

  return (
    <div className="flex flex-col gap-12">

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-3">
        <div className="font-data text-accent text-[10px] tracking-widest uppercase">
          Instamart Intelligence · System Index {loading && "(LOADING...)"}
        </div>
        <h1 className="text-5xl font-light tracking-tight uppercase leading-none">
          Household<br />
          <span className="font-black">Intelligence</span>
        </h1>
        <p className="font-data text-sm text-muted max-w-lg">
          The household AI that knows your kitchen better than you do.
          Trained on 4 months of order history. 34 items modeled.
        </p>
      </div>

      {/* ── 4 Stat Blocks ───────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-border">
        {STATS.map((s) => (
          <div key={s.label} className="card p-6 flex flex-col gap-3">
            <div className="stat-value text-accent">{s.value}</div>
            <div className="flex flex-col gap-1">
              <div className="stat-label">{s.label}</div>
              <div className="font-data text-[11px] text-muted">{s.sub}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Live Depletion Timeline ─────────────────────────── */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="dot-pulse" />
            <span className="font-data text-xs tracking-widest uppercase">Live Depletion Monitor</span>
          </div>
          <Link href="/predictions" className="font-data text-[10px] text-accent tracking-widest uppercase hover:underline">
            View All →
          </Link>
        </div>

        <div className="divide-y divide-border">
          {depleting.map((item) => {
            const u = urgencyColor(item.days);
            return (
              <div
                key={item.name}
                className="group px-6 py-4 flex flex-col gap-3 hover:bg-accent-dim transition-colors cursor-pointer"
              >
                {/* Top row */}
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className={`pill ${u.pill}`}>
                      T-{item.days}d
                    </span>
                    <span className="font-semibold text-sm tracking-wide truncate">
                      {item.name}
                    </span>
                  </div>
                  <div className="font-data text-xs text-muted shrink-0">
                    CONF: <span className={u.text}>{item.conf}%</span>
                  </div>
                </div>

                {/* Depletion bar */}
                <div className="depletion-bar">
                  <div
                    className="depletion-bar-fill"
                    style={{ width: `${barFill(item.days)}%`, background: u.bar }}
                  />
                </div>

                {/* Bottom stats */}
                <div className="font-data text-[11px] text-muted flex gap-4">
                  <span>AVG {item.avg}</span>
                  <span>CYCLE {item.cycle}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Module Grid ─────────────────────────────────────── */}
      <div>
        <div className="font-data text-[10px] text-muted uppercase tracking-widest mb-4">
          Intelligence Modules
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-border">
          {[
            { href: "/household",    tag: "M-01", title: "Household Profile",   desc: "Inferred composition · Anomaly log · Model health" },
            { href: "/predictions",  tag: "M-02", title: "Predictions",         desc: "Full depletion timeline · Confidence breakdown" },
            { href: "/recipes",      tag: "M-03", title: "Recipe Intelligence", desc: "Pantry-aware meal planning · Missing-item cart" },
            { href: "/price-alerts", tag: "M-04", title: "Price Intelligence",  desc: "Commodity spikes · Dip alerts · Buy signals" },
          ].map((m) => (
            <Link
              key={m.href}
              href={m.href}
              className="card group p-6 flex items-start justify-between gap-4 hover:border-accent transition-all"
            >
              <div className="flex flex-col gap-2">
                <div className="font-data text-[10px] text-muted tracking-widest uppercase">{m.tag}</div>
                <div className="font-bold uppercase tracking-wide group-hover:text-accent transition-colors">{m.title}</div>
                <div className="font-data text-xs text-muted leading-relaxed">{m.desc}</div>
              </div>
              <span className="text-muted group-hover:text-accent transition-colors text-xl mt-1">→</span>
            </Link>
          ))}
        </div>
      </div>

    </div>
  );
}

