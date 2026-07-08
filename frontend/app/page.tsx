"use client";

import { useEffect, useState, useRef } from "react";
import Link from 'next/link';
import useSWR from "swr";
import { predictionsApi, householdApi, APIPrediction } from "../lib/api";
import { Package, ShieldCheck, Zap, Sparkles, ShoppingCart, Calendar, Bell, BellOff, ArrowRight } from "lucide-react";


interface DepletingItem {
  id: string;
  name: string;
  days: number;
  rawDays: number;
  fillPct: number;
  conf: number;
  avg: string;
  cycle: string;
}


const STATS = [
  { value: "34",     label: "Groceries Monitored",   sub: "Automatically tracked" },
  { value: "98%",    label: "Accuracy",              sub: "Based on your habits" },
  { value: "12",     label: "Stockouts Avoided",      sub: "Saved from running out" },
  { value: "High",   label: "Smart Helper",           sub: "Covering your main items" },
];

const FALLBACK_DEPLETING: DepletingItem[] = [
  { id: "fallback-milk", name: "Amul Taza Milk 1L",         days: 1, rawDays: 1, fillPct: 30, conf: 76, avg: "0.48L/day",  cycle: "1.8d" },
  { id: "fallback-tomatoes", name: "Tomatoes (500g)",       days: 1, rawDays: 1, fillPct: 14, conf: 78, avg: "140g/day",   cycle: "3.1d" },
  { id: "fallback-eggs", name: "Nandini Eggs (Pack of 12)", days: 2, rawDays: 2, fillPct: 43, conf: 88, avg: "2.4/day",    cycle: "4.6d" },
  { id: "fallback-bread", name: "Britannia Whole Wheat Bread", days: 3, rawDays: 3, fillPct: 77, conf: 82, avg: "0.24/day",  cycle: "3.9d" },
  { id: "fallback-onions", name: "Onions (1kg)",            days: 5, rawDays: 5, fillPct: 53, conf: 72, avg: "130g/day",   cycle: "7.7d" },
];


function urgencyColor(days: number, fillPercent: number) {
  if (fillPercent <= 20) return { bar: "#ff5a00", text: "text-red-500",   pill: "pill-danger"  };
  if (fillPercent <= 45) return { bar: "#d97706", text: "text-amber-500", pill: "pill-warning" };
  return                        { bar: "#10b981", text: "text-emerald-500", pill: "pill-ok"      };
}

function urgencyLabel(days: number, fillPercent: number) {
  if (fillPercent <= 20) return "Out tomorrow!";
  if (fillPercent <= 45) return `Out in ${days} days`;
  return `${days} days left (${fillPercent}%)`;
}

function certaintyLabel(conf: number) {
  if (conf >= 85) return "Very sure";
  if (conf >= 70) return "Pretty sure";
  return "Guessing";
}

function formatAvg(avg: string) {
  return `Uses ${avg.replace("/day", " per day")}`;
}

function formatCycle(cycle: string) {
  const d = parseFloat(cycle);
  if (isNaN(d)) return `Bought every ${cycle}`;
  if (d <= 2.5) return "Bought every 2 days";
  if (d >= 6 && d <= 7.5) return "Bought weekly";
  if (d >= 13 && d <= 16) return "Bought every 2 weeks";
  if (d >= 25 && d <= 30) return "Bought monthly";
  return `Bought every ${Math.round(d)} days`;
}



