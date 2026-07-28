"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import {
  CheckCheck,
  Send,
  ShoppingCart,
  Zap,
  ChefHat,
  Tag,
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  MapPin,
  Search,
  Plus,
  Minus,
  Milk,
  Droplet,
  Wheat,
  Egg,
  Apple,
  Signal,
  Wifi,
  ChevronRight,
  Home,
  User,
  X
} from "lucide-react";
import { APIPrediction } from "../lib/api";
import { usePredictions } from "../lib/hooks";
import { toast } from "sonner";
import { Iphone } from "./ui/iphone";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";

interface PhoneMockupProps {
  activeScenario: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const RECIPE_DB = {
  biryani: {
    dish: "Chicken Biryani",
    servings: 6,
    prepTime: "45 mins",
    ingredients: [
      { name: "Basmati Rice", needed: "600g", status: "have", category: "Grains" },
      { name: "Onions", needed: "400g", status: "have", category: "Produce" },
      { name: "Sunflower Oil", needed: "80ml", status: "low", price: 127, category: "Oils" },
      { name: "Fresh Cream", needed: "200ml", status: "missing", price: 55, category: "Dairy" },
      { name: "Kasuri Methi", needed: "10g", status: "missing", price: 35, category: "Spices" },
    ]
  },
  dal: {
    dish: "Dal Makhani",
    servings: 4,
    prepTime: "30 mins",
    ingredients: [
      { name: "Butter", needed: "50g", status: "have", category: "Dairy" },
      { name: "Onions", needed: "200g", status: "have", category: "Produce" },
      { name: "Fresh Cream", needed: "100ml", status: "missing", price: 55, category: "Dairy" },
      { name: "Rajma Beans", needed: "200g", status: "missing", price: 45, category: "Staples" },
    ]
  },
  paneer: {
    dish: "Paneer Tikka",
    servings: 3,
    prepTime: "25 mins",
    ingredients: [
      { name: "Capsicum", needed: "200g", status: "have", category: "Produce" },
      { name: "Curd", needed: "200g", status: "have", category: "Dairy" },
      { name: "Fresh Paneer", needed: "250g", status: "missing", price: 90, category: "Dairy" },
      { name: "Tikka Masala", needed: "50g", status: "missing", price: 30, category: "Spices" },
    ]
  },
  oats: {
    dish: "Healthy Oats Bowl",
    servings: 2,
    prepTime: "10 mins",
    ingredients: [
      { name: "Rolled Oats", needed: "150g", status: "have", category: "Grains" },
      { name: "Honey", needed: "50ml", status: "have", category: "Pantry" },
      { name: "Fresh Milk", needed: "300ml", status: "low", price: 66, category: "Dairy" },
      { name: "Almonds", needed: "50g", status: "missing", price: 120, category: "Nuts" },
    ]
  }
};

const PRICE_SIGNALS = [
  { name: "Tomatoes 500g", current: 48, avg: 20, signal: "SPIKE", desc: "+140% vs 30d avg" },
  { name: "Sunflower Oil 1L", current: 98, avg: 127, signal: "DIP", desc: "-23% Stock Up" },
  { name: "Onions 1kg", current: 42, avg: 38, signal: "WATCH", desc: "+10% gradual rise" },
];

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default function PhoneMockup({ activeScenario }: PhoneMockupProps) {
  // Host App Bottom Navigation Tabs: "home" | "quick" | "prefill" | "account"
  const [hostTab, setHostTab] = useState<"home" | "quick" | "prefill" | "account">("prefill");

  // PreFill Feature Sub-Tabs: "pantry" | "recipes" | "signals"
  const [prefillSubTab, setPrefillSubTab] = useState<"pantry" | "recipes" | "signals">("pantry");

  const [itemQuantities, setItemQuantities] = useState<Record<string, number>>({});
  const [selectedRecipe, setSelectedRecipe] = useState<"biryani" | "dal" | "paneer" | "oats">("biryani");
  const [orderedRecipe, setOrderedRecipe] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isWhatsAppOpen, setIsWhatsAppOpen] = useState(false);
  const [restockedState, setRestockedState] = useState(false);
  const [selectedIngredients, setSelectedIngredients] = useState<Record<string, boolean>>({});

  const contentContainerRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Auto-reset scroll position when host tab changes
  useEffect(() => {
    if (contentContainerRef.current) {
      contentContainerRef.current.scrollTop = 0;
    }
  }, [hostTab]);

  // Auto-clear search query when sub-tab changes
  useEffect(() => {
    setSearchQuery("");
  }, [prefillSubTab]);

  // Reset selected ingredients when dish changes
  useEffect(() => {
    const recipe = RECIPE_DB[selectedRecipe as keyof typeof RECIPE_DB];
    const initial: Record<string, boolean> = {};
    recipe.ingredients.forEach(ing => {
      if (ing.status !== "have") {
        initial[ing.name] = true;
      }
    });
    setSelectedIngredients(initial);
  }, [selectedRecipe]);

  const toggleIngredientSelection = (name: string) => {
    setSelectedIngredients(prev => ({ ...prev, [name]: !prev[name] }));
  };

  const handleAddRecipeMissingToCart = () => {
    const recipe = RECIPE_DB[selectedRecipe as keyof typeof RECIPE_DB];
    const toAdd = recipe.ingredients.filter(i => i.status !== "have" && selectedIngredients[i.name] !== false);
    if (toAdd.length === 0) {
      toast.info("No missing ingredients selected");
      return;
    }
    toAdd.forEach(item => {
      setItemQuantities(prev => ({ ...prev, [item.name]: (prev[item.name] || 0) + 1 }));
    });
    setOrderedRecipe(true);
    toast.success(`Added ${toAdd.length} ingredients for ${recipe.dish} to Cart!`);
  };

