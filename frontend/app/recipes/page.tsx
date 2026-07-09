"use client";

import { useState, useEffect } from "react";
import { predictionsApi, APIPrediction } from "../../lib/api";
import { COLOR_PALETTE } from "../../lib/theme";
import { CheckCircle2, AlertTriangle, XCircle, Search, Calendar, ShoppingCart, Loader2, ChefHat, Activity } from "lucide-react";

type Ingredient = {
  name: string;
  needed: string;
  status: "have" | "low" | "missing";
  estimated?: string;
  price?: number;
};

type RecipeResult = {
  dish: string;
  servings: number;
  ingredients: Ingredient[];
};

const RECIPE_DB: Record<string, RecipeResult> = {
  biryani: {
    dish: "Chicken Biryani",
    servings: 6,
    ingredients: [
      { name: "Basmati Rice",             needed: "600g",  status: "have",    estimated: "~800g in kitchen"   },
      { name: "Onions",                   needed: "400g",  status: "have",    estimated: "~600g in kitchen"   },
      { name: "Fortune Sunflower Oil",    needed: "80ml",  status: "low",     estimated: "~90ml left", price: 127 },
      { name: "Amul Fresh Cream",         needed: "200ml", status: "missing", price: 55 },
      { name: "Kasuri Methi",             needed: "10g",   status: "missing", price: 35 },
      { name: "Saffron",                  needed: "1g",    status: "missing", price: 120 },
    ],
  },
  "dal makhani": {
    dish: "Dal Makhani",
    servings: 4,
    ingredients: [
      { name: "Amul Butter",             needed: "50g",   status: "have",    estimated: "~100g in kitchen"  },
      { name: "Onions",                  needed: "200g",  status: "have",    estimated: "~600g in kitchen"  },
      { name: "Tata Salt",               needed: "5g",    status: "have",    estimated: "~800g in kitchen"  },
      { name: "Amul Fresh Cream",        needed: "100ml", status: "missing", price: 55 },
      { name: "Kasuri Methi",            needed: "5g",    status: "missing", price: 35 },
    ],
  },
  "aloo paratha": {
    dish: "Aloo Paratha",
    servings: 4,
    ingredients: [
      { name: "Aashirvaad Atta",         needed: "400g",  status: "have",    estimated: "~1.2kg in kitchen" },
      { name: "Tata Salt",               needed: "10g",   status: "have",    estimated: "~800g in kitchen"  },
      { name: "Fortune Sunflower Oil",   needed: "30ml",  status: "low",     estimated: "~90ml left", price: 40 },
      { name: "Amul Butter",             needed: "30g",   status: "have",    estimated: "~100g in kitchen"  },
    ],
  },
};

function findRecipe(query: string): RecipeResult | null {
  const q = query.toLowerCase().trim();
  for (const key of Object.keys(RECIPE_DB)) {
    if (q.includes(key)) return RECIPE_DB[key];
  }
  return null;
}

const SUGGESTIONS = ["Sunday Biryani", "Dal Makhani", "Aloo Paratha"];

