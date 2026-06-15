"use client";

import { useEffect, useState, useRef } from "react";
import Link from 'next/link';
import useSWR from "swr";
import { predictionsApi, householdApi, APIPrediction } from "../lib/api";
import { Package, ShieldCheck, Zap, Sparkles, ShoppingCart, Calendar, Bell, BellOff, ArrowRight, X } from "lucide-react";

interface DepletingItem {
  name: string;
  days: number;
  conf: number;
  avg: string;
  cycle: string;
  urgent: boolean;
}

const STATS = [
  { value: "34",     label: "Pantry Staples Tracked", sub: "automatic tracking active" },
  { value: "98%",    label: "Prediction Accuracy",    sub: "based on last 30 refills" },
  { value: "12",     label: "Stockouts Prevented",    sub: "automatic refills saved" },
  { value: "High",   label: "Smart Coverage",        sub: "across all kitchen essentials" },
];

const FALLBACK_DEPLETING: DepletingItem[] = [
  { name: "Amul Taza Milk 1L",        days: 2,  conf: 76, avg: "1.1L/day",  cycle: "2.1d",  urgent: false },
  { name: "Tomatoes (500g)",          days: 1,  conf: 78, avg: "150g/day",  cycle: "3d",    urgent: true  },
  { name: "Nandini Eggs (Pack of 12)", days: 2,  conf: 88, avg: "2.3/day",   cycle: "5d",    urgent: true  },
  { name: "Fortune Sunflower Oil 1L",  days: 2,  conf: 87, avg: "68ml/day",  cycle: "15d",   urgent: true  },
  { name: "Aashirvaad Atta 5kg",       days: 12, conf: 68, avg: "280g/day",  cycle: "13d",   urgent: false },
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
  if (conf >= 85) return "Very High Certainty";
  if (conf >= 70) return "High Certainty";
  return "Calculated Estimate";
}

function formatAvg(avg: string) {
  return `Uses ${avg.replace("/day", " daily")}`;
}

function formatCycle(cycle: string) {
  const d = parseFloat(cycle);
  if (isNaN(d)) return `Restocked every ${cycle}`;
  if (d <= 2.5) return "Restocked every 2 days";
  if (d >= 6 && d <= 7.5) return "Restocked weekly";
  if (d >= 13 && d <= 16) return "Restocked every 2 weeks";
  if (d >= 25 && d <= 30) return "Restocked monthly";
  return `Restocked every ${Math.round(d)} days`;
}

function barFill(days: number) {
  return Math.min(100, Math.max(4, Math.round((days / 30) * 100)));
}

