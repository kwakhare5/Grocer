'use client';
/* ─────────────────────────────────────────────────────────
   Recipe Intelligence — Demo Scene 5
   "Type Sunday biryani for 6. Show ingredient parsing.
    Show the pantry check. Show the missing items cart."
   — CLAUDE.md Part 7

   This page has ONE primary interaction: type a dish name,
   get a pantry-aware ingredient check. The search is the UI.
───────────────────────────────────────────────────────── */
import { useState } from 'react';

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

/* Simulated pantry-aware results for demo dishes */
const RECIPE_DB: Record<string, RecipeResult> = {
  biryani: {
    dish: "Chicken Biryani",
    servings: 6,
    ingredients: [
      { name: "India Gate Basmati Rice",  needed: "600g",  status: "have",    estimated: "~800g left"   },
      { name: "Onions",                   needed: "400g",  status: "have",    estimated: "~600g left"   },
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
      { name: "Amul Butter",             needed: "50g",   status: "have",    estimated: "~100g left"  },
      { name: "Onions",                  needed: "200g",  status: "have",    estimated: "~600g left"  },
      { name: "Tata Salt",               needed: "5g",    status: "have",    estimated: "~800g left"  },
      { name: "Amul Fresh Cream",        needed: "100ml", status: "missing", price: 55 },
      { name: "Kasuri Methi",            needed: "5g",    status: "missing", price: 35 },
    ],
  },
  "aloo paratha": {
    dish: "Aloo Paratha",
    servings: 4,
    ingredients: [
      { name: "Aashirvaad Atta",         needed: "400g",  status: "have",    estimated: "~1.2kg left" },
      { name: "Tata Salt",               needed: "10g",   status: "have",    estimated: "~800g left"  },
      { name: "Fortune Sunflower Oil",   needed: "30ml",  status: "low",     estimated: "~90ml left", price: 40 },
      { name: "Amul Butter",             needed: "30g",   status: "have",    estimated: "~100g left"  },
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

  const handleSearch = (q: string) => {
    setQuery(q);
    setOrdered(false);
    if (!q.trim()) { setResult(null); return; }
    setLoading(true);
    // Simulate API latency
    setTimeout(() => {
      setResult(findRecipe(q));
      setLoading(false);
    }, 600);
  };

  const missing    = result?.ingredients.filter(i => i.status === 'missing') ?? [];
  const low        = result?.ingredients.filter(i => i.status === 'low')     ?? [];
  const cartItems  = [...missing, ...low];
  const cartTotal  = cartItems.reduce((sum, i) => sum + (i.price ?? 0), 0);

  return (
    <div className="flex flex-col gap-12">

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex flex-col gap-3">
        <div className="font-data text-accent text-[10px] tracking-widest uppercase">
          M-03 · Recipe Intelligence
        </div>
        <h1 className="text-5xl font-light tracking-tight uppercase leading-none">
          Recipe<br />
          <span className="font-black">Planner</span>
        </h1>
        <p className="font-data text-sm text-muted max-w-lg">
          Tell the system what you&apos;re cooking. It checks your estimated pantry
          and shows exactly what&apos;s missing — ready to order in one tap.
        </p>
      </div>

      {/* ── Search — this IS the product ────────────────────── */}
      <div className="card p-6 flex flex-col gap-4">
        <div className="font-data text-[10px] text-muted uppercase tracking-widest">
          What are you cooking?
        </div>
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch(query)}
            placeholder="e.g. Sunday Biryani for 6, Dal Makhani, Aloo Paratha..."
            className="flex-1 bg-background border border-border px-4 py-3 font-data text-sm
                       placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
          />
          <button
            onClick={() => handleSearch(query)}
            className="px-6 py-3 bg-accent text-white font-data text-xs uppercase tracking-widest
                       hover:bg-accent/90 transition-colors"
          >
            Check Pantry
          </button>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-data text-[10px] text-muted uppercase tracking-widest">Try:</span>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => handleSearch(s)}
              className="font-data text-[11px] text-accent border border-accent/30 px-3 py-1
                         hover:bg-accent-dim transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* ── Loading ─────────────────────────────────────────── */}
      {loading && (
        <div className="card p-8 flex items-center gap-4">
          <div className="dot-pulse" />
          <span className="font-data text-sm text-muted">Checking pantry against order history...</span>
        </div>
      )}

      {/* ── No match ────────────────────────────────────────── */}
      {!loading && query && !result && (
        <div className="card p-8 font-data text-sm text-muted">
          Recipe not in demo database. Try: Biryani, Dal Makhani, or Aloo Paratha.
        </div>
      )}

      {/* ── Results ─────────────────────────────────────────── */}
      {!loading && result && (
        <div className="flex flex-col gap-6">

          {/* Recipe header */}
          <div className="flex items-center justify-between">
            <div>
              <div className="font-data text-[10px] text-muted uppercase tracking-widest">Pantry check for</div>
              <div className="text-2xl font-black tracking-tight uppercase mt-1">{result.dish}</div>
            </div>
            <span className="pill pill-muted">{result.servings} servings</span>
          </div>

          {/* Ingredients table */}
          <div className="card overflow-hidden">
            <div className="px-6 py-3 border-b border-border font-data text-[10px] text-muted uppercase tracking-widest">
              Ingredient Check — {result.ingredients.length} items
            </div>
            <div className="divide-y divide-border">
              {result.ingredients.map((ing) => (
                <div
                  key={ing.name}
                  className="px-6 py-4 flex items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-4 min-w-0">
                    <span className={
                      ing.status === 'have'    ? 'text-ok text-lg'      :
                      ing.status === 'low'     ? 'text-warning text-lg' :
                                                 'text-danger text-lg'
                    }>
                      {ing.status === 'have' ? '✓' : ing.status === 'low' ? '⚠' : '✗'}
                    </span>
                    <div className="flex flex-col min-w-0">
                      <span className="font-semibold text-sm">{ing.name}</span>
                      {ing.estimated && (
                        <span className="font-data text-xs text-muted">{ing.estimated}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 shrink-0">
                    <span className="font-data text-xs text-muted">{ing.needed}</span>
                    {ing.status !== 'have' && (
                      <span className={`pill ${ing.status === 'low' ? 'pill-warning' : 'pill-danger'}`}>
                        {ing.status === 'low' ? 'LOW' : 'MISSING'}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Missing items cart */}
          {cartItems.length > 0 && !ordered && (
            <div className="card overflow-hidden border-accent">
              <div className="px-6 py-4 border-b border-border flex items-center justify-between">
                <div className="font-data text-[10px] text-accent uppercase tracking-widest">
                  Missing Items Cart — ₹{cartTotal}
                </div>
                <span className="pill pill-accent">{cartItems.length} items</span>
              </div>
              <div className="divide-y divide-border">
                {cartItems.map((item) => (
                  <div key={item.name} className="px-6 py-3 flex items-center justify-between font-data text-sm">
                    <span>{item.name}</span>
                    <span className="text-muted">₹{item.price}</span>
                  </div>
                ))}
              </div>
              <div className="px-6 py-4 border-t border-border flex items-center justify-between">
                <span className="font-data text-sm font-bold">Total: ₹{cartTotal}</span>
                <button
                  onClick={() => setOrdered(true)}
                  className="px-6 py-2 bg-accent text-white font-data text-xs uppercase tracking-widest
                             hover:bg-accent/90 transition-colors"
                >
                  Order Missing Items →
                </button>
              </div>
            </div>
          )}

          {/* Order confirmation */}
          {ordered && (
            <div className="card p-6 border-ok flex items-center gap-4">
              <span className="text-ok text-2xl">✓</span>
              <div className="flex flex-col gap-1">
                <span className="font-bold text-ok">Order Placed — ₹{cartTotal}</span>
                <span className="font-data text-xs text-muted">
                  {cartItems.length} items · Arriving in ~15 minutes · Order #INS_MOCK_DEMO
                </span>
              </div>
            </div>
          )}

        </div>
      )}

    </div>
  );
}
