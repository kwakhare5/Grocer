"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { 
  ShoppingBag, 
  MessageSquare, 
  CheckCheck, 
  Send, 
  ShoppingCart,
  Zap,
  ChefHat,
  Tag,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  XCircle,
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
  Sparkles,
  Signal,
  Wifi,
  Clock,
  ChevronRight,
  Flame,
  Home,
  User,
  Zap as Flash,
  X
} from "lucide-react";
import { APIPrediction } from "../lib/api";
import { usePredictions } from "../lib/hooks";
import { toast } from "sonner";
import { Iphone } from "./ui/iphone";
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
    ]
  }
};

const PRICE_SIGNALS = [
  { name: "Tomatoes 500g", current: 48, avg: 20, signal: "SPIKE", desc: "+140% vs 30d avg", sparkline: [20, 22, 28, 35, 48] },
  { name: "Sunflower Oil 1L", current: 98, avg: 127, signal: "DIP", desc: "-23% Stock Up", sparkline: [127, 120, 110, 102, 98] },
  { name: "Onions 1kg", current: 42, avg: 38, signal: "WATCH", desc: "+10% gradual rise", sparkline: [38, 39, 40, 41, 42] },
];

export default function PhoneMockup({ activeScenario }: PhoneMockupProps) {
  // Host App Bottom Navigation Tabs: "home" | "quick" | "prefill" | "account"
  const [hostTab, setHostTab] = useState<"home" | "quick" | "prefill" | "account">("prefill");
  
  const [itemQuantities, setItemQuantities] = useState<Record<string, number>>({});
  const [selectedRecipe, setSelectedRecipe] = useState<"biryani" | "dal">("biryani");
  const [orderedRecipe, setOrderedRecipe] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isWhatsAppOpen, setIsWhatsAppOpen] = useState(false);

  // WhatsApp Chat State
  const [messages, setMessages] = useState([
    {
      sender: "bot",
      text: "Good morning, Karan.\n\nYour milk & tomatoes will run out in 24 hrs. Tap 'YES' to reorder instantly.",
      timestamp: "08:00 AM"
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const { predictionsData } = usePredictions("demo_user_001");

  const depleting = useMemo(() => {
    if (predictionsData?.predictions && predictionsData.predictions.length > 0) {
      return predictionsData.predictions.map((p: APIPrediction) => ({
        id: p.item_id,
        name: p.item_name.split(" — ")[0],
        days: p.days_remaining !== null ? Math.round(p.days_remaining) : 10,
        fillPct: p.stock_fill_percent !== undefined ? Math.round(p.stock_fill_percent) : 100,
        avg: `${p.avg_daily_consumption.toFixed(2)}/day`,
        icon: p.category === "dairy" ? Milk : p.category === "produce" ? Apple : p.category === "bakery" ? Wheat : Droplet
      }));
    }
    return [
      { id: "milk", name: "Fresh Milk 1L", days: 1, fillPct: 20, avg: "0.48L/day", icon: Milk },
      { id: "tomatoes", name: "Tomatoes 500g", days: 1, fillPct: 14, avg: "140g/day", icon: Apple },
      { id: "eggs", name: "Farm Eggs 12pcs", days: 2, fillPct: 35, avg: "2.4/day", icon: Egg },
      { id: "bread", name: "Wheat Bread 400g", days: 3, fillPct: 65, avg: "0.24/day", icon: Wheat },
    ];
  }, [predictionsData]);

  useEffect(() => {
    const handleScenarioSwitched = (e: any) => {
      const scenario = e.detail?.scenario || "refreshed";
      setMessages([
        {
          sender: "bot",
          text: `🔄 Scenario updated to ${scenario.toUpperCase()}. Pantry state recalculated. What would you like to reorder?`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    };
    window.addEventListener("scenario-switched", handleScenarioSwitched);
    return () => window.removeEventListener("scenario-switched", handleScenarioSwitched);
  }, []);

  useEffect(() => {
    if (isWhatsAppOpen) {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, loading, isWhatsAppOpen]);

  const updateQuantity = (name: string, delta: number, e: React.MouseEvent) => {
    e.stopPropagation();
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

    try {
      const res = await fetch(`${API_BASE}/api/webhook/whatsapp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: "+919999999999", message: msgText })
      });

      if (!res.ok) throw new Error("API error");

      const data = await res.json();
      setMessages(prev => [
        ...prev,
        {
          sender: "bot",
          text: data.response_message || "Received, processing.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);

      if (data.response_message?.includes("Order placed")) {
        window.dispatchEvent(new CustomEvent("order-placed"));
      }
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          sender: "bot",
          text: "Order intent confirmed.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const currentRecipe = RECIPE_DB[selectedRecipe];
  const recipeMissing = currentRecipe.ingredients.filter(i => i.status !== "have");
  const recipeTotal = recipeMissing.reduce((acc, i) => acc + (i.price || 0), 0);

  const filteredStaples = depleting.filter(item => 
    item.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col items-center gap-2 w-[305px] aspect-[71.5/149.6] shrink-0 mx-auto select-none">
      
      {/* Magic UI iPhone Mockup Frame */}
      <Iphone className="drop-shadow-2xl w-full h-full">
        <div className="w-full h-full bg-slate-50 flex flex-col relative pt-10 pb-4 overflow-hidden select-none">
          
          {/* Authentic Real iOS Top Status Bar */}
          <div className="absolute top-0 left-0 right-0 h-10 px-6 flex items-center justify-between z-40 bg-white/90 backdrop-blur-md text-slate-900 font-sans border-b border-slate-100">
            <span className="text-[12px] font-bold tracking-tight">9:41</span>
            
            <div className="flex items-center gap-2">
              <Signal className="h-3 w-3 fill-slate-900 stroke-none" />
              <Wifi className="h-3.5 w-3.5" />
              <div className="flex items-center gap-1">
                <span className="text-[9px] font-bold font-mono">92%</span>
                <div className="w-5 h-2.5 rounded-sm border border-slate-900 p-0.5 flex items-center">
                  <div className="h-full w-[85%] bg-emerald-500 rounded-2xs" />
                </div>
              </div>
            </div>
          </div>

          {/* Clean App Header */}
          <div className="bg-white border-b border-slate-200/80 px-3.5 pt-2 pb-2.5 flex flex-col gap-2 z-30 shrink-0 shadow-2xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900 font-display">
                <MapPin className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                <span className="truncate max-w-[180px]">Green Park · 10 MINS</span>
              </div>
              <div className="h-6 w-6 rounded-full bg-slate-900 text-white font-bold text-[10px] flex items-center justify-center font-display shadow-2xs">
                K
              </div>
            </div>

            {/* App Search Bar */}
            <div className="bg-slate-100 rounded-xl px-3 py-1.5 flex items-center gap-2 border border-slate-200">
              <Search className="h-3.5 w-3.5 text-slate-400 shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search milk, atta, tomatoes..."
                className="bg-transparent text-[11px] font-medium text-slate-900 focus:outline-none w-full placeholder:text-slate-400 font-sans"
              />
            </div>
          </div>

          {/* MAIN SCREEN CONTENT AREA */}
          <div className="flex-1 overflow-y-auto no-scrollbar relative flex flex-col">
            
            {/* TAB: PREFILL SMART PANTRY MODULE (Unified View) */}
            {hostTab === "prefill" && (
              <div className="p-3 flex flex-col gap-3.5 pb-16">
                
                {/* 1. Smart Restock Overview Banner */}
                <div className="bg-slate-900 text-white rounded-xl p-3 flex flex-col gap-1 shadow-2xs">
                  <div className="flex items-center justify-between text-[9px] font-bold font-mono">
                    <span className="bg-emerald-600 text-white px-2 py-0.5 rounded font-bold">
                      SMART PANTRY ACTIVE
                    </span>
                    <span className="text-slate-300">AUTO-RESTOCK</span>
                  </div>
                  <span className="text-xs font-bold font-display leading-tight">PreFill Pantry Module</span>
                  <span className="text-[9.5px] text-slate-400 font-medium">Tracking household consumption & depletion rates</span>
                </div>

                {/* 2. Stockout Warning Banner */}
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-2.5 flex items-start gap-2 text-slate-900">
                  <Zap className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
                  <div className="flex flex-col">
                    <span className="text-[10px] font-bold font-display">Low Stock Warning</span>
                    <span className="text-[9px] text-slate-600 font-medium">Milk & Tomatoes predicted low in 24 hours.</span>
                  </div>
                </div>

                {/* 3. Pantry Items Depletion List */}
                <div className="flex flex-col gap-2">
                  <span className="text-[9px] font-bold uppercase tracking-wider text-slate-500 font-display">Pantry Stock Depletion</span>
                  
                  {filteredStaples.map((item) => {
                    const qty = itemQuantities[item.name] || 0;
                    const isDanger = item.fillPct < 25;
                    const isWarning = item.fillPct >= 25 && item.fillPct < 50;
                    const IconComponent = item.icon;

                    return (
                      <div key={item.id} className="bg-white rounded-xl border border-slate-200/90 p-2.5 flex items-center justify-between gap-2 shadow-2xs">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="p-2 rounded-lg bg-slate-100 text-slate-700 shrink-0 border border-slate-200">
                            <IconComponent className="h-4 w-4" />
                          </div>
                          <div className="flex flex-col min-w-0">
                            <span className="font-bold text-[11px] text-slate-900 font-display truncate">{item.name}</span>
                            
                            <div className="flex items-center gap-2 mt-1">
                              <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200">
                                <div 
                                  className={clsx("h-full rounded-full transition-all duration-500", isDanger ? "bg-red-500" : isWarning ? "bg-amber-500" : "bg-emerald-500")}
                                  style={{ width: `${item.fillPct}%` }}
                                />
                              </div>
                              <span className={clsx(isDanger ? "pill-subtle-red" : isWarning ? "pill-subtle-yellow" : "pill-subtle-green")}>
                                {item.fillPct}%
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Interactive Quantity Selector */}
                        {qty > 0 ? (
                          <div className="flex items-center gap-2 bg-slate-900 text-white rounded-lg px-2 py-1 shrink-0">
                            <button onClick={(e) => updateQuantity(item.name, -1, e)} className="p-0.5 cursor-pointer hover:text-slate-300 active:scale-95 transition-transform">
                              <Minus className="h-3 w-3" />
                            </button>
                            <span className="text-[10px] font-bold font-mono px-0.5">{qty}</span>
                            <button onClick={(e) => updateQuantity(item.name, 1, e)} className="p-0.5 cursor-pointer hover:text-slate-300 active:scale-95 transition-transform">
                              <Plus className="h-3 w-3" />
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={(e) => updateQuantity(item.name, 1, e)}
                            className="h-7 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-[9.5px] font-bold font-display cursor-pointer flex items-center gap-1 border border-slate-900 shrink-0 active:scale-[0.97] transition-transform"
                          >
                            <ShoppingCart className="h-3 w-3" />
                            <span>ADD</span>
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* 4. Recipe Ingredient Checker Section */}
                <div className="flex flex-col gap-2 pt-1 border-t border-slate-200">
                  <div className="flex items-center justify-between">
                    <span className="text-[9px] font-bold uppercase tracking-wider text-slate-500 font-display flex items-center gap-1">
                      <ChefHat className="h-3.5 w-3.5 text-slate-700" /> Recipe Checker
                    </span>
                    <div className="flex gap-1">
                      <button
                        onClick={() => { setSelectedRecipe("biryani"); setOrderedRecipe(false); }}
                        className={clsx("px-2 py-0.5 rounded text-[8.5px] font-bold font-display cursor-pointer transition-colors active:scale-95", selectedRecipe === "biryani" ? "bg-slate-900 text-white" : "bg-slate-200 text-slate-700")}
                      >
                        Biryani
                      </button>
                      <button
                        onClick={() => { setSelectedRecipe("dal"); setOrderedRecipe(false); }}
                        className={clsx("px-2 py-0.5 rounded text-[8.5px] font-bold font-display cursor-pointer transition-colors active:scale-95", selectedRecipe === "dal" ? "bg-slate-900 text-white" : "bg-slate-200 text-slate-700")}
                      >
                        Dal Makhani
                      </button>
                    </div>
                  </div>

                  <div className="bg-white rounded-xl border border-slate-200 p-2.5 flex flex-col gap-2 shadow-2xs">
                    <span className="font-bold text-[11px] text-slate-900 font-display">{currentRecipe.dish} ({currentRecipe.servings} servings)</span>
                    <div className="flex flex-col divide-y divide-slate-100">
                      {currentRecipe.ingredients.map((ing) => (
                        <div key={ing.name} className="py-1 flex items-center justify-between text-[9.5px]">
                          <div className="flex items-center gap-1.5 min-w-0">
                            {ing.status === "have" && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />}
                            {ing.status === "low" && <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />}
                            {ing.status === "missing" && <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />}
                            <span className="font-medium text-slate-800 truncate">{ing.name} ({ing.needed})</span>
                          </div>
                          <span className={clsx(ing.status === "have" ? "pill-subtle-green" : ing.status === "low" ? "pill-subtle-yellow" : "pill-subtle-red")}>
                            {ing.status === "have" ? "Stocked" : ing.status === "low" ? "Low" : `₹${ing.price}`}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {orderedRecipe ? (
                    <div className="bg-emerald-50 border border-emerald-200 p-2 rounded-xl text-center text-[10px] font-bold text-emerald-700 font-display">
                      ✓ Ingredients Arriving in 10 mins!
                    </div>
                  ) : (
                    recipeMissing.length > 0 && (
                      <button
                        onClick={() => setOrderedRecipe(true)}
                        className="bg-slate-900 text-white p-2.5 rounded-xl flex items-center justify-between cursor-pointer hover:bg-slate-800 shadow-2xs active:scale-[0.98] transition-transform"
                      >
                        <div className="flex flex-col text-left">
                          <span className="text-[8.5px] text-slate-400 font-medium">Fill Missing Ingredients</span>
                          <span className="text-[11px] font-bold font-display">Total ₹{recipeTotal}</span>
                        </div>
                        <span className="bg-emerald-600 text-white px-2.5 py-1 rounded-lg text-[9px] font-bold font-display flex items-center gap-1">
                          Order Now <ChevronRight className="h-3 w-3" />
                        </span>
                      </button>
                    )
                  )}
                </div>

                {/* 5. Commodity Price Signals Section */}
                <div className="flex flex-col gap-2 pt-1 border-t border-slate-200">
                  <span className="text-[9px] font-bold uppercase tracking-wider text-slate-500 font-display flex items-center gap-1">
                    <Tag className="h-3.5 w-3.5 text-slate-700" /> Market Price Signals
                  </span>

                  <div className="flex flex-col gap-2">
                    {PRICE_SIGNALS.map((p) => {
                      const isSpike = p.signal === "SPIKE";
                      const isDip = p.signal === "DIP";

                      return (
                        <div key={p.name} className="bg-white rounded-xl border border-slate-200 p-2.5 flex flex-col gap-1 shadow-2xs">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-[10.5px] text-slate-900 font-display">{p.name}</span>
                            <span className={clsx(isSpike ? "pill-subtle-red" : isDip ? "pill-subtle-green" : "pill-subtle-yellow")}>
                              {p.signal}
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-[9px] pt-1 border-t border-slate-100">
                            <span className="font-bold text-slate-800 font-display">Today: ₹{p.current} <span className="text-slate-400 font-normal">(Avg ₹{p.avg})</span></span>
                            <span className={clsx("font-bold flex items-center gap-0.5", isSpike ? "text-red-600" : isDip ? "text-emerald-600" : "text-amber-600")}>
                              {isSpike ? <TrendingUp className="h-2.5 w-2.5" /> : <TrendingDown className="h-2.5 w-2.5" />}
                              {p.desc}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

              </div>
            )}

            {/* TAB: OTHER HOST TABS (Home marketplace) */}
            {hostTab !== "prefill" && (
              <div className="p-3 flex flex-col gap-3 pb-14">
                <div className="bg-slate-900 text-white rounded-xl p-3 flex flex-col gap-2 shadow-2xs">
                  <span className="text-xs font-bold font-display">Quick Commerce Store</span>
                  <span className="text-[9.5px] text-slate-300 font-medium">Browse 10-minute grocery delivery items</span>
                  <button
                    onClick={() => setHostTab("prefill")}
                    className="mt-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 px-3 py-1.5 rounded-xl text-[10px] font-bold font-display cursor-pointer flex items-center justify-between active:scale-[0.98] transition-all"
                  >
                    <span>Open PreFill Pantry</span>
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}

          </div>

          {/* Floating Cart Drawer Banner */}
          {hostTab === "prefill" && totalCartItems > 0 && (
            <div className="absolute bottom-12 left-3 right-14 bg-slate-900 text-white rounded-xl p-2 flex items-center justify-between shadow-lg border border-slate-800 z-30">
              <div className="flex items-center gap-1.5 text-[9.5px] font-bold font-display">
                <ShoppingCart className="h-3.5 w-3.5 text-emerald-400" />
                <span>{totalCartItems} item{totalCartItems > 1 ? "s" : ""} added</span>
              </div>
              <span className="text-[9px] font-extrabold font-display bg-emerald-600 px-2 py-0.5 rounded">Checkout ➔</span>
            </div>
          )}

          {/* Right Bottom Floating WhatsApp Action Button (FAB) */}
          <button
            onClick={() => setIsWhatsAppOpen(!isWhatsAppOpen)}
            className="absolute bottom-12 right-3 z-40 bg-[#25D366] hover:bg-[#20ba5a] text-white p-2.5 rounded-full shadow-lg border border-emerald-400 cursor-pointer active:scale-[0.93] transition-transform flex items-center justify-center"
            title="Open WhatsApp Chat Assistant"
          >
            <MessageSquare className="h-4 w-4 fill-current" />
          </button>

          {/* WhatsApp Chat Floating Drawer Overlay */}
          {isWhatsAppOpen && (
            <div className="absolute inset-0 top-10 bg-[#E5DDD5] z-50 flex flex-col transition-all duration-200 ease-out">
              {/* WhatsApp Header */}
              <div className="bg-[#075E54] text-white px-3 py-2 flex items-center justify-between shadow-2xs shrink-0">
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded-full bg-emerald-700 flex items-center justify-center text-[10px] font-bold border border-emerald-400/40">
                    <MessageSquare className="h-3 w-3 text-emerald-100" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[10.5px] font-bold font-display leading-none">WhatsApp Pantry Bot</span>
                    <span className="text-[7.5px] text-emerald-200 font-mono leading-none mt-0.5">online · (+91 99999 99999)</span>
                  </div>
                </div>
                <button
                  onClick={() => setIsWhatsAppOpen(false)}
                  className="p-1 text-emerald-200 hover:text-white cursor-pointer active:scale-95"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Chat Messages */}
              <div className="flex-1 p-2.5 overflow-y-auto space-y-2 text-[9.5px] bg-[radial-gradient(#075e54_1px,transparent_1px)] [background-size:16px_16px] bg-opacity-5">
                {messages.map((m, idx) => (
                  <div
                    key={idx}
                    className={clsx(
                      "flex flex-col max-w-[85%] rounded-lg px-2.5 py-1.5 shadow-2xs relative leading-snug border border-slate-300/40 text-[9.5px]",
                      m.sender === "user" ? "ml-auto bg-[#DCF8C6] text-slate-900 rounded-tr-none" : "mr-auto bg-white text-slate-900 rounded-tl-none"
                    )}
                  >
                    <div className="whitespace-pre-wrap">{m.text}</div>
                    <div className="flex items-center justify-end gap-1 mt-0.5 text-[7.5px] text-slate-500 self-end">
                      <span>{m.timestamp}</span>
                      {m.sender === "user" && <CheckCheck className="h-3 w-3 text-sky-500" />}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="mr-auto bg-white rounded-lg px-2.5 py-1 text-[8.5px] text-slate-500 font-medium border border-slate-200">
                    typing...
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Quick Action Chips */}
              <div className="px-2 py-1 bg-[#F0F0F0] border-t border-slate-300 flex gap-1 overflow-x-auto no-scrollbar shrink-0">
                {["YES", "NO", "check"].map((chip) => (
                  <button
                    key={chip}
                    onClick={() => handleSendMessage(chip)}
                    className="font-bold text-[7.5px] uppercase px-2 py-0.5 rounded bg-white text-[#075E54] border border-[#075E54]/30 shrink-0 cursor-pointer hover:bg-emerald-50 active:scale-95 transition-transform"
                  >
                    {chip === "check" ? "Check" : chip}
                  </button>
                ))}
              </div>

              {/* Input Area */}
              <div className="p-1.5 bg-[#F0F0F0] border-t border-slate-300 flex gap-1.5 items-center shrink-0">
                <input
                  type="text"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSendMessage()}
                  placeholder="Type message..."
                  className="flex-1 bg-white border border-slate-300 rounded-full px-2.5 py-0.5 text-[9px] focus:outline-none"
                />
                <button
                  onClick={() => handleSendMessage()}
                  disabled={loading}
                  className="h-5.5 w-5.5 rounded-full bg-[#075E54] text-white flex items-center justify-center cursor-pointer shrink-0 disabled:opacity-50 active:scale-95 transition-transform"
                >
                  <Send className="h-2.5 w-2.5 fill-current" />
                </button>
              </div>
            </div>
          )}

          {/* Authentic Host Quick Commerce App Bottom Navigation Bar */}
          <div className="bg-white/95 backdrop-blur-md border-t border-slate-200/90 px-2 py-1.5 flex items-center justify-around z-40 shrink-0 text-slate-600">
            <button
              onClick={() => setHostTab("home")}
              className={clsx(
                "flex flex-col items-center gap-0.5 text-[9px] font-bold font-display cursor-pointer transition-colors active:scale-95",
                hostTab === "home" ? "text-slate-900" : "text-slate-400 hover:text-slate-700"
              )}
            >
              <Home className="h-4 w-4" />
              <span>Home</span>
            </button>

            <button
              onClick={() => setHostTab("quick")}
              className={clsx(
                "flex flex-col items-center gap-0.5 text-[9px] font-bold font-display cursor-pointer transition-colors active:scale-95",
                hostTab === "quick" ? "text-slate-900" : "text-slate-400 hover:text-slate-700"
              )}
            >
              <Flash className="h-4 w-4" />
              <span>Quick</span>
            </button>

            <button
              onClick={() => setHostTab("prefill")}
              className={clsx(
                "flex flex-col items-center gap-0.5 text-[9px] font-bold font-display cursor-pointer transition-colors relative active:scale-95",
                hostTab === "prefill" ? "text-emerald-700 font-extrabold" : "text-slate-400 hover:text-slate-700"
              )}
            >
              <Sparkles className="h-4 w-4 text-emerald-600 fill-emerald-100" />
              <span>PreFill</span>
            </button>

            <button
              onClick={() => setHostTab("account")}
              className={clsx(
                "flex flex-col items-center gap-0.5 text-[9px] font-bold font-display cursor-pointer transition-colors active:scale-95",
                hostTab === "account" ? "text-slate-900" : "text-slate-400 hover:text-slate-700"
              )}
            >
              <User className="h-4 w-4" />
              <span>Account</span>
            </button>
          </div>

          {/* Authentic Real iOS Home Indicator Bar */}
          <div className="w-full shrink-0 pt-1 pb-0.5 bg-white z-40 flex items-center justify-center">
            <div className="w-28 h-1 bg-slate-900 rounded-full" />
          </div>

        </div>
      </Iphone>
    </div>
  );
}