function jarFluidStyle(name: string, fillPercent: number) {
  let fluidColor = "rgba(16, 185, 129, 0.4)"; // default ok green
  let border = "var(--ok)";
  
  if (fillPercent <= 20) {
    fluidColor = "rgba(225, 29, 72, 0.45)"; // urgent red (danger)
    border = "var(--danger)";
  } else if (fillPercent <= 45) {
    fluidColor = "rgba(217, 119, 6, 0.45)"; // low warning amber (warning)
    border = "var(--warning)";
  }
  
  return {
    backgroundColor: fluidColor,
    borderTop: `1px solid ${border}`
  };
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
  const [depleting, setDepleting] = useState<DepletingItem[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Interactive Local UI states
  const [addedItems, setAddedItems] = useState<Set<string>>(new Set());
  const [pinnedItems, setPinnedItems] = useState<Set<string>>(new Set());
  const [snoozedItems, setSnoozedItems] = useState<Set<string>>(new Set());
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [phoneAlert, setPhoneAlert] = useState<string | null>(null);
  const [showConfetti, setShowConfetti] = useState(false);
  const [refilledItems, setRefilledItems] = useState<Set<string>>(new Set());
  
  const [activeScenario, setActiveScenario] = useState("standard");
  const [switchingScenario, setSwitchingScenario] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);

  const { data: predictionsData, error: predictionsError, mutate: mutatePredictions } = useSWR(
    "demo_user_001",
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000,
    }
  );

  useEffect(() => {
    if (predictionsData) {
      if (predictionsData.predictions && predictionsData.predictions.length > 0) {
        const apiItems = predictionsData.predictions.map((p: APIPrediction) => ({
          name: p.item_name,
          days: p.days_remaining !== null ? Math.round(p.days_remaining) : 10,
          conf: Math.round((p.confidence_score || 0.5) * 100),
          avg: `${p.avg_daily_consumption.toFixed(2)}/day`,
          cycle: `${p.consumption_cycle_days || 7}d`,
          urgent: p.days_remaining !== null && p.days_remaining <= 3
        }));
        setDepleting(apiItems);
      } else {
        setDepleting(FALLBACK_DEPLETING);
      }
      setLoading(false);
    } else if (predictionsError) {
      setDepleting(FALLBACK_DEPLETING);
      setLoading(false);
    }
  }, [predictionsData, predictionsError]);

  const handleScenarioChange = async (scenario: string) => {
    if (switchingScenario) return;
    setSwitchingScenario(true);
    setLoading(true);
    
    // Optimistic Update
    const previousScenario = activeScenario;
    setActiveScenario(scenario);
    
    try {
      await householdApi.switchScenario("demo_user_001", scenario);
      triggerToast(`Switched to ${scenario === "standard" ? "Standard Staples" : scenario === "party" ? "Party Spike" : "Vacation Mode"}!`);
      await mutatePredictions();
    } catch (err) {
      console.warn("Failed to switch scenario", err);
      // Revert on failure
      setActiveScenario(previousScenario);
      triggerToast("⚠️ Failed to switch demo scenario.");
    } finally {
      setSwitchingScenario(false);
      setLoading(false);
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

      triggerToast("🎉 Swiggy Instamart Order Confirmed!");
    };

    window.addEventListener("order-placed", handleOrderPlaced);
    return () => window.removeEventListener("order-placed", handleOrderPlaced);
  }, [depleting]);

  // Listen to whatsapp-alert event to show smartphone push notifications
  useEffect(() => {
    const handleAlert = (e: Event) => {
      const customEvent = e as CustomEvent;
      const text = customEvent.detail?.text || "";
      if (text && (text.includes("likely running low on") || text.includes("reorder") || text.includes("ready with") || text.includes("Order placed"))) {
        let summary = text;
        if (text.includes("likely running low on") || text.includes("purchase patterns")) {
          summary = "🛒 Proactive low-stock alert! Tap to open details.";
        } else if (text.includes("ready with")) {
          summary = "🛒 Instamart cart ready! Tap to confirm order.";
        } else if (text.includes("Order placed")) {
          summary = "✅ Order placed successfully! Arriving in 15 mins.";
        } else {
          summary = "💬 New Restock update available.";
        }
        setPhoneAlert(summary);
      }
    };
    
    window.addEventListener("whatsapp-alert", handleAlert);
    return () => window.removeEventListener("whatsapp-alert", handleAlert);
  }, []);

  const handleToastClick = () => {
    window.dispatchEvent(new CustomEvent("open-whatsapp-chat"));
    setPhoneAlert(null);
  };

  // Caching predictions are handled via SWR hook mutates

  const triggerToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 3000);
  };

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
        triggerToast(`Added ${name.split(" — ")[0]} to your Instamart Cart!`);
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
    <Package className="h-5 w-5 text-accent/80" />,
    <ShieldCheck className="h-5 w-5 text-accent/80" />,
    <Zap className="h-5 w-5 text-accent/80" />,
    <Sparkles className="h-5 w-5 text-accent/80" />
  ];

  return (
    <div className="flex flex-col gap-10 relative">
      <ConfettiEffect active={showConfetti} />
      
      {/* Ambient decorative blobs for premium editorial depth */}
      <div className="absolute top-[-50px] right-[-100px] w-[250px] h-[250px] bg-accent/8 blur-[100px] pointer-events-none -z-10" />

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-2.5">
        <div className="text-accent text-[11px] font-bold tracking-widest uppercase font-display">
          Instamart Assistant {loading && "(LOADING...)"}
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight leading-tight font-display text-foreground">
          My Kitchen <span className="text-accent">Pantry Checker</span>
        </h1>
        <p className="text-sm text-muted max-w-lg leading-relaxed font-medium">
          Predicts when your staples are running low. Tap to instantly add to your Instamart checkout cart, pin to meal planner, or adjust settings.
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
            <span>Swiggy Reviewer Demo Settings</span>
          </div>
          <span className="text-[10px] text-muted font-bold tracking-normal font-sans">
            {panelOpen ? "Collapse ▴" : "Expand scenario tools ▾"}
          </span>
        </button>
        
        {panelOpen && (
          <div className="p-6 bg-white dark:bg-[#121110] border-t border-border/50 animate-in fade-in slide-in-from-top-2 duration-300 flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <span className="font-extrabold text-xs text-foreground font-display uppercase tracking-wide">Select Household Lifestyle Scenario</span>
              <p className="text-[11px] leading-relaxed text-muted font-medium">
                Changing scenarios instantly regenerates the household's order history, runs Swiggy's Prophet ML model predictions, and profiles household composition in real-time.
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
                <span className="font-extrabold text-xs font-display">🌾 Standard Staples</span>
                <span className="text-[10px] leading-normal text-muted font-medium">Standard Indian household consumption cycles and predictable restocking windows.</span>
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
                <span className="font-extrabold text-xs font-display">🥛 Weekend Party Spike</span>
                <span className="text-[10px] leading-normal text-muted font-medium">Sudden heavy consumption spike of party staples (Cream, Milk, Butter) causing instant depletion.</span>
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
                <span className="font-extrabold text-xs font-display">✈️ Vacation Mode</span>
                <span className="text-[10px] leading-normal text-muted font-medium">Household travels for a vacation. Consumption stops and predictions adjust to reflect full pantry items.</span>
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
            Visual level represents remaining stock
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
              No depletions predicted. All stocked up! 👍
            </div>
          ) : (
            [...depleting]
              .map((item) => {
                const isRefilled = refilledItems.has(item.name);
                const cycleDays = parseFloat(item.cycle) || 30;
                const fillPercent = isRefilled ? 95 : Math.max(8, Math.min(95, Math.round((item.days / cycleDays) * 100)));
                return { ...item, fillPercent, isRefilled };
              })
              .sort((a, b) => a.fillPercent - b.fillPercent)
              .slice(0, 5)
              .map((item) => {
                const isAdded = addedItems.has(item.name);
                const style = jarFluidStyle(item.name, item.fillPercent);

                return (
                  <div
                    key={item.name}
                    className="relative w-full h-48 rounded-2xl glass-card overflow-hidden group hover:border-accent hover:shadow-[0_8px_30px_rgba(255,90,0,0.06)] transition-all duration-300 flex flex-col justify-between p-4 cursor-pointer"
                    onClick={(e) => handleAddToCart(item.name, e)}
                  >
                    {/* Jar Lid detail */}
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-12 h-2 bg-neutral-300/80 dark:bg-neutral-700/80 rounded-b-md z-20 jar-lid-transition group-hover:-translate-y-0.5 group-hover:scale-x-105" />

                    {/* Liquid Fill */}
                    <div
                      className="absolute bottom-0 left-0 w-full transition-all duration-1000 ease-out z-10 liquid-fill-animate"
                      style={{
                        height: `${item.fillPercent}%`,
                        backgroundImage: "linear-gradient(180deg, rgba(255, 255, 255, 0.15) 0%, rgba(0, 0, 0, 0.15) 100%)",
                        ...style
                      }}
                    />

                    {/* Content Overlay */}
                    <div className="relative z-20 flex flex-col h-full justify-between pointer-events-none">
                      {/* Top: Name and category */}
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[10px] uppercase font-bold text-muted font-display tracking-wider">
                          {item.name.toLowerCase().includes("milk") ? "Dairy" :
                           item.name.toLowerCase().includes("oil") ? "Oils" :
                           item.name.toLowerCase().includes("egg") ? "Proteins" : "Staple"}
                        </span>
                        <span className="font-extrabold text-xs text-foreground tracking-tight line-clamp-2 leading-tight font-display">
                          {item.name.split(" — ")[0]}
                        </span>
                      </div>

                      {/* Middle: Big Countdown */}
                      <div className="flex flex-col items-start my-auto">
                        <span className="text-2xl font-black text-foreground font-display leading-none">
                          {item.isRefilled ? "✓" : item.days}
                        </span>
                        <span className="text-[10px] font-bold text-muted uppercase tracking-wider font-display mt-0.5">
                          {item.isRefilled ? "Refilled" : item.days === 1 ? "day left" : "days left"}
                        </span>
                      </div>

                      {/* Bottom Info */}
                      <div className="text-[9px] font-bold text-muted/90 uppercase tracking-widest font-display">
                        {item.isRefilled ? "95% full" : `${item.fillPercent}% full`}
                      </div>
                    </div>

                    {/* Circular Add-To-Cart Plus Button (44px target) */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleAddToCart(item.name, e);
                      }}
                      className={`absolute bottom-3 right-3 w-11 h-11 rounded-full flex items-center justify-center transition-all duration-300 z-30 cursor-pointer shadow-md border ${
                        isAdded
                          ? "bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-500"
                          : "bg-white dark:bg-neutral-800 text-muted hover:text-accent hover:border-accent border-border"
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
            View Full Timeline <ArrowRight className="h-3 w-3" />
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
              No active depletions tracked.
            </div>
          ) : (
            [...depleting]
              .map((item) => {
                const isRefilled = refilledItems.has(item.name);
                const cycleDays = parseFloat(item.cycle) || 30;
                const fillPct = isRefilled ? 95 : Math.max(8, Math.min(95, Math.round((item.days / cycleDays) * 100)));
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
                    key={item.name}
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

      {/* ── Smartphone Push Notification ──────────────────── */}
      {phoneAlert && (
        <div 
          onClick={handleToastClick}
          className="fixed top-6 right-6 z-50 max-w-sm w-full bg-black/90 dark:bg-neutral-900/95 text-white p-4 rounded-2xl shadow-2xl border border-neutral-800 backdrop-blur-md cursor-pointer spring-notification flex gap-3 hover:scale-[1.02] active:scale-[0.98] transition-all"
        >
          {/* Simulated App Icon */}
          <div className="h-10 w-10 bg-accent rounded-xl flex items-center justify-center text-white font-extrabold text-xs shrink-0 shadow-lg shadow-accent/25">
            INS
          </div>
          <div className="flex-1 flex flex-col gap-0.5">
            <div className="flex justify-between items-center">
              <span className="text-[10px] uppercase font-bold text-accent tracking-widest font-display">SWIGGY INSTAMART</span>
              <span className="text-[9px] text-muted font-bold font-display font-sans">NOW</span>
            </div>
            <span className="font-extrabold text-xs tracking-tight text-white font-display mt-0.5">
              Pantry Depletion Alert
            </span>
            <p className="text-[11px] leading-relaxed text-neutral-300 font-sans mt-0.5">
              {phoneAlert}
            </p>
            <span className="text-[9px] text-accent/90 font-bold uppercase tracking-wider font-display mt-1.5 flex items-center gap-0.5 animate-pulse">
              Tap to open WhatsApp & reorder →
            </span>
          </div>
          <button 
            onClick={(e) => {
              e.stopPropagation();
              setPhoneAlert(null);
            }}
            className="text-muted hover:text-white transition-colors self-start p-1 cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

    </div>
  );
}