function ConfettiEffect({ active }: { active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!active) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    
    // Set canvas dimensions
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const colors = ["#ff5a00", "#ff8a00", "#10b981", "#3b82f6", "#f59e0b", "#ec4899"];
    
    interface Particle {
      x: number;
      y: number;
      r: number;
      d: number;
      color: string;
      tilt: number;
      tiltAngleIncremental: number;
      tiltAngle: number;
    }

    const particles: Particle[] = [];
    const maxParticles = 120;

    for (let i = 0; i < maxParticles; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height - canvas.height,
        r: Math.random() * 6 + 4,
        d: Math.random() * maxParticles + 10,
        color: colors[Math.floor(Math.random() * colors.length)],
        tilt: Math.random() * 10 - 5,
        tiltAngleIncremental: Math.random() * 0.07 + 0.02,
        tiltAngle: 0
      });
    }

    let angle = 0;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (let i = 0; i < maxParticles; i++) {
        const p = particles[i];
        ctx.beginPath();
        ctx.lineWidth = p.r;
        ctx.strokeStyle = p.color;
        ctx.moveTo(p.x + p.tilt + p.r / 2, p.y);
        ctx.lineTo(p.x + p.tilt, p.y + p.tilt + p.r / 2);
        ctx.stroke();
      }

      // Update positions
      angle += 0.01;
      for (let i = 0; i < maxParticles; i++) {
        const p = particles[i];
        p.y += (Math.cos(angle + p.d) + 1 + p.r / 2) / 2;
        p.x += Math.sin(angle);
        p.tiltAngle += p.tiltAngleIncremental;
        p.tilt = Math.sin(p.tiltAngle - i / 3) * 15;

        // If particle reaches bottom, recycle it to top
        if (p.y > canvas.height) {
          p.x = Math.random() * canvas.width;
          p.y = -20;
          p.tilt = Math.random() * 10 - 5;
        }
      }

      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    const handleResize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", handleResize);
    };
  }, [active]);

  if (!active) return null;

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none z-50"
    />
  );
}

const fetcher = (userId: string) => predictionsApi.getForHousehold(userId).then(res => res.data);

