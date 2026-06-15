'use client';

import { useEffect, useState } from 'react';
import { Users, History, Layers, ShieldCheck, Map, Calendar, Sparkles } from 'lucide-react';
import { householdApi, predictionsApi, APIPrediction } from '../../lib/api';

interface ProfileData {
  type: string;
  confidence: number;
  trackedSince: string;
  monthsTracked: number;
  itemsModeled: number;
  accuracy: string;
  ordersAnalyzed: number;
  stockoutsPrevented: number;
}

interface ConsumptionItem {
  label: string;
  rate: string;
  conf: number;
  id: string;
}

const FALLBACK_PROFILE: ProfileData = {
  type:        "Family (3–4 members)",
  confidence:  84,
  trackedSince: "January 2026",
  monthsTracked: 4,
  itemsModeled: 34,
  accuracy:    "±1 day",
  ordersAnalyzed: 87,
  stockoutsPrevented: 12,
};

const FALLBACK_CONSUMPTION: ConsumptionItem[] = [
  { label: "Amul Milk",        rate: "1.1 L/day",   conf: 76, id: "INS_001" },
  { label: "Aashirvaad Atta",  rate: "280 g/day",   conf: 68, id: "INS_002" },
  { label: "Sunflower Oil",    rate: "68 ml/day",   conf: 87, id: "INS_003" },
  { label: "Eggs",             rate: "2.3 pcs/day", conf: 88, id: "INS_005" },
  { label: "Basmati Rice",     rate: "200 g/day",   conf: 71, id: "INS_004" },
];

const ANOMALIES = [
  {
    type:  "Family Travel",
    color: "text-amber-600",
    bg:    "bg-amber-500/10",
    date:  "March 15 – 24, 2026",
    desc:  "9-day travel gap detected. Refill alerts were automatically paused.",
  },
  {
    type:  "Special Event / Guests",
    color: "text-blue-600",
    bg:    "bg-blue-500/10",
    date:  "February 8, 2026",
    desc:  "3x surge in dairy consumption. Spike was excluded from normal averages.",
  },
];

const COMPOSITION_LABELS: Record<string, string> = {
  "solo":         "Solo (1 person)",
  "couple":       "Couple (2 people)",
  "family_small": "Family (3–4 members)",
  "family_large": "Large Family (5+ members)",
};

function formatRate(rate: number, name: string): string {
  const lowerName = name.toLowerCase();
  if (lowerName.includes("oil")) {
    return `${Math.round(rate * 1000)} ml daily`;
  }
  if (lowerName.includes("milk")) {
    return `${rate.toFixed(1)} L daily`;
  }
  if (lowerName.includes("atta") || lowerName.includes("rice") || lowerName.includes("salt") || lowerName.includes("butter")) {
    if (rate < 1.0) {
      return `${Math.round(rate * 1000)} g daily`;
    }
    return `${rate.toFixed(2)} kg daily`;
  }
  if (lowerName.includes("eggs")) {
    return `${rate.toFixed(1)} eggs daily`;
  }
  return `${rate.toFixed(2)} units daily`;
}

function certaintyLabel(conf: number) {
  if (conf >= 85) return "Very High";
  if (conf >= 70) return "High";
  return "Normal";
}