  // WhatsApp Chat State
  const [messages, setMessages] = useState([
    {
      sender: "bot",
      text: "Good morning, Karan!\n\nYour household staples will run out in 24 hrs:\n• Fresh Milk 1L — ₹66\n• Tomatoes 500g — ₹32\n\nSubtotal: ₹98\nDelivery Fee: ₹15 | Handling: ₹5\nTotal Cart: ₹118 (10-Min Delivery)\n\nReply 'YES' to confirm auto-restock, or tap a chip below to modify items.",
      timestamp: "08:00 AM"
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const { predictionsData } = usePredictions("demo_user_001");

  const depleting = useMemo(() => {
    if (restockedState) {
      return [
        { id: "milk", name: "Fresh Milk 1L", days: 14, fillPct: 100, avg: "0.48L/day", icon: Milk, category: "dairy" },
        { id: "tomatoes", name: "Tomatoes 500g", days: 10, fillPct: 100, avg: "140g/day", icon: Apple, category: "produce" },
        { id: "eggs", name: "Farm Eggs 12pcs", days: 12, fillPct: 100, avg: "2.4/day", icon: Egg, category: "poultry" },
        { id: "bread", name: "Wheat Bread 400g", days: 9, fillPct: 100, avg: "0.24/day", icon: Wheat, category: "bakery" },
      ];
    }
    if (predictionsData?.predictions && predictionsData.predictions.length > 0) {
      return predictionsData.predictions.map((p: APIPrediction) => ({
        id: p.item_id,
        name: p.item_name.split(" — ")[0],
        days: p.days_remaining !== null ? Math.round(p.days_remaining) : 10,
        fillPct: p.stock_fill_percent !== undefined ? Math.round(p.stock_fill_percent) : 100,
        avg: `${p.avg_daily_consumption.toFixed(2)}/day`,
        icon: p.category === "dairy" ? Milk : p.category === "produce" ? Apple : p.category === "bakery" ? Wheat : Droplet,
        category: p.category
      }));
    }
    return [
      { id: "milk", name: "Fresh Milk 1L", days: 1, fillPct: 20, avg: "0.48L/day", icon: Milk, category: "dairy" },
      { id: "tomatoes", name: "Tomatoes 500g", days: 1, fillPct: 14, avg: "140g/day", icon: Apple, category: "produce" },
      { id: "eggs", name: "Farm Eggs 12pcs", days: 2, fillPct: 35, avg: "2.4/day", icon: Egg, category: "poultry" },
      { id: "bread", name: "Wheat Bread 400g", days: 3, fillPct: 65, avg: "0.24/day", icon: Wheat, category: "bakery" },
    ];
  }, [predictionsData, restockedState]);

  useEffect(() => {
    const handleScenarioSwitched = (e: Event) => {
      const customEv = e as CustomEvent<{ scenario?: string }>;
      const scenario = customEv.detail?.scenario || "refreshed";
      setRestockedState(false);
      setMessages([
        {
          sender: "bot",
          text: `Scenario updated to ${scenario.toUpperCase()}. Pantry state recalculated. What would you like to reorder?`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    };
    window.addEventListener("scenario-switched", handleScenarioSwitched);
    return () => window.removeEventListener("scenario-switched", handleScenarioSwitched);
  }, []);

  // Container-only scroll for WhatsApp drawer
  useEffect(() => {
    if (isWhatsAppOpen && chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, loading, isWhatsAppOpen]);

  const updateQuantity = (name: string, delta: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setItemQuantities((prev) => {
      const current = prev[name] || 0;
      const next = Math.max(0, current + delta);
      if (next === 0) {
        toast.info(`Removed ${name}`);
      } else if (current === 0 && next === 1) {
        toast.success(`Added ${name} to Cart`);
      }
      return { ...prev, [name]: next };
    });
  };

  const totalCartItems = Object.values(itemQuantities).reduce((a, b) => a + b, 0);

  const handleSendMessage = async (textToSend?: string) => {
    const msgText = textToSend || input;
    if (!msgText.trim() || loading) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMessages(prev => [...prev, { sender: "user", text: msgText, timestamp: timeStr }]);
    if (!textToSend) setInput("");
    setLoading(true);

    setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/webhook/whatsapp`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ phone: "+919999999999", message: msgText })
        });

        if (res.ok) {
          const data = await res.json();
          setMessages(prev => [
            ...prev,
            {
              sender: "bot",
              text: data.response_message || "Received, processing.",
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            }
          ]);
          if (data.response_message?.includes("Order placed") || msgText.includes("YES")) {
            setRestockedState(true);
            setItemQuantities({});
            toast.success("1-Tap Restock Confirmed! Household pantry restocked.");
            window.dispatchEvent(new CustomEvent("order-placed"));
          }
          return;
        }
      } catch {
        // Fallback smooth transition
      }

      if (msgText.includes("YES")) {
        setRestockedState(true);
        setItemQuantities({});
        toast.success("1-Tap Restock Confirmed! Household pantry restocked.");
        window.dispatchEvent(new CustomEvent("order-placed"));
      }
      setMessages(prev => [
        ...prev,
        {
          sender: "bot",
          text: "Order intent confirmed. Your 10-minute quick commerce delivery is dispatched and on the way!",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      setLoading(false);
    }, 800);
  };

  const currentRecipe = RECIPE_DB[selectedRecipe];
  const recipeMissing = currentRecipe.ingredients.filter(i => i.status !== "have");
  const recipeTotal = recipeMissing.reduce((acc, i) => acc + (i.price || 0), 0);

  const filteredStaples = depleting.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col items-center gap-2 w-[305px] h-[638px] aspect-[71.5/149.6] shrink-0 mx-auto select-none overflow-hidden rounded-[42px]">

      {/* Magic UI iPhone Mockup Frame */}
      <Iphone className="drop-shadow-2xl w-full h-full">
        <div className="w-full h-full bg-[#F6F7F8] flex flex-col relative pt-9 pb-0 overflow-hidden select-none">

          {/* Authentic Real iOS Top Status Bar */}
          <div className="absolute top-0 left-0 right-0 h-9 px-4.5 pt-1 flex items-center justify-between z-40 bg-[#F6F7F8]/90 backdrop-blur-md text-[#252525] font-sans border-b border-[#E5E7EB]">
            <span className="text-[11.5px] font-extrabold tracking-tight text-[#252525] font-sans ml-1">9:41</span>

            <div className="flex items-center gap-2 mr-1">
              {/* Cellular Signal Icon */}
              <div className="h-3.5 w-3.5 flex items-center justify-center shrink-0">
                <svg className="h-3.5 w-3.5 text-[#252525]" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="3" y="15" width="3" height="5" rx="0.8" />
                  <rect x="8" y="11" width="3" height="9" rx="0.8" />
                  <rect x="13" y="7" width="3" height="13" rx="0.8" />
                  <rect x="18" y="3" width="3" height="17" rx="0.8" />
                </svg>
              </div>

              {/* Wi-Fi Icon */}
              <div className="h-3.5 w-3.5 flex items-center justify-center shrink-0">
                <svg className="h-3.5 w-3.5 text-[#252525]" viewBox="0 0 24 24" fill="currentColor">
                  <path d="m1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9m8 8l3 3l3-3a4.237 4.237 0 0 0-6 0m-4-4l2 2a7.074 7.074 0 0 1 10 0l2-2C15.14 9.14 8.87 9.14 5 13" />
                </svg>
              </div>

              {/* Battery Icon */}
              <div className="h-3.5 w-3.5 flex items-center justify-center shrink-0">
                <svg className="h-3.5 w-3.5 text-[#252525]" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M17 7a3 3 0 0 1 3 3a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1a3 3 0 0 1-3 3H3a3 3 0 0 1-3-3v-4a3 3 0 0 1 3-3zm-1 2H3a1 1 0 0 0-1 1v4a1 1 0 0 0 1 1h13a1 1 0 0 0 1-1v-4a1 1 0 0 0-1-1m-11 1.5h3v3H5zm4.5 0h3v3h-3z" />
                </svg>
              </div>
            </div>
          </div>

          {/* Clean App Header */}
          <div className="bg-[#FFFFFF] border-b border-[#E5E7EB] px-2.5 pt-1.5 pb-2 flex flex-col gap-1.5 z-30 shrink-0 shadow-2xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1 text-[11.5px] font-bold text-[#252525] font-display">
                {restockedState ? (
                  <div className="flex items-center gap-1 text-[#15803D] font-bold truncate">
                    <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
                    <span className="truncate max-w-[170px]">Order #4029 Dispatched · 6 MINS</span>
                  </div>
                ) : (
                  <>
                    <MapPin className="h-3.5 w-3.5 text-[#15803D] shrink-0" />
                    <span className="truncate max-w-[170px]">Green Park · 10 MINS</span>
                  </>
                )}
              </div>
              <div className="h-5.5 w-5.5 rounded-full bg-[#252525] text-white font-bold text-[10px] flex items-center justify-center font-display shadow-2xs">
                K
              </div>
            </div>

            {/* App Search Bar */}
            <div className="bg-[#F3F4F6] rounded-full px-3 py-1 h-7 flex items-center gap-1.5 border border-[#E5E7EB]">
              <Search className="h-3.5 w-3.5 text-[#64717E] shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search milk, atta, tomatoes..."
                className="bg-transparent text-[10px] font-medium text-[#252525] focus:outline-none w-full placeholder:text-[#64717E] font-sans"
              />
            </div>
          </div>

          {/* PreFill Feature Segmented Sub-Tabs Bar (Uniform 3-Tab Control) */}
          {hostTab === "prefill" && (
            <div className="bg-[#F6F7F8] border-b border-[#E5E7EB] px-2.5 py-1.5 grid grid-cols-3 gap-1 z-30 shrink-0">
              {(["pantry", "recipes", "signals"] as const).map((tabKey) => {
                const isActive = prefillSubTab === tabKey;
                const IconComponent = tabKey === "pantry" ? ShoppingCart : tabKey === "recipes" ? ChefHat : Tag;
                const label = tabKey === "pantry" ? "Pantry" : tabKey === "recipes" ? "Recipes" : "Signals";

                return (
                  <button
                    key={tabKey}
                    onClick={() => setPrefillSubTab(tabKey)}
                    className={clsx(
                      "h-7.5 w-full rounded-lg text-[10px] font-bold font-display cursor-pointer transition-all active:scale-95 flex items-center justify-center gap-1.5 relative border",
                      isActive
                        ? "bg-[#252525] text-white border-[#252525] shadow-2xs"
                        : "bg-white text-[#64717E] border-[#E5E7EB] hover:border-slate-300 hover:text-[#252525]"
                    )}
                  >
                    <IconComponent className="h-3 w-3" />
                    <span>{label}</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* MAIN SCREEN CONTENT AREA */}
          <div ref={contentContainerRef} className="flex-1 overflow-y-auto no-scrollbar relative flex flex-col">

            {/* TAB: PREFILL SMART PANTRY MODULE */}
            {hostTab === "prefill" && (
              <div className="p-2.5 flex flex-col gap-2 pb-24">

                {/* SUB-TAB VIEW 1: PANTRY STOCK DEPLETION */}
                {prefillSubTab === "pantry" && (
                  <div className="flex flex-col gap-2">
                    <span className="text-[8.5px] font-bold uppercase tracking-wider text-[#64717E] font-display">Pantry Stock Depletion</span>
                    {filteredStaples.length === 0 ? (
                      <div className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 text-center flex flex-col items-center gap-1.5 shadow-2xs hover:border-slate-300 transition-all">
                        <Search className="h-4 w-4 text-[#64717E]" />
                        <span className="text-[10.5px] font-bold text-[#252525] font-display">No active depletion for &quot;{searchQuery}&quot;</span>
                        <span className="text-[9px] text-[#64717E]">Tap below to add this item to your Prophet ML consumption profile.</span>
                        <button
                          onClick={() => {
                            toast.success(`Added "${searchQuery}" to Consumption Profile`);
                            setSearchQuery("");
                          }}
                          className="bg-[#15803D] hover:bg-emerald-700 text-white font-extrabold text-[9px] px-3 py-1 h-6.5 rounded-md shadow-2xs active:scale-95 transition-all cursor-pointer mt-0.5"
                        >
                          + Add to Consumption Tracker
                        </button>
                      </div>
                    ) : (
                      filteredStaples.map((item) => {
                        const qty = itemQuantities[item.name] || 0;
                        const isDanger = item.fillPct < 25;
                        const isWarning = item.fillPct >= 25 && item.fillPct < 50;
                        const IconComponent = item.icon;

                        return (
                          <div key={item.id} className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 flex items-center justify-between gap-2 shadow-2xs hover:border-slate-300 active:scale-[0.99] transition-all">
                            <div className="flex items-center gap-2.5 min-w-0">
                              <div className={clsx("h-8 w-8 rounded-lg shrink-0 border flex items-center justify-center", item.category === "dairy" ? "bg-blue-50 text-blue-600 border-blue-100" : item.category === "produce" ? "bg-rose-50 text-rose-600 border-rose-100" : item.category === "poultry" ? "bg-amber-50 text-amber-600 border-amber-100" : "bg-emerald-50 text-emerald-600 border-emerald-100")}>
                                <IconComponent className="h-4 w-4" />
                              </div>
                              <div className="flex flex-col min-w-0 justify-center">
                                <span className="font-bold text-[11.5px] text-[#252525] font-display truncate leading-tight">{item.name}</span>
                                <span className="text-[9px] font-semibold text-[#64717E] truncate leading-tight mt-0.5">{item.avg} · {item.days}d left</span>

                                <div className="flex items-center gap-1.5 mt-1">
                                  <div className="w-14 h-1.5 bg-[#F3F4F6] rounded-full overflow-hidden border border-[#E5E7EB]">
                                    <div
                                      className={clsx("h-full rounded-full transition-all duration-500", isDanger ? "bg-[#BE123C]" : isWarning ? "bg-[#C2410C]" : "bg-[#15803D]")}
                                      style={{ width: `${item.fillPct}%` }}
                                    />
                                  </div>
                                  <span className={clsx("text-[8.5px] px-1.5 py-0.2 font-extrabold rounded-md border leading-none", isDanger ? "bg-[#FFF1F2] text-[#BE123C] border-[#FECDD3]" : isWarning ? "bg-[#FFFBEB] text-[#C2410C] border-[#FDE68A]" : "bg-[#F0FDF4] text-[#15803D] border-[#DCFCE7]")}>
                                    {item.fillPct}%
                                  </span>
                                </div>
                              </div>
                            </div>

                            {/* Interactive Quantity Selector */}
                            <AnimatePresence mode="wait">
                              {qty > 0 ? (
                                <motion.div
                                  key="stepper"
                                  initial={{ scale: 0.9, opacity: 0 }}
                                  animate={{ scale: 1, opacity: 1 }}
                                  exit={{ scale: 0.9, opacity: 0 }}
                                  transition={{ duration: 0.12 }}
                                  className="flex items-center gap-1.5 bg-[#15803D] text-white rounded-lg px-2 h-7 shrink-0 shadow-2xs"
                                >
                                  <button onClick={(e) => updateQuantity(item.name, -1, e)} className="p-0.5 cursor-pointer hover:text-slate-200 active:scale-95 transition-transform">
                                    <Minus className="h-3 w-3" />
                                  </button>
                                  <span className="text-[10px] font-extrabold font-sans px-0.5">{qty}</span>
                                  <button onClick={(e) => updateQuantity(item.name, 1, e)} className="p-0.5 cursor-pointer hover:text-slate-200 active:scale-95 transition-transform">
                                    <Plus className="h-3 w-3" />
                                  </button>
                                </motion.div>
                              ) : (
                                <motion.button
                                  key="add-btn"
                                  initial={{ scale: 0.9, opacity: 0 }}
                                  animate={{ scale: 1, opacity: 1 }}
                                  exit={{ scale: 0.9, opacity: 0 }}
                                  transition={{ duration: 0.12 }}
                                  onClick={(e) => updateQuantity(item.name, 1, e)}
                                  className="bg-white border border-[#15803D] text-[#15803D] hover:bg-emerald-50 text-[10px] font-extrabold px-3 h-7 rounded-lg flex items-center justify-center shrink-0 active:scale-[0.96] transition-all shadow-2xs cursor-pointer"
                                >
                                  <span>ADD</span>
                                </motion.button>
                              )}
                            </AnimatePresence>
                          </div>
                        );
                      })
                    )}
                  </div>
                )}

                {/* SUB-TAB VIEW 2: RECIPE INGREDIENT CHECKER */}
                {prefillSubTab === "recipes" && (
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[8.5px] font-bold uppercase tracking-wider text-[#64717E] font-display flex items-center gap-1">
                        <ChefHat className="h-3.5 w-3.5 text-[#252525]" /> Recipe Checker
                      </span>
                    </div>

                    {/* Equal-Width 4-Column Dish Selector Grid */}
                    <div className="grid grid-cols-4 gap-1.5 w-full py-0.5">
                      {(["biryani", "dal", "paneer", "oats"] as const).map((rKey) => (
                        <button
                          key={rKey}
                          onClick={() => { setSelectedRecipe(rKey); setOrderedRecipe(false); }}
                          className={clsx(
                            "h-7.5 w-full px-1 text-[10px] font-bold font-display cursor-pointer transition-all active:scale-95 capitalize rounded-lg flex items-center justify-center border",
                            selectedRecipe === rKey
                              ? "bg-[#252525] text-white border-[#252525] shadow-2xs"
                              : "bg-white text-[#64717E] border-[#E5E7EB] hover:border-slate-300 hover:text-[#252525]"
                          )}
                        >
                          {RECIPE_DB[rKey].dish.split(" ")[0]}
                        </button>
                      ))}
                    </div>

                    <div className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 flex flex-col gap-2 shadow-2xs hover:border-slate-300 transition-all">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-[11px] text-[#252525] font-display">{currentRecipe.dish}</span>
                        <span className="text-[8.5px] font-semibold text-[#64717E]">{currentRecipe.servings} servings · {currentRecipe.prepTime}</span>
                      </div>
                      <div className="flex flex-col divide-y divide-[#E5E7EB]/60">
                        {currentRecipe.ingredients.map((ing) => {
                          const isMissingOrLow = ing.status !== "have";
                          const isSelected = selectedIngredients[ing.name] !== false;

                          return (
                            <div
                              key={ing.name}
                              onClick={() => isMissingOrLow && toggleIngredientSelection(ing.name)}
                              className={clsx(
                                "py-1.5 px-1 flex items-center justify-between text-[9.5px] transition-colors rounded-md",
                                isMissingOrLow ? "cursor-pointer hover:bg-[#F6F7F8]" : "opacity-80"
                              )}
                            >
                              <div className="flex items-center gap-1.5 min-w-0">
                                {ing.status === "have" ? (
                                  <CheckCircle2 className="h-3.5 w-3.5 text-[#15803D] shrink-0" />
                                ) : isSelected ? (
                                  <div className="h-3.5 w-3.5 rounded bg-[#15803D] text-white flex items-center justify-center font-bold text-[8px] shrink-0">✓</div>
                                ) : (
                                  <div className="h-3.5 w-3.5 rounded border border-[#E5E7EB] bg-white shrink-0" />
                                )}
                                <span className={clsx("font-medium truncate", isSelected ? "text-[#252525]" : "text-[#64717E] line-through")}>
                                  {ing.name} ({ing.needed})
                                </span>
                              </div>
                              <span
                                className={clsx(
                                  "text-[8.5px] px-1.5 py-0.5 font-bold rounded-md border",
                                  ing.status === "have"
                                    ? "bg-[#F0FDF4] text-[#15803D] border-[#DCFCE7]"
                                    : isSelected
                                    ? "bg-[#F3F4F6] text-[#252525] border-[#E5E7EB]"
                                    : "bg-[#F6F7F8] text-[#64717E] border-[#E5E7EB]"
                                )}
                              >
                                {ing.status === "have" ? "Stocked" : ing.status === "low" ? "Low" : `₹${ing.price}`}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {orderedRecipe ? (
                      <div className="bg-[#F0FDF4] border border-[#DCFCE7] p-2.5 rounded-xl text-center text-[10px] font-bold text-[#15803D] font-display flex items-center justify-center gap-1.5 shadow-2xs">
                        <CheckCircle2 className="h-3.5 w-3.5 text-[#15803D]" />
                        <span>Ingredients Added to Cart!</span>
                      </div>
                    ) : (
                      recipeMissing.length > 0 && (
                        <button
                          onClick={handleAddRecipeMissingToCart}
                          className="bg-[#15803D] hover:bg-emerald-700 text-white px-3 py-1.5 h-9 w-full rounded-xl flex items-center justify-between cursor-pointer active:scale-[0.96] transition-all shadow-2xs"
                        >
                          <div className="flex items-center gap-1.5">
                            <span className="text-[10px] font-extrabold font-display">Add {recipeMissing.length} Missing Ingredients</span>
                          </div>
                          <span className="bg-white/20 text-white px-2 py-0.5 rounded-md text-[9px] font-extrabold font-display flex items-center gap-0.5">
                            Total ₹{recipeTotal} <ChevronRight className="h-2.5 w-2.5" />
                          </span>
                        </button>
                      )
                    )}
                  </div>
                )}

                {/* SUB-TAB VIEW 3: COMMODITY PRICE SIGNALS */}
                {prefillSubTab === "signals" && (
                  <div className="flex flex-col gap-2">
                    <span className="text-[8.5px] font-bold uppercase tracking-wider text-[#64717E] font-display flex items-center gap-1">
                      <Tag className="h-3.5 w-3.5 text-[#252525]" /> Market Price Signals
                    </span>

                    <div className="flex flex-col gap-2">
                      {PRICE_SIGNALS.map((p) => {
                        const isSpike = p.signal === "SPIKE";
                        const isDip = p.signal === "DIP";

                        return (
                          <div key={p.name} className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 flex flex-col gap-1.5 shadow-2xs hover:border-slate-300 active:scale-[0.99] transition-all">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-[11.5px] text-[#252525] font-display">{p.name}</span>
                              <span className={clsx("text-[8.5px] px-1.5 py-0.5 font-extrabold rounded-md border", isSpike ? "bg-[#FFF1F2] text-[#BE123C] border-[#FECDD3]" : isDip ? "bg-[#F0FDF4] text-[#15803D] border-[#DCFCE7]" : "bg-[#FFFBEB] text-[#C2410C] border-[#FDE68A]")}>
                                {p.signal}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-[9.5px] pt-1 border-t border-[#E5E7EB]/60">
                              <span className="font-bold text-[#252525] font-display">Today: ₹{p.current} <span className="text-[#64717E] font-normal">(Avg ₹{p.avg})</span></span>
                              <span className={clsx("font-bold flex items-center gap-0.5 text-[9px]", isSpike ? "text-[#BE123C]" : isDip ? "text-[#15803D]" : "text-[#C2410C]")}>
                                {isSpike ? <TrendingUp className="h-2.5 w-2.5" /> : <TrendingDown className="h-2.5 w-2.5" />}
                                {p.desc}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

              </div>
            )}

            {/* TAB: HOME MARKETPLACE */}
            {hostTab === "home" && (
              <div className="p-2.5 flex flex-col gap-2 pb-20">
                <div className="bg-white border border-[#E5E7EB] text-[#252525] rounded-xl p-2.5 flex flex-col gap-1 shadow-2xs hover:border-slate-300 transition-all">
                  <div className="flex items-center justify-between text-[8px] font-bold">
                    <span className="bg-[#15803D] text-white px-1.5 py-0.5 rounded-full uppercase">10-MIN EXPRESS</span>
                    <span className="text-[#15803D]">NEARBY STORE</span>
                  </div>
                  <span className="text-[12px] font-bold font-display text-[#252525]">Quick Commerce Store</span>
                  <span className="text-[9px] text-[#64717E] font-medium">10,000+ daily fresh groceries delivered to your door.</span>
                  <button
                    onClick={() => setHostTab("prefill")}
                    className="mt-1 bg-[#15803D] hover:bg-emerald-600 text-white px-2.5 py-1 rounded-md text-[9px] font-extrabold font-display cursor-pointer flex items-center justify-between active:scale-[0.96] transition-all shadow-2xs"
                  >
                    <span>Open PreFill AI Restock Module</span>
                    <ChevronRight className="h-2.5 w-2.5" />
                  </button>
                </div>

                <span className="text-[8.5px] font-bold uppercase tracking-wider text-[#64717E] font-display mt-0.5">Top Categories</span>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 flex flex-col gap-1 cursor-pointer hover:border-slate-300 active:scale-95 transition-all shadow-2xs">
                    <div className="p-1.5 rounded-lg bg-emerald-50 text-[#15803D] w-fit border border-emerald-200">
                      <ShoppingCart className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-[10.5px] font-bold text-[#252525]">Dairy & Milk</span>
                    <span className="text-[8.5px] text-[#64717E]">12 Instant Items</span>
                  </div>
                  <div className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 flex flex-col gap-1 cursor-pointer hover:border-slate-300 active:scale-95 transition-all shadow-2xs">
                    <div className="p-1.5 rounded-lg bg-rose-50 text-rose-600 w-fit border border-rose-200">
                      <Apple className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-[10.5px] font-bold text-[#252525]">Fresh Veggies</span>
                    <span className="text-[8.5px] text-[#64717E]">Farm Direct</span>
                  </div>
                  <div className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 flex flex-col gap-1 cursor-pointer hover:border-slate-300 active:scale-95 transition-all shadow-2xs">
                    <div className="p-1.5 rounded-lg bg-amber-50 text-amber-700 w-fit border border-amber-200">
                      <Wheat className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-[10.5px] font-bold text-[#252525]">Atta & Grains</span>
                    <span className="text-[8.5px] text-[#64717E]">Pantry Essentials</span>
                  </div>
                  <div className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 flex flex-col gap-1 cursor-pointer hover:border-slate-300 active:scale-95 transition-all shadow-2xs">
                    <div className="p-1.5 rounded-lg bg-purple-50 text-purple-700 w-fit border border-purple-200">
                      <Zap className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-[10.5px] font-bold text-[#252525]">Snacks & Drinks</span>
                    <span className="text-[8.5px] text-[#64717E]">Express Delivery</span>
                  </div>
                </div>
              </div>
            )}

            {/* TAB: QUICK 1-TAP REORDER */}
            {hostTab === "quick" && (
              <div className="p-2.5 flex flex-col gap-2 pb-20">
                <span className="text-[8.5px] font-bold uppercase tracking-wider text-[#64717E] font-display">1-Tap Household Bundles</span>

                <div className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 flex flex-col gap-1.5 shadow-2xs hover:border-slate-300 active:scale-[0.99] transition-all">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-[#252525] font-display">Weekly Basics Basket</span>
                    <span className="text-[10px] font-extrabold text-[#15803D]">₹420</span>
                  </div>
                  <span className="text-[8.5px] text-[#64717E]">Fresh Milk 1L, Atta 5kg, Eggs 12pcs, Tomatoes 500g</span>
                  <button
                    onClick={() => {
                      toast.success("1-Tap Bundle Added to Cart!");
                      updateQuantity("Fresh Milk 1L", 1);
                      updateQuantity("Wheat Bread 400g", 1);
                    }}
                    className="bg-[#15803D] hover:bg-emerald-700 text-white text-[9px] font-extrabold px-3 py-1 h-6.5 rounded-md flex items-center justify-between cursor-pointer active:scale-[0.96] transition-all shadow-2xs mt-0.5"
                  >
                    <span>Add Bundle to Cart</span>
                    <ChevronRight className="h-2.5 w-2.5" />
                  </button>
                </div>

                <div className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 flex flex-col gap-1.5 shadow-2xs hover:border-slate-300 active:scale-[0.99] transition-all">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-[#252525] font-display">Breakfast Essentials</span>
                    <span className="text-[10px] font-extrabold text-[#15803D]">₹280</span>
                  </div>
                  <span className="text-[8.5px] text-[#64717E]">Wheat Bread 400g, Butter 200g, Rolled Oats 500g</span>
                  <button
                    onClick={() => {
                      toast.success("Breakfast Bundle Added to Cart!");
                      updateQuantity("Wheat Bread 400g", 1);
                    }}
                    className="bg-[#15803D] hover:bg-emerald-700 text-white text-[9px] font-extrabold px-3 py-1 h-6.5 rounded-md flex items-center justify-between cursor-pointer active:scale-[0.96] transition-all shadow-2xs mt-0.5"
                  >
                    <span>Add Bundle to Cart</span>
                    <ChevronRight className="h-2.5 w-2.5" />
                  </button>
                </div>
              </div>
            )}

            {/* TAB: USER ACCOUNT & PANTRY HEALTH */}
            {hostTab === "account" && (
              <div className="p-2.5 flex flex-col gap-2 pb-20">
                <div className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 flex items-center gap-2.5 shadow-2xs hover:border-slate-300 transition-all">
                  <div className="h-8 w-8 rounded-full bg-[#252525] text-white font-bold text-[11px] flex items-center justify-center font-display shrink-0">
                    K
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="text-[11px] font-bold text-[#252525] font-display truncate">Karan Wakhare</span>
                    <span className="text-[8.5px] text-[#64717E] truncate">Green Park, New Delhi · Premium Household</span>
                  </div>
                </div>

                <div className="bg-white border border-[#E5E7EB] rounded-xl p-2.5 flex flex-col gap-1.5 shadow-2xs hover:border-slate-300 transition-all">
                  <div className="flex items-center justify-between text-[8.5px] font-bold">
                    <span className="text-[#15803D] uppercase">PANTRY HEALTH INDEX</span>
                    <span className="text-[#15803D]">84% STOCKED</span>
                  </div>
                  <div className="w-full h-1.5 bg-[#F3F4F6] rounded-full overflow-hidden border border-[#E5E7EB]">
                    <div className="h-full bg-[#15803D] w-[84%] rounded-full" />
                  </div>
                  <span className="text-[8.5px] text-[#64717E] mt-0.5">Prophet ML model active. Next automated order window: Tomorrow 8:00 AM</span>
                </div>

                <div className="rounded-xl border border-[#E5E7EB] bg-white p-2.5 flex flex-col divide-y divide-[#E5E7EB]/60 shadow-2xs hover:border-slate-300 transition-all">
                  <div className="py-2 px-1.5 flex items-center justify-between text-[9.5px] font-bold text-[#252525]">
                    <span>WhatsApp Restock Subscriptions</span>
                    <span className="bg-[#F0FDF4] text-[#15803D] border border-[#DCFCE7] text-[8px] px-1.5 py-0.5 rounded-md font-extrabold">Active</span>
                  </div>
                  <div className="py-2 px-1.5 flex items-center justify-between text-[9.5px] font-bold text-[#252525]">
                    <span>Notification Preferences</span>
                    <span className="text-[#64717E] text-[8.5px]">Enabled</span>
                  </div>
                  <div className="py-2 px-1.5 flex items-center justify-between text-[9.5px] font-bold text-[#252525]">
                    <span>Payment Methods</span>
                    <span className="text-[#64717E] text-[8.5px]">UPI / Apple Pay</span>
                  </div>
                </div>
              </div>
            )}

          </div>

          {/* Floating Cart Drawer Banner */}
          {hostTab === "prefill" && totalCartItems > 0 && (
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 20, opacity: 0 }}
              onClick={() => setIsWhatsAppOpen(true)}
              className="absolute bottom-[68px] left-3 right-15 bg-[#15803D] text-white rounded-xl p-2 flex items-center justify-between shadow-lg z-30 cursor-pointer active:scale-[0.98] transition-transform"
            >
              <div className="flex items-center gap-1.5 text-[9.5px] font-extrabold font-display truncate">
                <ShoppingCart className="h-3.5 w-3.5 text-white fill-current shrink-0" />
                <span className="truncate">{totalCartItems} ITEM{totalCartItems > 1 ? "S" : ""} · ₹{totalCartItems * 66}</span>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); setIsWhatsAppOpen(true); }}
                className="text-[9px] font-extrabold font-display bg-white text-[#15803D] hover:bg-emerald-50 px-2.5 py-1 rounded-md cursor-pointer active:scale-95 transition-transform shadow-2xs shrink-0"
              >
                Checkout ➔
              </button>
            </motion.div>
          )}

          {/* Authentic WhatsApp Vector SVG Floating Action Button */}
          <button
            onClick={() => setIsWhatsAppOpen(!isWhatsAppOpen)}
            className="absolute bottom-[72px] right-3.5 z-40 h-10 w-10 rounded-full bg-[#25D366] hover:bg-[#20ba5a] text-white flex items-center justify-center shadow-lg cursor-pointer active:scale-95 transition-transform"
            title="Open WhatsApp Restock Assistant"
          >
            <svg className="h-5 w-5 fill-current text-white" viewBox="0 0 24 24">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.501-.669-.51l-.57-.01c-.198 0-.52.074-.792.372s-1.04 1.016-1.04 2.479 1.065 2.876 1.213 3.074c.149.198 2.095 3.2 5.076 4.487.709.306 1.263.489 1.694.626.712.226 1.36.194 1.872.118.572-.085 1.758-.719 2.006-1.413.248-.695.248-1.29.173-1.414-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c-.001 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" />
            </svg>
            <span className="absolute top-0 right-0 h-2.5 w-2.5 bg-red-500 rounded-full border-2 border-white" />
          </button>

          {/* WhatsApp Chat Floating Bottom Sheet Overlay */}
          <AnimatePresence>
            {isWhatsAppOpen && (
              <div className="absolute inset-0 z-50 flex flex-col justify-end">
                {/* Backdrop Blur Overlay */}
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  onClick={() => setIsWhatsAppOpen(false)}
                  className="absolute inset-0 bg-black/40 backdrop-blur-xs cursor-pointer"
                />

                {/* iOS Bottom Sheet Container */}
                <motion.div
                  initial={{ y: "100%" }}
                  animate={{ y: 0 }}
                  exit={{ y: "100%" }}
                  transition={{ type: "spring", damping: 25, stiffness: 300 }}
                  className="relative w-full h-[85%] bg-[#E5DDD5] rounded-t-2xl flex flex-col shadow-2xl overflow-hidden border-t border-[#E5E7EB]"
                >
                  {/* Drag Handle Indicator */}
                  <div className="w-8 h-1 bg-slate-400/50 rounded-full mx-auto my-1.5 shrink-0" />

                  {/* WhatsApp Modal Header (Pure White with WhatsApp #25D366 Brand Touch) */}
                  <div className="bg-white border-b border-[#E5E7EB] px-3 py-2.5 flex items-center justify-between shadow-2xs shrink-0">
                    <div className="flex items-center gap-2.5">
                      <div className="h-7 w-7 rounded-lg bg-[#25D366] text-white flex items-center justify-center shrink-0 shadow-2xs">
                        <svg className="h-4 w-4 fill-current" viewBox="0 0 24 24">
                          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.501-.669-.51l-.57-.01c-.198 0-.52.074-.792.372s-1.04 1.016-1.04 2.479 1.065 2.876 1.213 3.074c.149.198 2.095 3.2 5.076 4.487.709.306 1.263.489 1.694.626.712.226 1.36.194 1.872.118.572-.085 1.758-.719 2.006-1.413.248-.695.248-1.29.173-1.414-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c-.001 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" />
                        </svg>
                      </div>
                      <div className="flex flex-col">
                        <span className="text-[12px] font-bold font-display text-[#252525] leading-none">WhatsApp Pantry Bot</span>
                        <span className="text-[8.5px] font-semibold text-[#128C7E] font-sans leading-none mt-0.5">online · (+91 99999 99999)</span>
                      </div>
                    </div>
                    <button
                      onClick={() => setIsWhatsAppOpen(false)}
                      className="p-1 text-[#64717E] hover:text-[#252525] cursor-pointer active:scale-95 transition-transform"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>

                  {/* Authentic WhatsApp Light Wallpaper Background (#E5DDD5 with Doodle Motif) */}
                  <div ref={chatContainerRef} className="flex-1 p-3 overflow-y-auto space-y-2.5 text-[10px] bg-[#E5DDD5] bg-[radial-gradient(#075e54_1px,transparent_1px)] [background-size:16px_16px] bg-opacity-[0.05]">
                    {messages.map((m, idx) => (
                      <div
                        key={idx}
                        className={clsx(
                          "flex flex-col max-w-[85%] rounded-xl p-2.5 shadow-2xs relative leading-snug text-[10px] font-sans",
                          m.sender === "user" ? "ml-auto bg-[#DCF8C6] text-[#075E54] border border-[#BBE3A5] rounded-tr-xs font-semibold" : "mr-auto bg-white text-[#252525] border border-[#E5E7EB] rounded-tl-xs"
                        )}
                      >
                        <div className="whitespace-pre-wrap">{m.text}</div>
                        <div className="flex items-center justify-end gap-1 mt-1 text-[8.5px] text-[#64717E] self-end font-medium">
                          <span>{m.timestamp}</span>
                          {m.sender === "user" && <CheckCheck className="h-3 w-3 text-[#34B7F1]" />}
                        </div>
                      </div>
                    ))}
                    {loading && (
                      <div className="mr-auto bg-white rounded-xl p-2 text-[9px] text-[#64717E] font-semibold border border-[#E5E7EB] shadow-2xs">
                        typing...
                      </div>
                    )}
                  </div>

                  {/* Quick Action Chips (Matching Phone Mockup Sub-tab Buttons) */}
                  <div className="px-3 py-2 bg-[#F0F0F0] border-t border-[#E5E7EB] flex gap-2 overflow-x-auto no-scrollbar shrink-0">
                    {["YES (Confirm ₹118)", "+ Add Bread (₹40)", "Skip This Week"].map((chip) => (
                      <button
                        key={chip}
                        onClick={() => handleSendMessage(chip)}
                        className="bg-white hover:bg-[#E8FADF] text-[#252525] hover:text-[#075E54] border border-[#E5E7EB] hover:border-[#25D366] rounded-lg px-2.5 py-1 text-[9px] font-extrabold shrink-0 cursor-pointer shadow-2xs active:scale-95 transition-all"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>

                  {/* Input Area */}
                  <div className="p-2.5 bg-[#F0F0F0] border-t border-[#E5E7EB] flex gap-2 items-center shrink-0">
                    <input
                      type="text"
                      value={input}
                      onChange={e => setInput(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && handleSendMessage()}
                      placeholder="Type message..."
                      className="flex-1 bg-white border border-[#E5E7EB] text-[#252525] rounded-xl px-3 py-1.5 text-[10px] font-medium focus:outline-none focus:border-[#25D366] font-sans"
                    />
                    <button
                      onClick={() => handleSendMessage()}
                      disabled={loading}
                      className="h-7 w-7 rounded-xl bg-[#25D366] hover:bg-[#20ba5a] text-white flex items-center justify-center cursor-pointer shrink-0 disabled:opacity-50 active:scale-95 transition-transform shadow-2xs"
                    >
                      <Send className="h-3.5 w-3.5 fill-current" />
                    </button>
                  </div>
                </motion.div>
              </div>
            )}
          </AnimatePresence>

          {/* Authentic Host Quick Commerce App Bottom Navigation Bar & Home Indicator */}
          <div className="bg-[#FFFFFF] border-t border-[#E5E7EB] pt-1.5 pb-2 flex flex-col items-center gap-1 z-40 shrink-0">
            <div className="w-full px-2 flex items-center justify-around text-[#64717E]">
              <button
                onClick={() => setHostTab("home")}
                className={clsx(
                  "flex flex-col items-center gap-0.5 text-[9px] font-bold font-display cursor-pointer transition-colors active:scale-95",
                  hostTab === "home" ? "text-[#252525]" : "text-[#64717E] hover:text-[#252525]"
                )}
              >
                <Home className="h-3.5 w-3.5" />
                <span>Home</span>
                {hostTab === "home" && <span className="h-1 w-1 rounded-full bg-[#252525]" />}
              </button>

              <button
                onClick={() => setHostTab("quick")}
                className={clsx(
                  "flex flex-col items-center gap-0.5 text-[9px] font-bold font-display cursor-pointer transition-colors active:scale-95",
                  hostTab === "quick" ? "text-[#252525]" : "text-[#64717E] hover:text-[#252525]"
                )}
              >
                <Zap className="h-3.5 w-3.5" />
                <span>Quick</span>
                {hostTab === "quick" && <span className="h-1 w-1 rounded-full bg-[#252525]" />}
              </button>

              <button
                onClick={() => setHostTab("prefill")}
                className={clsx(
                  "flex flex-col items-center gap-0.5 text-[9px] font-bold font-display cursor-pointer transition-colors relative active:scale-95",
                  hostTab === "prefill" ? "text-[#15803D] font-extrabold" : "text-[#64717E] hover:text-[#252525]"
                )}
              >
                <Droplet className="h-3.5 w-3.5 text-[#15803D] fill-emerald-100" />
                <span>PreFill</span>
                {hostTab === "prefill" && <span className="h-1 w-1 rounded-full bg-[#15803D]" />}
              </button>

              <button
                onClick={() => setHostTab("account")}
                className={clsx(
                  "flex flex-col items-center gap-0.5 text-[9px] font-bold font-display cursor-pointer transition-colors active:scale-95",
                  hostTab === "account" ? "text-[#252525]" : "text-[#64717E] hover:text-[#252525]"
                )}
              >
                <User className="h-3.5 w-3.5" />
                <span>Account</span>
                {hostTab === "account" && <span className="h-1 w-1 rounded-full bg-[#252525]" />}
              </button>
            </div>

            {/* Authentic Real iOS Home Indicator Bar */}
            <div className="w-20 h-1 bg-[#252525] rounded-full my-0.5" />
          </div>

        </div>
      </Iphone>
    </div>
  );
}
