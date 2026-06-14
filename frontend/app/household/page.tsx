/* ─────────────────────────────────────────────────────────
   Household Profile — Demo Scene 1 (detail)
   Shows: composition inference, key consumption rates,
   system health, and detected anomalies.
   The "wow" moment: seeing that the AI knows you're a
   family of 4 just from grocery order patterns.
───────────────────────────────────────────────────────── */

const PROFILE = {
  type:        "Family (3–4 members)",
  confidence:  84,
  trackedSince: "January 2026",
  monthsTracked: 4,
  itemsModeled: 34,
  accuracy:    "±1.4 days",
  ordersAnalyzed: 87,
  stockoutsPrevented: 12,
};

const CONSUMPTION = [
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

export default function HouseholdPage() {
  return (
    <div className="flex flex-col gap-12">

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-3">
        <div className="font-data text-accent text-[10px] tracking-widest uppercase">
          M-01 · Household Profile
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
          <div className="text-4xl font-black tracking-tight">{PROFILE.type}</div>
          <div className="font-data text-xs text-muted">
            Based on: milk (1.1L/d) · atta (280g/d) · eggs (2.3/d)
          </div>
        </div>
        <div className="flex flex-col items-start sm:items-end gap-2 shrink-0">
          <div className="stat-value text-accent">{PROFILE.confidence}%</div>
          <div className="stat-label">Confidence</div>
          <div className="conf-track w-32">
            <div className="conf-fill" style={{ width: `${PROFILE.confidence}%` }} />
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
              { value: PROFILE.ordersAnalyzed,      label: "Orders Analysed" },
              { value: PROFILE.itemsModeled,         label: "Items Modeled" },
              { value: PROFILE.monthsTracked + "mo", label: "Data Depth" },
              { value: PROFILE.stockoutsPrevented,   label: "Stockouts Prevented" },
            ].map((s) => (
              <div key={s.label} className="stat-block">
                <div className="stat-value">{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </div>
          <div className="border-t border-border pt-4 font-data text-xs text-muted flex justify-between">
            <span>Tracking since {PROFILE.trackedSince}</span>
            <span className="text-ok">Accuracy {PROFILE.accuracy}</span>
          </div>
        </div>

        {/* Key Consumption Rates */}
        <div className="card p-6 flex flex-col gap-6">
          <div className="font-data text-[10px] text-muted uppercase tracking-widest border-b border-border pb-3">
            Modeled Consumption Rates
          </div>
          <div className="flex flex-col gap-5">
            {CONSUMPTION.map((item) => (
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