export default function Home() {
  // Interactive Local UI states
  const [addedItems, setAddedItems] = useState<Set<string>>(new Set());
  const [pinnedItems, setPinnedItems] = useState<Set<string>>(new Set());
  const [snoozedItems, setSnoozedItems] = useState<Set<string>>(new Set());
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const [showConfetti, setShowConfetti] = useState(false);
  const [refilledItems, setRefilledItems] = useState<Set<string>>(new Set());
  
  const [activeScenario, setActiveScenario] = useState("standard");
  const [switchingScenario, setSwitchingScenario] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);

  // Hoisted Toast handler
  function triggerToast(msg: string) {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 3000);
  }

  const { data: predictionsData, mutate: mutatePredictions, isLoading: predictionsLoading } = useSWR(
    "demo_user_001",
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000,
    }
  );

  // Listen to refresh-dashboard event to trigger revalidation of predictions
  useEffect(() => {
    const handleRefresh = () => {
      mutatePredictions();
    };
    window.addEventListener("refresh-dashboard", handleRefresh);
    return () => window.removeEventListener("refresh-dashboard", handleRefresh);
  }, [mutatePredictions]);

  const loading = predictionsLoading || switchingScenario;

  const depleting = predictionsData?.predictions && predictionsData.predictions.length > 0
    ? predictionsData.predictions.map((p: APIPrediction) => ({
        id: p.item_id,
        name: p.item_name,
        days: p.days_remaining !== null ? Math.round(p.days_remaining) : 10,
        rawDays: p.days_remaining !== null ? p.days_remaining : 10,
        fillPct: p.stock_fill_percent !== undefined ? Math.round(p.stock_fill_percent) : 100,
        conf: Math.round((p.confidence_score || 0.5) * 100),
        avg: `${p.avg_daily_consumption.toFixed(2)}/day`,
        cycle: `${p.consumption_cycle_days || 7}d`,
      }))
    : FALLBACK_DEPLETING;


  const handleScenarioChange = async (scenario: string) => {
    if (switchingScenario) return;
    setSwitchingScenario(true);
    
    // Optimistic Update
    const previousScenario = activeScenario;
    setActiveScenario(scenario);
    
    try {
      await householdApi.switchScenario("demo_user_001", scenario);
      triggerToast(`Switched to ${scenario === "standard" ? "Standard Staples" : scenario === "party" ? "Party Spike" : "Vacation Mode"}!`);
      window.dispatchEvent(new CustomEvent("scenario-switched"));
      await mutatePredictions();
    } catch (err) {
      console.warn("Failed to switch scenario", err);
      // Revert on failure
      setActiveScenario(previousScenario);
      triggerToast("⚠️ Failed to switch demo scenario.");
    } finally {
      setSwitchingScenario(false);
    }
  };

  // Listen to order-placed event to trigger confetti and shelf replenish animation
  useEffect(() => {
    const handleOrderPlaced = () => {
      setShowConfetti(true);
      setTimeout(() => setShowConfetti(false), 5000); // confetti runs for 5s

      // Visually replenish all kitchen shelf jars back to full (95%)
      const allNames = depleting.map(i => i.name);
      setRefilledItems(new Set(allNames));
      
      // Keep shelf visuals refilled for 12 seconds
      setTimeout(() => {
        setRefilledItems(new Set());
      }, 12000);

      triggerToast("🎉 PreFill Order Confirmed!");
    };

    window.addEventListener("order-placed", handleOrderPlaced);
    return () => window.removeEventListener("order-placed", handleOrderPlaced);
  }, [depleting]);





  // Caching predictions are handled via SWR hook mutates

  const handleAddToCart = (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setAddedItems((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
        triggerToast(`Removed ${name.split(" — ")[0]} from Cart`);
      } else {
        next.add(name);
        triggerToast(`Added ${name.split(" — ")[0]} to your PreFill Cart!`);
      }
      return next;
    });
  };

  const handlePinToSunday = (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setPinnedItems((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
        triggerToast(`Removed ${name.split(" — ")[0]} from Sunday Meal Plan`);
      } else {
        next.add(name);
        triggerToast(`Pinned ${name.split(" — ")[0]} to Sunday Meal Plan checklist`);
      }
      return next;
    });
  };

  const handleSnoozeAlert = (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setSnoozedItems((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
        triggerToast(`Restored alerts for ${name.split(" — ")[0]}`);
      } else {
        next.add(name);
        triggerToast(`Paused refilling reminders for ${name.split(" — ")[0]} (snoozed)`);
      }
      return next;
    });
  };

  const STATS_ICONS = [
    <Package key="package" className="h-5 w-5 text-accent/80" />,
    <ShieldCheck key="shield" className="h-5 w-5 text-accent/80" />,
    <Zap key="zap" className="h-5 w-5 text-accent/80" />,
    <Sparkles key="sparkles" className="h-5 w-5 text-accent/80" />
  ];

  return (
    <div className="flex flex-col gap-10 relative">
      <ConfettiEffect active={showConfetti} />
      
      {/* Ambient decorative blobs for premium editorial depth */}
      <div className="absolute top-[-50px] right-[-100px] w-[250px] h-[250px] bg-accent/8 blur-[100px] pointer-events-none -z-10" />

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-2.5">
        <div className="text-accent text-[11px] font-bold tracking-widest uppercase font-display">
          PreFill Assistant {loading && "(LOADING...)"}
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight leading-tight font-display text-foreground">
          My Kitchen <span className="text-accent">Pantry Checker</span>
        </h1>
        <p className="text-sm text-muted max-w-lg leading-relaxed font-medium">
          Shows when your groceries are running out. Tap to add to your cart, save for Sunday recipes, or change settings.
        </p>
      </div>

      {/* ── Demo Scenario Switcher Panel ─────────────────────── */}
      <div className="glass-card rounded-2xl overflow-hidden border border-border/70 shadow-sm transition-all duration-300">
        <button
          onClick={() => setPanelOpen(!panelOpen)}
          className="w-full px-6 py-4 flex items-center justify-between text-xs font-bold text-accent uppercase tracking-wider font-display bg-neutral-50/50 dark:bg-neutral-900/30 hover:bg-neutral-50 dark:hover:bg-neutral-900/50 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <Sparkles className="h-4.5 w-4.5 animate-pulse" />
            <span>PreFill Reviewer Demo Settings</span>
          </div>
          <span className="text-[10px] text-muted font-bold tracking-normal font-sans">
            {panelOpen ? "Collapse ▴" : "Expand scenario tools ▾"}
          </span>
        </button>
        
        {panelOpen && (
          <div className="p-6 bg-white dark:bg-[#121110] border-t border-border/50 animate-in fade-in slide-in-from-top-2 duration-300 flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <span className="font-extrabold text-xs text-foreground font-display uppercase tracking-wide">Choose a Scenario to Demo</span>
              <p className="text-[11px] leading-relaxed text-muted font-medium">
                {"Switch scenarios to see how the assistant adapts to different situations, like a normal week, holiday vacation, or weekend party."}
              </p>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <button
                disabled={switchingScenario}
                onClick={() => handleScenarioChange("standard")}
                className={`flex flex-col gap-1.5 p-4 rounded-xl border text-left cursor-pointer transition-all duration-300 ${
                  activeScenario === "standard"
                    ? "bg-accent/5 border-accent text-accent shadow-md shadow-accent/5 animate-in fade-in"
                    : "bg-white dark:bg-[#1c1a18] border-border hover:border-muted text-foreground"
                } disabled:opacity-50`}
              >
                <span className="font-extrabold text-xs font-display">🌾 Regular Week</span>
                <span className="text-[10px] leading-normal text-muted font-medium">Normal family routine with regular shopping patterns.</span>
              </button>

              <button
                disabled={switchingScenario}
                onClick={() => handleScenarioChange("party")}
                className={`flex flex-col gap-1.5 p-4 rounded-xl border text-left cursor-pointer transition-all duration-300 ${
                  activeScenario === "party"
                    ? "bg-accent/5 border-accent text-accent shadow-md shadow-accent/5 animate-in fade-in"
                    : "bg-white dark:bg-[#1c1a18] border-border hover:border-muted text-foreground"
                } disabled:opacity-50`}
              >
                <span className="font-extrabold text-xs font-display">🥛 Weekend Party</span>
                <span className="text-[10px] leading-normal text-muted font-medium">Family buys extra milk, butter, and cream for hosting guests, causing stock to run out quickly.</span>
              </button>

              <button
                disabled={switchingScenario}
                onClick={() => handleScenarioChange("vacation")}
                className={`flex flex-col gap-1.5 p-4 rounded-xl border text-left cursor-pointer transition-all duration-300 ${
                  activeScenario === "vacation"
                    ? "bg-accent/5 border-accent text-accent shadow-md shadow-accent/5 animate-in fade-in"
                    : "bg-white dark:bg-[#1c1a18] border-border hover:border-muted text-foreground"
                } disabled:opacity-50`}
              >
                <span className="font-extrabold text-xs font-display">✈️ On Vacation</span>
                <span className="text-[10px] leading-normal text-muted font-medium">Family travels, meaning no groceries are used and everything stays full.</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── 4 Stat Blocks ───────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STATS.map((s, idx) => (
          <div key={s.label} className="glass-card p-6 rounded-2xl flex flex-col gap-3.5 card-transition">
            <div className="flex items-center justify-between">
              <div className="stat-value text-accent font-display">{s.value}</div>
              {STATS_ICONS[idx]}
            </div>
            <div className="flex flex-col gap-0.5">
              <div className="text-xs font-bold text-foreground tracking-wide font-display">{s.label}</div>
              <div className="text-[11px] text-muted font-medium leading-normal">{s.sub}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Virtual Pantry Shelf (Visual Anchor) ──────────────── */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="text-xs font-bold text-muted uppercase tracking-wider font-display">
            Virtual Kitchen Shelf
          </div>
          <span className="text-[11px] text-muted font-semibold hidden sm:inline">
            Jars show how much is left in your kitchen
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="relative w-full h-48 rounded-2xl glass-card animate-pulse border border-border/10 p-4 flex flex-col justify-between bg-neutral-100/50 dark:bg-neutral-900/30">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-12 h-2 bg-neutral-300/40 dark:bg-neutral-800/40 rounded-b-md" />
                <div className="flex flex-col gap-2">
                  <div className="h-3 w-12 bg-neutral-300/30 dark:bg-neutral-800/30 rounded" />
                  <div className="h-4 w-24 bg-neutral-300/30 dark:bg-neutral-800/30 rounded" />
                </div>
                <div className="h-8 w-8 bg-neutral-300/30 dark:bg-neutral-800/30 rounded" />
                <div className="h-3 w-16 bg-neutral-300/30 dark:bg-neutral-800/30 rounded" />
              </div>
            ))
          ) : depleting.length === 0 ? (
            <div className="col-span-full py-8 text-center text-xs text-muted font-bold font-display uppercase tracking-widest">
              All groceries are stocked up! 👍
            </div>
          ) : (
            [...depleting]
              .map((item) => {
                const isRefilled = refilledItems.has(item.name);
                const fillPercent = isRefilled ? 95 : Math.max(0, item.fillPct);
                return { ...item, fillPercent, isRefilled };
              })
              .sort((a, b) => a.fillPercent - b.fillPercent)
              .slice(0, 5)
              .map((item, idx) => {
                const isAdded = addedItems.has(item.name);
                const fp = item.fillPercent;
                const colors = fp <= 20
                  ? {
                      frontStart: "rgba(254, 205, 211, 0.95)",
                      frontMid: "rgba(239, 68, 68, 0.8)",
                      frontEnd: "rgba(159, 18, 57, 0.95)",
                      backStart: "rgba(239, 68, 68, 0.5)",
                      backEnd: "rgba(136, 19, 55, 0.75)",
                    }
                  : fp <= 45
                  ? {
                      frontStart: "rgba(253, 230, 138, 0.95)",
                      frontMid: "rgba(245, 158, 11, 0.8)",
                      frontEnd: "rgba(180, 83, 9, 0.95)",
                      backStart: "rgba(245, 158, 11, 0.5)",
                      backEnd: "rgba(146, 64, 14, 0.75)",
                    }
                  : {
                      frontStart: "rgba(167, 243, 208, 0.95)",
                      frontMid: "rgba(16, 185, 129, 0.75)",
                      frontEnd: "rgba(4, 120, 87, 0.95)",
                      backStart: "rgba(16, 185, 129, 0.45)",
                      backEnd: "rgba(6, 95, 70, 0.75)",
                    };
                const waveDelay = `${idx * -1.2}s`; // Negative delay offsets start times so waves are out of phase immediately

                return (
                  <div
                    key={item.id || item.name}
                    className="relative w-full h-48 rounded-2xl glass-card overflow-hidden group hover:border-accent hover:shadow-[0_8px_30px_rgba(255,90,0,0.08)] transition-all duration-300 flex flex-col justify-between p-4 cursor-pointer"
                    onClick={(e) => handleAddToCart(item.name, e)}
                  >
                    {/* Jar Lid */}
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-14 h-2.5 bg-gradient-to-b from-neutral-300 to-neutral-400 dark:from-neutral-600 dark:to-neutral-700 rounded-b-lg z-20 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:scale-x-105 shadow-sm" />

                    {/* Liquid body */}
                    <div
                      className="absolute bottom-0 left-0 w-full z-10 transition-all duration-1000 ease-out liquid-fill-animate"
                      style={{ height: `${fp}%` }}
                    >
                      {/* Animated SVG wave & body (Seamless, no horizontal seam line, horizontally scrolling repeating waves) */}
                      <svg
                        viewBox="0 0 400 100"
                        preserveAspectRatio="none"
                        className="absolute top-0 left-0 w-[200%] h-full overflow-visible"
                      >
                        <defs>
                          <linearGradient id={`grad-back-${idx}`} x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop offset="0%" stopColor={colors.backStart} />
                            <stop offset="100%" stopColor={colors.backEnd} />
                          </linearGradient>
                          <linearGradient id={`grad-front-${idx}`} x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop offset="0%" stopColor={colors.frontStart} />
                            <stop offset="12%" stopColor={colors.frontMid} />
                            <stop offset="100%" stopColor={colors.frontEnd} />
                          </linearGradient>
                        </defs>
                        {/* Back Wave Layer */}
                        <path
                          d="M 0,25 Q 50,33 100,25 Q 150,17 200,25 Q 250,33 300,25 Q 350,17 400,25 L 400,100 L 0,100 Z"
                          fill={`url(#grad-back-${idx})`}
                          className="wave-back-animate"
                          style={{ animationDelay: waveDelay }}
                        />
                        {/* Front Wave Layer */}
                        <path
                          d="M 0,20 Q 50,12 100,20 Q 150,28 200,20 Q 250,12 300,20 Q 350,28 400,20 L 400,100 L 0,100 Z"
                          fill={`url(#grad-front-${idx})`}
                          className="wave-front-animate"
                          style={{ animationDelay: waveDelay }}
                        />
                      </svg>
                    </div>

                    {/* Content */}
                    <div className="relative z-20 flex flex-col h-full justify-between pointer-events-none">
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[10px] uppercase font-bold text-foreground/75 font-display tracking-wider jar-text-glow-muted">
                          {item.name.toLowerCase().includes("milk") ? "Dairy" :
                           item.name.toLowerCase().includes("oil") ? "Oils" :
                           item.name.toLowerCase().includes("egg") ? "Proteins" : "Staple"}
                        </span>
                        <span className="font-extrabold text-xs text-foreground tracking-tight line-clamp-2 leading-tight font-display jar-text-glow">
                          {item.name.split(" — ")[0]}
                        </span>
                      </div>
                      <div className="flex flex-col items-start my-auto">
                        <span className="text-2xl font-black text-foreground font-display leading-none jar-text-glow">
                          {item.isRefilled ? "✓" : item.days}
                        </span>
                        <span className="text-[10px] font-bold text-foreground/80 uppercase tracking-wider font-display mt-0.5 jar-text-glow-muted">
                          {item.isRefilled ? "Refilled" : item.days === 1 ? "day left" : "days left"}
                        </span>
                      </div>
                      <div className="text-[9px] font-bold text-foreground/80 uppercase tracking-widest font-display jar-text-glow-muted">
                        {item.isRefilled ? "95% full" : `${fp}% full`}
                      </div>
                    </div>

                    {/* Add-to-cart button */}
                    <button
                      onClick={(e) => { e.stopPropagation(); handleAddToCart(item.name, e); }}
                      className={`absolute bottom-3 right-3 w-11 h-11 rounded-full flex items-center justify-center transition-all duration-300 z-30 cursor-pointer shadow-md border ${
                        isAdded
                          ? "bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-500"
                          : "bg-white/90 dark:bg-neutral-800 text-muted hover:text-accent hover:border-accent border-border"
                      }`}
                      aria-label={`Add ${item.name} to cart`}
                    >
                      <ShoppingCart className="h-4.5 w-4.5" />
                    </button>
                  </div>
                );
              })
          )}
        </div>
      </div>

      {/* ── Live Depletion Timeline ─────────────────────────── */}
      <div className="glass-card overflow-hidden rounded-2xl shadow-sm border border-border/80">
        <div className="px-6 py-4.5 border-b border-border/60 flex items-center justify-between bg-white/40 dark:bg-neutral-900/20">
          <div className="flex items-center gap-3">
            <div className="dot-pulse" />
            <span className="text-xs font-bold uppercase tracking-wider text-foreground font-display">Running Out Soon</span>
          </div>
          <Link href="/predictions" className="text-xs font-bold text-accent hover:text-accent/85 hover:underline transition-colors flex items-center gap-1">
            View Full List <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        <div className="divide-y divide-border/60">
          {loading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="px-6 py-6 animate-pulse flex flex-col gap-4">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <div className="h-6 w-20 bg-neutral-300/30 dark:bg-neutral-800/30 rounded-full" />
                    <div className="h-4 w-40 bg-neutral-300/30 dark:bg-neutral-800/30 rounded" />
                  </div>
                  <div className="h-4 w-28 bg-neutral-300/30 dark:bg-neutral-800/30 rounded" />
                </div>
                <div className="h-1.5 w-full bg-neutral-300/20 dark:bg-neutral-800/20 rounded-full" />
                <div className="flex justify-between items-center">
                  <div className="h-4 w-32 bg-neutral-300/30 dark:bg-neutral-800/30 rounded" />
                  <div className="flex gap-2">
                    <div className="h-9 w-24 bg-neutral-300/30 dark:bg-neutral-800/30 rounded-full" />
                    <div className="h-9 w-24 bg-neutral-300/30 dark:bg-neutral-800/30 rounded-full" />
                  </div>
                </div>
              </div>
            ))
          ) : depleting.length === 0 ? (
            <div className="py-10 text-center text-xs text-muted font-bold font-display uppercase tracking-widest">
              No items running out soon.
            </div>
          ) : (
            [...depleting]
              .map((item) => {
                const isRefilled = refilledItems.has(item.name);
                const fillPct = isRefilled ? 95 : Math.max(0, item.fillPct);
                return { ...item, fillPct, isRefilled };
              })
              .sort((a, b) => a.fillPct - b.fillPct)
              .map((item) => {
                const u = item.isRefilled
                  ? { bar: "#10b981", text: "text-emerald-500", pill: "pill-ok" }
                  : urgencyColor(item.days, item.fillPct);
                const label = item.isRefilled ? "Refilled" : urgencyLabel(item.days, item.fillPct);

                const isAdded = addedItems.has(item.name);
                const isPinned = pinnedItems.has(item.name);
                const isSnoozed = snoozedItems.has(item.name);

                return (
                  <div
                    key={item.id || item.name}
                    className={`group px-6 py-5.5 flex flex-col gap-4 hover:bg-white/40 dark:hover:bg-neutral-900/10 transition-all ${
                      isSnoozed ? "opacity-35" : ""
                    }`}
                  >
                    {/* Top row */}
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className={`pill ${u.pill} font-semibold font-display`}>
                          {label}
                        </span>
                        <span className="font-extrabold text-sm tracking-wide text-foreground font-display truncate">
                          {item.name}
                        </span>
                      </div>
                      <div className="text-xs text-muted/80 shrink-0 font-semibold font-display">
                        {certaintyLabel(item.conf)}
                      </div>
                    </div>

                    {/* Depletion bar */}
                    <div className="depletion-bar rounded-full h-1.5 bg-neutral-200/50 dark:bg-neutral-800/40">
                      <div
                        className="depletion-bar-fill rounded-full"
                        style={{
                          width: `${item.fillPct}%`,
                          background: isSnoozed
                            ? "#9ca3af"
                            : (item.isRefilled || item.fillPct > 45)
                            ? "linear-gradient(90deg, var(--ok) 0%, #059669 100%)"
                            : item.fillPct <= 20
                            ? "linear-gradient(90deg, var(--danger) 0%, #be123c 100%)"
                            : "linear-gradient(90deg, var(--warning) 0%, #b45309 100%)"
                        }}
                      />
                    </div>

                    {/* Bottom stats & Quick Actions */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-0.5">
                      <div className="text-xs text-muted/90 flex gap-4 font-medium">
                        <span>{formatAvg(item.avg)}</span>
                        <span className="text-border">|</span>
                        <span>{formatCycle(item.cycle)}</span>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <button
                          disabled={item.isRefilled}
                          onClick={(e) => handleAddToCart(item.name, e)}
                          className={`h-11 px-4.5 rounded-full text-xs font-bold tracking-wide transition-all duration-200 flex items-center justify-center gap-1.5 active:scale-[0.98] ${
                            item.isRefilled
                              ? "bg-emerald-100 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900/50 cursor-not-allowed opacity-90"
                              : isAdded
                              ? "bg-emerald-600 text-white hover:bg-emerald-700 cursor-pointer"
                              : "bg-accent text-white hover:bg-accent/90 cursor-pointer"
                          }`}
                        >
                          {item.isRefilled ? (
                            <>
                              <ShieldCheck className="h-4 w-4" />
                              Stocked
                            </>
                          ) : (
                            <>
                              <ShoppingCart className="h-4 w-4" />
                              {isAdded ? "Added to Cart" : "Add to Cart"}
                            </>
                          )}
                        </button>
                        <button
                          onClick={(e) => handlePinToSunday(item.name, e)}
                          className={`h-11 px-4.5 rounded-full text-xs font-bold border transition-all duration-200 flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.98] ${
                            isPinned
                              ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-200"
                              : "bg-white/80 dark:bg-neutral-800 text-muted hover:text-foreground border-border hover:border-muted-foreground"
                          }`}
                        >
                          <Calendar className="h-4 w-4" />
                          {isPinned ? "Pinned to Sunday" : "Pin to Sunday"}
                        </button>
                        <button
                          onClick={(e) => handleSnoozeAlert(item.name, e)}
                          className={`h-11 px-4.5 rounded-full text-xs font-bold border transition-all duration-200 flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.98] ${
                            isSnoozed
                              ? "bg-neutral-800 text-neutral-200 border-neutral-700"
                              : "bg-white/80 dark:bg-neutral-800 text-muted hover:text-red-500 border-border hover:border-red-200"
                          }`}
                        >
                          {isSnoozed ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
                          {isSnoozed ? "Unpause Alerts" : "Pause Alerts"}
                        </button>
                      </div>
                    </div>
                </div>
              );
            })
          )}
        </div>
      </div>
      {/* ── Toast Notification ─────────────────────────────── */}
      {toastMessage && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 bg-neutral-900/95 dark:bg-neutral-100/95 backdrop-blur-md text-white dark:text-neutral-900 px-5 py-3 rounded-full shadow-[0_12px_40px_rgba(0,0,0,0.25)] flex items-center gap-2 border border-neutral-800 dark:border-neutral-200 animate-in fade-in slide-in-from-bottom-4 duration-300">
          <span className="text-xs font-bold tracking-wide font-display">{toastMessage}</span>
        </div>
      )}



    </div>
  );
}

