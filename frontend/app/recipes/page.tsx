'use client';

import { useState, useEffect } from 'react';
import { predictionsApi, APIPrediction } from '../../lib/api';
import { CheckCircle2, AlertTriangle, XCircle, Search, Calendar, ShoppingCart, Loader2, ChefHat } from 'lucide-react';

type Ingredient = {
  name: string;
  needed: string;
  status: 'have' | 'low' | 'missing';
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

const SUGGESTIONS = ["Sunday Biryani for 6", "Dal Makhani", "Aloo Paratha"];

export default function RecipesPage() {
  const [query, setQuery]     = useState('');
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
            let status: 'have' | 'low' | 'missing' = 'have';
            if (predMatch.status === 'depleted' || predMatch.status === 'critical') {
              status = 'missing';
            } else if (predMatch.status === 'low') {
              status = 'low';
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
      triggerToast(`Pinned ${result?.dish} to Sunday Meal Plan! Check notifications Saturday.`);
    } else {
      triggerToast(`Removed ${result?.dish} from Sunday Meal Plan.`);
    }
  };

  const missing    = result?.ingredients.filter(i => i.status === 'missing') ?? [];
  const low        = result?.ingredients.filter(i => i.status === 'low')     ?? [];
  const cartItems  = [...missing, ...low];
  const cartTotal  = cartItems.reduce((sum, i) => sum + (i.price ?? 0), 0);

  return (
    <div className="flex flex-col gap-10 relative">
      <div className="absolute top-[-50px] right-[-100px] w-[250px] h-[250px] bg-accent/6 blur-[100px] pointer-events-none -z-10" />

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-2.5">
        <div className="text-accent text-[11px] font-bold tracking-widest uppercase font-display flex items-center gap-1.5">
          <ChefHat className="h-4 w-4" />
          <span>Meal Planner & Auto-Cart</span>
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight leading-tight font-display text-foreground">
          Pantry-Aware <span className="text-accent">Recipe Checker</span>
        </h1>
        <p className="text-sm text-muted max-w-lg leading-relaxed font-medium">
          Plan what you want to cook. The system cross-references against estimated pantry levels and builds a checkout cart for what you need.
        </p>
      </div>

      {/* ── Search — this IS the product ────────────────────── */}
      <div className="glass-card p-6 flex flex-col gap-4 rounded-2xl border border-border/80">
        <div className="text-xs font-bold text-foreground font-display">
          What are you planning to cook?
        </div>
        <div className="flex gap-3 relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch(query)}
            placeholder="e.g. Sunday Biryani for 6, Dal Makhani, Aloo Paratha..."
            className="flex-1 bg-background border border-border/60 px-4 h-12 text-sm rounded-xl
                       placeholder:text-muted focus:outline-none focus:border-accent/80 focus:ring-1 focus:ring-accent/45 transition-all font-medium"
          />
          <button
            onClick={() => handleSearch(query)}
            className="h-12 px-6 bg-accent text-white font-bold text-xs uppercase tracking-widest rounded-xl
                       hover:bg-accent/90 transition-colors cursor-pointer flex items-center justify-center gap-1.5 font-display"
          >
            <Search className="h-4 w-4" />
            Check Pantry
          </button>
        </div>
        <div className="flex items-center gap-2.5 flex-wrap text-xs font-medium">
          <span className="text-muted mr-1.5">Try suggestions:</span>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => handleSearch(s)}
              className="text-accent border border-accent/20 h-11 px-4.5 rounded-full hover:bg-accent-dim transition-all cursor-pointer hover:border-accent/40 font-semibold"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* ── Loading ─────────────────────────────────────────── */}
      {loading && (
        <div className="glass-card p-8 flex items-center gap-4 rounded-2xl border border-border/80 bg-surface">
          <Loader2 className="h-5 w-5 text-accent animate-spin" />
          <span className="text-sm text-muted font-medium">Checking kitchen inventory matching history...</span>
        </div>
      )}

      {/* ── No match ────────────────────────────────────────── */}
      {!loading && query && !result && (
        <div className="glass-card p-8 text-sm text-muted rounded-2xl border border-border/80 bg-surface font-medium">
          Recipe not in demo database. Try searching for: <span className="font-bold text-accent">Biryani</span>, <span className="font-bold text-accent">Dal Makhani</span>, or <span className="font-bold text-accent">Aloo Paratha</span>.
        </div>
      )}

      {/* ── Results ─────────────────────────────────────────── */}
      {!loading && result && (
        <div className="flex flex-col gap-6">

          {/* Recipe header */}
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted font-bold font-display uppercase tracking-wider">Kitchen checklist for</div>
              <div className="text-2xl font-black text-foreground mt-1 font-display">{result.dish}</div>
            </div>
            <div className="flex items-center gap-3">
              <span className="pill pill-muted font-semibold font-display">{result.servings} servings</span>
              <button
                onClick={handleTogglePinRecipe}
                className={`h-11 px-4.5 rounded-full text-xs font-bold border transition-all cursor-pointer active:scale-[0.98] flex items-center justify-center gap-1.5 ${
                  isPinnedToSunday
                    ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-200"
                    : "bg-white/80 dark:bg-neutral-800 text-muted hover:text-foreground border-border hover:border-muted-foreground"
                }`}
              >
                <Calendar className="h-4 w-4" />
                {isPinnedToSunday ? "Pinned to Sunday" : "Pin to Sunday Meal"}
              </button>
            </div>
          </div>

          {/* Ingredients table */}
          <div className="glass-card overflow-hidden rounded-2xl border border-border/80">
            <div className="px-6 py-4 border-b border-border/60 text-xs font-bold text-muted uppercase tracking-wider font-display bg-white/40 dark:bg-neutral-900/20">
              Ingredient Checklist ({result.ingredients.length} total items)
            </div>
            <div className="divide-y divide-border/60">
              {result.ingredients.map((ing) => (
                <div
                  key={ing.name}
                  className="px-6 py-4.5 flex items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-4 min-w-0">
                    <span className="shrink-0">
                      {ing.status === 'have' && <CheckCircle2 className="h-5 w-5 text-ok" />}
                      {ing.status === 'low' && <AlertTriangle className="h-5 w-5 text-warning" />}
                      {ing.status === 'missing' && <XCircle className="h-5 w-5 text-danger" />}
                    </span>
                    <div className="flex flex-col min-w-0">
                      <span className="font-extrabold text-sm text-foreground font-display">{ing.name}</span>
                      {ing.estimated && (
                        <span className="text-xs text-muted/95 mt-1 font-medium">{ing.estimated}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 shrink-0">
                    <span className="text-xs font-bold text-muted/85 font-display">{ing.needed} needed</span>
                    <span className={`pill ${
                      ing.status === 'have' ? 'pill-ok' :
                      ing.status === 'low' ? 'pill-warning' :
                      'pill-danger'
                    } font-semibold font-display`}>
                      {ing.status === 'have' ? 'Stocked' : ing.status === 'low' ? 'Running Low' : 'Need to buy'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Missing items cart formatted as a dashed print receipt card */}
          {cartItems.length > 0 && !ordered && (
            <div className="glass-card overflow-hidden border-2 border-dashed border-accent/40 rounded-2xl shadow-sm bg-white/60 dark:bg-neutral-900/10">
              <div className="px-6 py-4.5 border-b border-dashed border-border/60 flex items-center justify-between bg-accent-dim/20">
                <div className="text-xs font-bold text-accent uppercase tracking-wider font-display">
                  Missing Items Auto-Cart
                </div>
                <span className="pill pill-accent font-semibold font-display">{cartItems.length} items to order</span>
              </div>
              <div className="divide-y divide-dashed divide-border/60 px-6 py-1">
                {cartItems.map((item) => (
                  <div key={item.name} className="py-3 flex items-center justify-between text-xs font-bold font-display">
                    <span className="text-foreground">{item.name}</span>
                    <span className="text-muted">₹{item.price}</span>
                  </div>
                ))}
              </div>
              <div className="px-6 py-4.5 border-t border-dashed border-border/60 flex items-center justify-between bg-neutral-100/30 dark:bg-neutral-900/20">
                <span className="text-sm font-extrabold text-foreground font-display">Estimated Total: ₹{cartTotal}</span>
                <button
                  onClick={handleOrderMissing}
                  className="h-11 px-6 bg-accent text-white font-bold text-xs uppercase tracking-widest rounded-full active:scale-[0.98]
                             hover:bg-accent/90 transition-all cursor-pointer flex items-center justify-center gap-1.5 font-display shadow-sm"
                >
                  <ShoppingCart className="h-4 w-4" />
                  Order Missing Items →
                </button>
              </div>
            </div>
          )}

          {/* Order confirmation */}
          {ordered && (
            <div className="glass-card p-6 border border-ok rounded-2xl flex items-center gap-4 bg-surface shadow-sm">
              <CheckCircle2 className="h-6 w-6 text-ok shrink-0" />
              <div className="flex flex-col gap-1">
                <span className="font-extrabold text-ok text-sm font-display">Order Placed successfully! — ₹{cartTotal}</span>
                <span className="text-xs text-muted font-medium">
                  {cartItems.length} items · Arriving in ~15 minutes · Order ID: #INS_MOCK_DEMO
                </span>
              </div>
            </div>
          )}

        </div>
      )}

      {/* ── Toast Notification ─────────────────────────────── */}
      {toastMessage && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 bg-neutral-900/95 dark:bg-neutral-100/95 backdrop-blur-md text-white dark:text-neutral-900 px-5 py-3 rounded-full shadow-[0_12px_40px_rgba(0,0,0,0.25)] flex items-center gap-2 border border-neutral-800 dark:border-neutral-200 animate-in fade-in slide-in-from-bottom-4 duration-300">
          <span className="text-xs font-bold tracking-wide font-display">{toastMessage}</span>
        </div>
      )}

    </div>
  );
}