export default function HouseholdPage() {
  const [profile, setProfile] = useState<ProfileData>(FALLBACK_PROFILE);
  const [consumption, setConsumption] = useState<ConsumptionItem[]>(FALLBACK_CONSUMPTION);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [profRes, predRes] = await Promise.all([
          householdApi.getProfile("demo_user_001"),
          predictionsApi.getForHousehold("demo_user_001")
        ]);

        const prof = profRes.data;
        const pred = predRes.data;

        if (prof) {
          setProfile({
            type: COMPOSITION_LABELS[prof.composition] || FALLBACK_PROFILE.type,
            confidence: prof.composition_confidence ? Math.round(prof.composition_confidence * 100) : FALLBACK_PROFILE.confidence,
            trackedSince: prof.created_at ? new Date(prof.created_at).toLocaleDateString("en-US", { month: "long", year: "numeric" }) : FALLBACK_PROFILE.trackedSince,
            monthsTracked: FALLBACK_PROFILE.monthsTracked,
            itemsModeled: pred.total_items || FALLBACK_PROFILE.itemsModeled,
            accuracy: FALLBACK_PROFILE.accuracy,
            ordersAnalyzed: FALLBACK_PROFILE.ordersAnalyzed,
            stockoutsPrevented: FALLBACK_PROFILE.stockoutsPrevented
          });
        }

        if (pred && pred.predictions && pred.predictions.length > 0) {
          const formattedConsumption = pred.predictions.map((p: APIPrediction) => ({
            label: p.item_name.split(" — ")[0].split(" (")[0], // Clean name
            rate: formatRate(p.avg_daily_consumption, p.item_name),
            conf: Math.round((p.confidence_score || 0.5) * 100),
            id: p.item_id
          }));
          setConsumption(formattedConsumption.slice(0, 5));
        }

      } catch (err) {
        console.warn("Failed to load household profile from DB, using fallback mocks.", err);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, []);

  return (
    <div className="flex flex-col gap-10">

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-2.5">
        <div className="text-accent text-[11px] font-bold tracking-wider uppercase">
          Kitchen Profile {loading && "(LOADING...)"}
        </div>
        <h1 className="text-4xl font-light tracking-tight leading-tight">
          My Kitchen <span className="font-extrabold text-accent">Habits</span>
        </h1>
        <p className="text-sm text-muted max-w-lg leading-relaxed">
          See your family's eating habits, tracking accuracy, and past schedule changes calculated from Swiggy Instamart orders.
        </p>
      </div>

      {/* ── Composition Banner ──────────────────────────────── */}
      <div className="glass-card p-8 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
        <div className="flex items-start gap-4">
          <div className="p-4 bg-accent-dim rounded-2xl text-accent shrink-0 mt-1">
            <Users className="h-6 w-6" />
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="text-[10px] text-accent font-bold uppercase tracking-widest font-display">
              Estimated Family Size
            </div>
            <div className="text-2xl font-black text-foreground font-display">{profile.type}</div>
            <div className="text-xs text-muted font-semibold leading-relaxed">
              Automatically checked from your milk, eggs, flour, and oil purchase cycles.
            </div>
          </div>
        </div>
        <div className="flex flex-col items-start sm:items-end gap-2 shrink-0 pl-14 sm:pl-0">
          <div className="text-3xl font-black text-accent font-display">{profile.confidence}%</div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-muted font-display">Accuracy Rating</div>
          <div className="conf-track w-32">
            <div className="conf-fill" style={{ width: `${profile.confidence}%` }} />
          </div>
        </div>
      </div>

      {/* ── Two-column: System Metrics + Consumption ────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* System Metrics */}
        <div className="glass-card p-6 flex flex-col gap-6 rounded-2xl">
          <div className="text-xs font-bold text-foreground uppercase tracking-wider border-b border-border/60 pb-3.5 font-display">
            Tracking Summary
          </div>
          <div className="grid grid-cols-2 gap-6">
            {[
              { value: profile.ordersAnalyzed,      label: "Refills Tracked", icon: <History className="h-4 w-4 text-accent/80" /> },
              { value: profile.itemsModeled,         label: "Items Tracked", icon: <Layers className="h-4 w-4 text-accent/80" /> },
              { value: profile.monthsTracked + " mo", label: "Months Monitored", icon: <Calendar className="h-4 w-4 text-accent/80" /> },
              { value: profile.stockoutsPrevented,   label: "Saved from running out", icon: <ShieldCheck className="h-4 w-4 text-accent/80" /> },
            ].map((s) => (
              <div key={s.label} className="stat-block flex flex-col gap-1.5">
                <div className="flex items-center gap-1.5">
                  {s.icon}
                  <div className="text-2xl font-black text-foreground font-display leading-none">{s.value}</div>
                </div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-muted font-display">{s.label}</div>
              </div>
            ))}
          </div>
          <div className="border-t border-border/60 pt-4 text-xs text-muted flex justify-between font-medium">
            <span>Tracking active since {profile.trackedSince}</span>
            <span className="text-ok font-semibold">Accuracy {profile.accuracy}</span>
          </div>
        </div>

        {/* Key Consumption Rates */}
        <div className="glass-card p-6 flex flex-col gap-6 rounded-2xl">
          <div className="text-xs font-bold text-foreground uppercase tracking-wider border-b border-border/60 pb-3.5 font-display">
            Grocery Buying History
          </div>
          <div className="flex flex-col gap-5">
            {consumption.map((item) => (
              <div key={item.id} className="flex flex-col gap-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-foreground">{item.label}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-muted font-medium">{item.rate}</span>
                    <span className="text-accent font-bold">{certaintyLabel(item.conf)}</span>
                  </div>
                </div>
                <div className="conf-track">
                  <div className="conf-fill" style={{ width: `${item.conf}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Anomaly Log ─────────────────────────────────────── */}
      <div className="glass-card overflow-hidden rounded-2xl border border-border/80">
        <div className="px-6 py-4 border-b border-border/60 text-xs font-bold text-foreground uppercase tracking-wider font-display">
          Schedule Changes
        </div>
        <div className="divide-y divide-border/60">
          {ANOMALIES.map((a) => (
            <div key={a.type} className="px-6 py-5 flex flex-col sm:flex-row sm:items-start gap-4">
              <div className={`pill ${a.bg} ${a.color} shrink-0 self-start font-semibold font-display flex items-center justify-center gap-1.5 h-11 px-4.5 rounded-full`}>
                {a.type === "Family Travel" ? <Map className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
                <span>{a.type}</span>
              </div>
              <div className="flex flex-col gap-1 min-h-[44px] justify-center">
                <div className="text-xs text-muted font-semibold">{a.date}</div>
                <div className="text-xs text-foreground/80 leading-relaxed font-medium">{a.desc}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="px-6 py-4 bg-neutral-50/20 dark:bg-neutral-900/10 border-t border-border/60 text-[11px] text-muted font-medium leading-relaxed">
          We ignore one-time changes (like holidays or party guest spikes) to keep your normal alerts correct.
        </div>
      </div>

    </div>
  );
}