export default function RecipesPage() {
  const [query, setQuery]     = useState("");
  const [result, setResult]   = useState<RecipeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [ordered, setOrdered] = useState(false);
  const [predictions, setPredictions] = useState<APIPrediction[]>([]);
  
  // Interactive Local UI states
  const [isPinnedToSunday, setIsPinnedToSunday] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    async function loadPantry() {
      try {
        const predRes = await predictionsApi.getForHousehold("demo_user_001");
        if (predRes.data && predRes.data.predictions) {
          setPredictions(predRes.data.predictions);
        }
      } catch (err) {
        console.warn("Failed to fetch pantry details, running on local fallbacks.", err);
      }
    }
    loadPantry();
  }, []);

  const triggerToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 3000);
  };

  const handleSearch = (q: string) => {
    setQuery(q);
    setOrdered(false);
    setIsPinnedToSunday(false);
    if (!q.trim()) { setResult(null); return; }
    setLoading(true);

    setTimeout(() => {
      const baseRecipe = findRecipe(q);
      if (baseRecipe) {
        const hydratedIngredients = baseRecipe.ingredients.map(ing => {
          const predMatch = predictions.find(p => 
            p.item_name.toLowerCase().includes(ing.name.toLowerCase()) ||
            ing.name.toLowerCase().includes(p.item_name.split(" — ")[0].split(" (")[0].toLowerCase())
          );

          if (predMatch) {
            let status: "have" | "low" | "missing" = "have";
            if (predMatch.status === "depleted" || predMatch.status === "critical") {
              status = "missing";
            } else if (predMatch.status === "low") {
              status = "low";
            }

            let estimated = ing.estimated;
            if (predMatch.days_remaining !== null) {
              const remainingQty = predMatch.avg_daily_consumption * Math.max(0, predMatch.days_remaining);
              if (remainingQty > 0) {
                const unit = predMatch.item_name.includes("Milk") || predMatch.item_name.includes("Oil") ? "L" : "kg";
                if (unit === "L" && remainingQty < 1.0) {
                  estimated = `~${Math.round(remainingQty * 1000)}ml in kitchen`;
                } else if (unit === "kg" && remainingQty < 1.0) {
                  estimated = `~${Math.round(remainingQty * 1000)}g in kitchen`;
                } else {
                  estimated = `~${remainingQty.toFixed(1)}${unit} in kitchen`;
                }
              } else {
                estimated = "None left";
              }
            }

            return {
              ...ing,
              status,
              estimated,
              price: ing.price || Math.round(predMatch.last_purchase_quantity * 50) || 120
            };
          }
          return ing;
        });

        setResult({
          ...baseRecipe,
          ingredients: hydratedIngredients
        });
      } else {
        setResult(null);
      }
      setLoading(false);
    }, 600);
  };

  const handleOrderMissing = () => {
    setOrdered(true);
    triggerToast("Order placed successfully!");
  };

  const handleTogglePinRecipe = () => {
    setIsPinnedToSunday(!isPinnedToSunday);
    if (!isPinnedToSunday) {
      triggerToast(`Pinned ${result?.dish} to Sunday Meal Plan!`);
    } else {
      triggerToast(`Removed ${result?.dish} from Sunday Meal Plan.`);
    }
  };

  const missing    = result?.ingredients.filter(i => i.status === "missing") ?? [];
  const low        = result?.ingredients.filter(i => i.status === "low")     ?? [];
  const cartItems  = [...missing, ...low];
  const cartTotal  = cartItems.reduce((sum, i) => sum + (i.price ?? 0), 0);

  return (
    <div className="flex flex-col gap-10 relative">

      {/* ── App Header ──────────────────────────────────────── */}
      <div className="flex flex-col gap-2.5 border-b border-border/40 pb-8">
        <div className="text-accent text-[11px] font-bold tracking-widest uppercase font-display flex items-center gap-1.5">
          <ChefHat className="h-4 w-4" />
          <span>Meal Planner</span>
        </div>
        <h1 className="text-4xl font-bold tracking-tight leading-none font-display text-foreground">
          Recipe <span className="title-accent">Pantry Checker</span>
        </h1>
        <p className="text-sm text-muted max-w-lg leading-relaxed font-medium mt-1">
          Check ingredients against pantry levels, see what is missing, and auto-refill instantly.
        </p>
      </div>

      {/* ── 2-Column App Grid ────────────────────────────────── */}
      <div className="grid grid-cols-12 gap-8 items-start">
        
        {/* Main Cooking Checklist Area (Left, col-span-8) */}
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
          
          {/* Search Card */}
          <div className="glass-card p-6 flex flex-col gap-4">
            <span className="font-extrabold text-xs text-foreground font-display uppercase tracking-wider">What are you cooking?</span>
            <div className="flex gap-2.5">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch(query)}
                placeholder="Search recipe: e.g. Sunday Biryani, Dal Makhani..."
                className="flex-1 bg-white border border-border/60 px-4 h-11 text-xs rounded-md focus:outline-none focus:border-accent transition-colors font-medium"
              />
              <button
                onClick={() => handleSearch(query)}
                className="h-11 px-5 btn-premium-blue text-white font-extrabold text-xs tracking-wider uppercase rounded-md transition-all flex items-center justify-center gap-1.5 font-display cursor-pointer"
              >
                <Search className="h-4 w-4" />
                Check
              </button>
            </div>

            <div className="flex items-center gap-2 flex-wrap text-xs font-medium border-t border-border/30 pt-3 mt-1">
              <span className="text-muted/70 text-[10px] uppercase font-bold tracking-wider mr-1.5">Suggestions:</span>
              {SUGGESTIONS.map((s, idx) => {
                const colors = [
                  COLOR_PALETTE.orange,
                  COLOR_PALETTE.green,
                  COLOR_PALETTE.blue,
                  COLOR_PALETTE.gray
                ];
                const c = colors[idx % colors.length];
                return (
                  <button
                    key={s}
                    onClick={() => handleSearch(s)}
                    className="h-8 px-3.5 rounded-md transition-colors cursor-pointer text-xs font-bold font-display border"
                    style={{ 
                      color: c.text, 
                      borderColor: c.border, 
                      backgroundColor: c.bg
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = c.hover}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = c.bg}
                  >
                    {s}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Loading details state */}
          {loading && (
            <div className="glass-card p-6 flex items-center justify-center gap-3.5">
              <Loader2 className="h-5 w-5 text-accent animate-spin" />
              <span className="text-xs text-muted font-bold uppercase tracking-wider font-display">Checking pantry stock...</span>
            </div>
          )}

          {/* No match error state */}
          {!loading && query && !result && (
            <div className="glass-card p-6 text-xs text-muted font-bold uppercase tracking-wider text-center">
              Recipe not found. Try: <span className="text-accent underline cursor-pointer" onClick={() => handleSearch("Biryani")}>Biryani</span> or <span className="text-accent underline cursor-pointer" onClick={() => handleSearch("Dal Makhani")}>Dal Makhani</span>
            </div>
          )}

          {/* Ingredients table details */}
          {!loading && result && (
            <div className="flex flex-col gap-5">
              
              {/* Recipe Info Block */}
              <div className="flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="text-[9px] text-muted font-bold uppercase tracking-wider font-display">Hydrated Checklist for</span>
                  <span className="text-xl font-black text-foreground font-display mt-0.5">{result.dish}</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <span className="pill pill-muted font-semibold font-display">{result.servings} servings</span>
                  <button
                    onClick={handleTogglePinRecipe}
                    className={`h-9 px-4 rounded-md text-xs font-bold border transition-all active:scale-95 flex items-center justify-center gap-1.5 cursor-pointer ${
                      isPinnedToSunday
                        ? "bg-amber-100 text-amber-800 border-amber-300"
                        : "bg-white text-muted border-border/80 hover:text-foreground"
                    }`}
                  >
                    <Calendar className="h-4 w-4" />
                    {isPinnedToSunday ? "Pinned to Plan" : "Pin to Sunday"}
                  </button>
                </div>
              </div>

              {/* Ingredients Table */}
              <div className="glass-card overflow-hidden">
                <div className="px-5 py-3.5 border-b border-border/60 text-[10px] font-bold text-muted uppercase tracking-wider font-display bg-white/40">
                  Ingredients Checklist ({result.ingredients.length} items)
                </div>
                <div className="divide-y divide-border/60">
                  {result.ingredients.map((ing) => (
                    <div
                      key={ing.name}
                      className="px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                    >
                      <div className="flex items-center gap-3.5 min-w-0">
                        <span className="shrink-0">
                          {ing.status === "have" && <CheckCircle2 className="h-4.5 w-4.5 text-ok" />}
                          {ing.status === "low" && <AlertTriangle className="h-4.5 w-4.5 text-warning" />}
                          {ing.status === "missing" && <XCircle className="h-4.5 w-4.5 text-danger" />}
                        </span>
                        <div className="flex flex-col min-w-0">
                          <span className="font-extrabold text-xs text-foreground font-display">{ing.name}</span>
                          {ing.estimated && (
                            <span className="text-[10px] text-muted mt-0.5 font-medium">{ing.estimated}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-4 shrink-0">
                        <span className="text-[10px] font-bold text-muted/80 font-display">{ing.needed} needed</span>
                        <span className={`pill ${
                          ing.status === "have" ? "pill-ok" :
                          ing.status === "low" ? "pill-warning" :
                          "pill-danger"
                        } font-semibold font-display`}>
                          {ing.status === "have" ? "Stocked" : ing.status === "low" ? "Running Low" : "Need to buy"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar Order Checkout / Summary (Right, col-span-4) */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-4">
          
          {/* Order confirmation block */}
          {ordered && (
            <div className="glass-card p-6 border border-ok flex items-start gap-3 shadow-sm animate-in fade-in duration-200">
              <CheckCircle2 className="h-5 w-5 text-ok shrink-0 mt-0.5" />
              <div className="flex flex-col">
                <span className="font-extrabold text-ok text-xs font-display">Order Confirmed!</span>
                <span className="text-[10px] text-muted font-medium mt-1 leading-relaxed">
                  Arriving in ~15 mins.<br />Order ID: #INS_MOCK_DEMO
                </span>
              </div>
            </div>
          )}

          {/* Missing items checkout summary */}
          {result && cartItems.length > 0 && !ordered && (
            <div className="glass-card overflow-hidden border border-dashed border-accent/40 shadow-sm">
              <div className="px-6 py-4 border-b border-border/60 bg-neutral-50/30 flex justify-between items-center">
                <div className="text-[10px] font-bold text-accent uppercase tracking-wider font-display">
                  Missing Restock items
                </div>
                <span className="pill pill-accent font-semibold font-display">{cartItems.length} items</span>
              </div>
              
              <div className="divide-y divide-dashed divide-border/60 px-5 py-1">
                {cartItems.map((item) => (
                  <div key={item.name} className="py-2.5 flex items-center justify-between text-[11px] font-bold font-display">
                    <span className="text-foreground truncate max-w-[70%]">{item.name}</span>
                    <span className="text-muted shrink-0">₹{item.price}</span>
                  </div>
                ))}
              </div>
              
              <div className="px-6 py-4 flex flex-col gap-2 hover:bg-neutral-50/50 transition-colors">
                <div className="flex justify-between items-baseline">
                  <span className="text-xs text-muted uppercase font-bold tracking-wider font-display">Total</span>
                  <span className="text-sm font-extrabold text-foreground font-display">₹{cartTotal}</span>
                </div>
                <button
                  onClick={handleOrderMissing}
                  className="h-10 w-full btn-premium-blue text-white font-extrabold text-xs uppercase tracking-wider rounded-md transition-all cursor-pointer flex items-center justify-center gap-1.5 font-display"
                >
                  <ShoppingCart className="h-4 w-4" />
                  Order Missing Items
                </button>
              </div>
            </div>
          )}

          {/* Initial state placeholder when no recipe loaded */}
          {!result && (
            <div className="glass-card p-6 text-center">
              <Activity className="h-5 w-5 text-muted mx-auto mb-2 opacity-50" />
              <span className="text-[10px] text-muted font-bold uppercase tracking-wider font-display">No recipe loaded</span>
              <p className="text-[10px] text-muted/70 font-medium leading-relaxed mt-1">
                Search or select a suggestion to display cooking checklists and auto-refill carts.
              </p>
            </div>
          )}

        </div>

      </div>

      {/* ── Toast Notification ─────────────────────────────── */}
      {toastMessage && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 bg-neutral-900/95 text-white px-5 py-3 rounded-md shadow-[0_12px_40px_rgba(0,0,0,0.25)] flex items-center gap-2 border border-neutral-800 animate-in fade-in slide-in-from-bottom-4 duration-300">
          <span className="text-xs font-bold tracking-wide font-display">{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
