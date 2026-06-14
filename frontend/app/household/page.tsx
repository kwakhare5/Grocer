'use client';
/* ─────────────────────────────────────────────────────────
   Household Profile — Demo Scene 1 (hydrated)
   Shows: composition inference, key consumption rates,
   system health, and detected anomalies.
   The "wow" moment: seeing that the AI knows you're a
   family of 4 just from grocery order patterns.
 ───────────────────────────────────────────────────────── */
import { useEffect, useState } from 'react';
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
  accuracy:    "±1.4 days",
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
    type:  "TRAVEL_GAP",
    color: "text-amber-500",
    bg:    "bg-amber-500/10",
    date:  "March 15 – 24, 2026",
    desc:  "9-day order gap detected. Predictions paused for this window.",
  },
  {
    type:  "GUEST_SPIKE",
    color: "text-blue-500",
    bg:    "bg-blue-500/10",
    date:  "February 8, 2026",
    desc:  "3× milk consumption spike. Event excluded from baseline model.",
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
    return `${Math.round(rate * 1000)} ml/day`;
  }
  if (lowerName.includes("milk")) {
    return `${rate.toFixed(1)} L/day`;
  }
  if (lowerName.includes("atta") || lowerName.includes("rice") || lowerName.includes("salt") || lowerName.includes("butter")) {
    if (rate < 1.0) {
      return `${Math.round(rate * 1000)} g/day`;
    }
    return `${rate.toFixed(2)} kg/day`;
  }
  if (lowerName.includes("eggs")) {
    return `${rate.toFixed(1)} pcs/day`;
  }
  return `${rate.toFixed(2)} units/day`;
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
    <div className="flex flex-col gap-12">

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-3">
        <div className="font-data text-accent text-[10px] tracking-widest uppercase">
          M-01 · Household Profile {loading && "(LOADING...)"}
        </div>
        <h1 className="text-5xl font-light tracking-tight uppercase leading-none">
          Profile<br />
          <span className="font-black">Dossier</span>
        </h1>
        <p className="font-data text-sm text-muted max-w-lg">
          Household composition inferred from consumption patterns.
          No forms filled. No data entered. The AI figured it out.
        </p>
      </div>

      {/* ── Composition Banner ──────────────────────────────── */}
      <div className="card p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
        <div className="flex flex-col gap-2">
          <div className="font-data text-[10px] text-muted tracking-widest uppercase">
            Inferred Household Type
          </div>
          <div className="text-4xl font-black tracking-tight">{profile.type}</div>
          <div className="font-data text-xs text-muted">
            Based on: milk · atta · oil · eggs baseline consumption rates.
          </div>
        </div>
        <div className="flex flex-col items-start sm:items-end gap-2 shrink-0">
          <div className="stat-value text-accent">{profile.confidence}%</div>
          <div className="stat-label">Confidence</div>
          <div className="conf-track w-32">
            <div className="conf-fill" style={{ width: `${profile.confidence}%` }} />
          </div>
        </div>
      </div>

      {/* ── Two-column: System Metrics + Consumption ────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-border">

        {/* System Metrics */}
        <div className="card p-6 flex flex-col gap-6">
          <div className="font-data text-[10px] text-muted uppercase tracking-widest border-b border-border pb-3">
            System Metrics
          </div>
          <div className="grid grid-cols-2 gap-6">
            {[
              { value: profile.ordersAnalyzed,      label: "Orders Analysed" },
              { value: profile.itemsModeled,         label: "Items Modeled" },
              { value: profile.monthsTracked + "mo", label: "Data Depth" },
              { value: profile.stockoutsPrevented,   label: "Stockouts Prevented" },
            ].map((s) => (
              <div key={s.label} className="stat-block">
                <div className="stat-value">{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </div>
          <div className="border-t border-border pt-4 font-data text-xs text-muted flex justify-between">
            <span>Tracking since {profile.trackedSince}</span>
            <span className="text-ok">Accuracy {profile.accuracy}</span>
          </div>
        </div>

        {/* Key Consumption Rates */}
        <div className="card p-6 flex flex-col gap-6">
          <div className="font-data text-[10px] text-muted uppercase tracking-widest border-b border-border pb-3">
            Modeled Consumption Rates
          </div>
          <div className="flex flex-col gap-5">
            {consumption.map((item) => (
              <div key={item.id} className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">{item.label}</span>
                  <div className="flex items-center gap-3">
                    <span className="font-data text-xs text-muted">{item.rate}</span>
                    <span className="font-data text-xs text-accent">{item.conf}%</span>
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
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-border font-data text-[10px] text-muted uppercase tracking-widest">
          Anomalies Detected &amp; Filtered
        </div>
        <div className="divide-y divide-border">
          {ANOMALIES.map((a) => (
            <div key={a.type} className="px-6 py-5 flex flex-col sm:flex-row sm:items-start gap-4">
              <div className={`pill ${a.bg} ${a.color} shrink-0 self-start`}>
                {a.type}
              </div>
              <div className="flex flex-col gap-1">
                <div className="font-data text-xs text-muted">{a.date}</div>
                <div className="text-sm text-foreground/80">{a.desc}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="px-6 py-3 bg-surface border-t border-border font-data text-[11px] text-muted">
          Anomalies are excluded from consumption models to preserve accuracy.
          Travel gaps pause predictions; guest spikes are excluded from baseline.
        </div>
      </div>

    </div>
  );
}
