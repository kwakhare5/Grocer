"use client";

import { useEffect, useState } from "react";
import { Users, History, Layers, ShieldCheck, Map, Calendar } from "lucide-react";
import { householdApi, predictionsApi, APIPrediction } from "../../lib/api";
import { COLOR_PALETTE } from "../../lib/theme";

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
    date:  "March 15 – 24, 2026",
    desc:  "9-day travel gap detected. Refill alerts were automatically paused.",
  },
  {
    type:  "Special Event / Guests",
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
  if (conf >= 85) return "Very sure";
  if (conf >= 70) return "Pretty sure";
  return "Guessing";
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

      {/* ── App Header ──────────────────────────────────────── */}
      <div className="flex flex-col gap-2.5 border-b border-border/40 pb-8">
        <div className="text-accent text-[11px] font-bold tracking-wider uppercase font-display flex items-center gap-1.5">
          <Users className="h-4 w-4" />
          <span>Kitchen Profile {loading && "(LOADING...)"}</span>
        </div>
        <h1 className="text-4xl font-bold tracking-tight leading-none font-display text-foreground">
          My Kitchen <span className="title-accent">Habits</span>
        </h1>
        <p className="text-sm text-muted max-w-lg leading-relaxed font-medium mt-1">
          {"Analysis of your family's size, buying intervals, and eating anomalies."}
        </p>
      </div>

      {/* ── 2-Column App Grid ────────────────────────────────── */}
      <div className="grid grid-cols-12 gap-8 items-start">
        
        {/* Profile Details & Anomalies (Left, col-span-8) */}
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
          
          {/* Estimated Family Size Banner */}
          <div className="glass-card p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-accent/8 rounded-lg text-accent shrink-0 mt-0.5">
                <Users className="h-5 w-5" />
              </div>
              <div className="flex flex-col">
                <div className="text-[9px] text-accent font-bold uppercase tracking-wider font-display">
                  Family Size Estimate
                </div>
                <div className="text-xl font-black text-foreground font-display mt-0.5">{profile.type}</div>
                <div className="text-[11px] text-muted font-medium leading-relaxed mt-1">
                  Estimated based on purchase frequency and average consumption rates of staples.
                </div>
              </div>
            </div>
            
            <div className="flex flex-col items-start sm:items-end gap-1.5 shrink-0 pl-12 sm:pl-0">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted font-display">Confidence</span>
              <span className="text-2xl font-black text-accent font-display leading-none">{profile.confidence}%</span>
              <div className="conf-track w-28 h-1 bg-neutral-200/50 rounded-md">
                <div className="conf-fill h-full bg-accent rounded-md" style={{ width: `${profile.confidence}%` }} />
              </div>
            </div>
          </div>

          {/* Schedule Changes / Anomalies */}
          <div className="glass-card overflow-hidden">
            <div className="px-6 py-4 border-b border-border/60 text-xs font-bold text-foreground uppercase tracking-wider font-display bg-white/40">
              Detected Anomalies & Pauses
            </div>
            <div className="divide-y divide-border/60">
              {ANOMALIES.map((a) => {
                const c = 
                  a.type === "Family Travel"
                    ? COLOR_PALETTE.orange
                    : COLOR_PALETTE.blue;
                return (
                  <div key={a.type} className="px-6 py-4.5 flex flex-col sm:flex-row sm:items-start gap-4">
                    <div 
                      className="pill shrink-0 self-start font-semibold font-display flex items-center justify-center gap-1.5 h-8 px-3 rounded-md border"
                      style={{ backgroundColor: c.bg, borderColor: c.border, color: c.text }}
                    >
                      {a.type === "Family Travel" ? <Map className="h-3.5 w-3.5" /> : <Users className="h-3.5 w-3.5" />}
                      <span>{a.type}</span>
                    </div>
                    <div className="flex flex-col gap-0.5 justify-center">
                      <div className="text-[10px] text-muted font-bold tracking-wider font-display uppercase">{a.date}</div>
                      <div className="text-xs text-foreground/80 leading-relaxed font-medium mt-0.5">{a.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="px-6 py-4 bg-neutral-50/20 border-t border-border/60 text-[10px] text-muted font-bold uppercase tracking-wider leading-relaxed">
              * One-time event spikes are automatically ignored to keep standard predictions accurate.
            </div>
          </div>

        </div>

        {/* System Summary Metrics & History (Right, col-span-4) */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
          
          {/* System Metrics */}
          <div className="glass-card p-6 flex flex-col gap-4">
            <span className="font-extrabold text-xs text-foreground font-display uppercase tracking-wider">Metrics Overview</span>
            <div className="flex flex-col gap-4">
              {[
                { value: profile.ordersAnalyzed,      label: "Orders Checked", icon: History },
                { value: profile.itemsModeled,         label: "Items Tracked", icon: Layers },
                { value: profile.monthsTracked + " mo", label: "Months Active", icon: Calendar },
                { value: profile.stockoutsPrevented,   label: "Stockouts Prevented", icon: ShieldCheck },
              ].map((s) => {
                const Icon = s.icon;
                const c = 
                  s.label.includes("Checked") ? COLOR_PALETTE.blue :
                  s.label.includes("Prevented") ? COLOR_PALETTE.green :
                  s.label.includes("Active") ? COLOR_PALETTE.orange :
                  COLOR_PALETTE.gray;
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
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="border-t border-border/40 pt-3.5 text-[9px] text-muted/80 font-bold uppercase tracking-wider flex justify-between font-display">
              <span>Active Since {profile.trackedSince}</span>
              <span className="text-ok">Accuracy {profile.accuracy}</span>
            </div>
          </div>

          {/* Key Buying History Rates */}
          <div className="glass-card p-6 flex flex-col gap-4">
            <span className="font-extrabold text-xs text-foreground font-display uppercase tracking-wider">Daily Consumption Rates</span>
            <div className="flex flex-col gap-4.5">
              {consumption.map((item) => (
                <div key={item.id} className="flex flex-col gap-1.5">
                  <div className="flex items-baseline justify-between text-xs">
                    <span className="font-extrabold text-foreground font-display text-[11px]">{item.label}</span>
                    <span className="text-[10px] text-muted font-semibold">{item.rate}</span>
                  </div>
                  <div className="conf-track h-1 bg-neutral-200/50 rounded-md flex items-center justify-between">
                    <div className="conf-fill h-full bg-accent rounded-md" style={{ width: `${item.conf}%` }} />
                  </div>
                  <div className="flex justify-end">
                    <span className="text-[8px] text-accent/80 font-bold tracking-wider uppercase font-display">{certaintyLabel(item.conf)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>

      </div>

    </div>
  );
}
