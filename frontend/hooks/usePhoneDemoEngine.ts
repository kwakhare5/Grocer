"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Milk, Apple, Egg, Wheat, Droplet } from "lucide-react";
import { APIPrediction } from "../lib/api";
import { usePredictions } from "../lib/hooks";
import { toast } from "sonner";
import { StapleItem, Recipe, PriceSignal, WhatsAppMessage } from "../lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const RECIPE_DB: Record<string, Recipe> = {
  biryani: {
    dish: "Chicken Biryani",
    servings: 6,
    prepTime: "45 mins",
    ingredients: [
      { name: "Basmati Rice", needed: "600g", status: "have", category: "Grains" },
      { name: "Onions", needed: "400g", status: "have", category: "Produce" },
      { name: "Sunflower Oil", needed: "80ml", status: "low", price: 127, category: "Oils" },
      { name: "Fresh Cream", needed: "200ml", status: "missing", price: 55, category: "Dairy" },
    ]
  },
  dal: {
    dish: "Dal Tadka",
    servings: 4,
    prepTime: "25 mins",
    ingredients: [
      { name: "Toor Dal", needed: "300g", status: "have", category: "Pulses" },
      { name: "Tomatoes", needed: "200g", status: "low", price: 32, category: "Produce" },
      { name: "Cumin Seeds", needed: "15g", status: "have", category: "Spices" },
      { name: "Ghee", needed: "50g", status: "missing", price: 68, category: "Dairy" },
    ]
  },
  paneer: {
    dish: "Paneer Butter Masala",
    servings: 4,
    prepTime: "30 mins",
    ingredients: [
      { name: "Paneer", needed: "250g", status: "missing", price: 95, category: "Dairy" },
      { name: "Tomatoes", needed: "300g", status: "low", price: 48, category: "Produce" },
      { name: "Butter", needed: "50g", status: "missing", price: 45, category: "Dairy" },
      { name: "Cashews", needed: "40g", status: "have", category: "Nuts" },
    ]
  },
  oats: {
    dish: "Morning Oats Bowl",
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

export const PRICE_SIGNALS: PriceSignal[] = [
  { name: "Tomatoes 500g", current: 48, avg: 20, signal: "SPIKE", desc: "+140% vs 30d avg" },
  { name: "Sunflower Oil 1L", current: 98, avg: 127, signal: "DIP", desc: "-23% Stock Up" },
  { name: "Onions 1kg", current: 42, avg: 38, signal: "WATCH", desc: "+10% gradual rise" },
];

export function usePhoneDemoEngine(activeScenario?: string, initialViewMode?: "lockscreen" | "whatsapp" | "pantry") {
  const [hostTab, setHostTab] = useState<"home" | "quick" | "grocer" | "account">("grocer");
  const [userSelectedTab, setUserSelectedTab] = useState<"pantry" | "recipes" | "signals" | null>(null);

  const grocerSubTab = userSelectedTab ?? (
    activeScenario === "recipe_smart_cart" ? "recipes" :
    activeScenario === "price_dip_buy" ? "signals" : "pantry"
  );

  const [itemQuantities, setItemQuantities] = useState<Record<string, number>>({});
  const [viewMode, setViewMode] = useState<"lockscreen" | "whatsapp" | "pantry">(initialViewMode || "lockscreen");
  const [selectedRecipe, setSelectedRecipe] = useState<"biryani" | "dal" | "paneer" | "oats">("biryani");
  const [orderedRecipe, setOrderedRecipe] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isWhatsAppOpen, setIsWhatsAppOpen] = useState(false);
  const [restockedState, setRestockedState] = useState(false);
  const [addedBread, setAddedBread] = useState(false);
  const [orderStage, setOrderStage] = useState<"initial" | "item_added" | "breakdown" | "confirmed">("initial");
  const [selectedIngredients, setSelectedIngredients] = useState<Record<string, boolean>>(() => {
    const recipe = RECIPE_DB.biryani;
    const initial: Record<string, boolean> = {};
    recipe.ingredients.forEach(ing => {
      if (ing.status !== "have") {
        initial[ing.name] = true;
      }
    });
    return initial;
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<WhatsAppMessage[]>([
    {
      sender: "bot",
      text: "👋 Good morning, Karan!\n\nProphet ML detected your 1L Amul Milk will run out tomorrow morning (15% stock left).\n\nWould you like to restock now?",
      timestamp: "08:00 AM"
    }
  ]);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, orderStage, viewMode]);

  const { predictionsData } = usePredictions("demo_user_001");

  const depleting: StapleItem[] = useMemo(() => {
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
      { id: "milk", name: "Fresh Milk 1L", days: 1, fillPct: 15, avg: "0.48L/day", icon: Milk, category: "dairy" },
      { id: "tomatoes", name: "Tomatoes 500g", days: 1, fillPct: 14, avg: "140g/day", icon: Apple, category: "produce" },
      { id: "eggs", name: "Farm Eggs 12pcs", days: 2, fillPct: 35, avg: "2.4/day", icon: Egg, category: "poultry" },
      { id: "bread", name: "Wheat Bread 400g", days: 3, fillPct: 65, avg: "0.24/day", icon: Wheat, category: "bakery" },
    ];
  }, [predictionsData, restockedState]);

  const updateQuantity = useCallback((name: string, delta: number, e?: React.MouseEvent) => {
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
  }, []);

  const handleSendMessage = useCallback(async (textToSend?: string) => {
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
          setLoading(false);
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
  }, [input, loading]);

  const handleSelectRecipe = useCallback((key: "biryani" | "dal" | "paneer" | "oats") => {
    setSelectedRecipe(key);
    setOrderedRecipe(false);
    const recipe = RECIPE_DB[key];
    const initial: Record<string, boolean> = {};
    recipe.ingredients.forEach(ing => {
      if (ing.status !== "have") {
        initial[ing.name] = true;
      }
    });
    setSelectedIngredients(initial);
  }, []);

  const toggleIngredientSelection = useCallback((name: string) => {
    setSelectedIngredients(prev => ({ ...prev, [name]: !prev[name] }));
  }, []);

  const handleAddRecipeMissingToCart = useCallback(() => {
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
  }, [selectedRecipe, selectedIngredients]);

  const totalCartItems = Object.values(itemQuantities).reduce((a, b) => a + b, 0);

  return {
    hostTab,
    setHostTab,
    grocerSubTab,
    setUserSelectedTab,
    itemQuantities,
    setItemQuantities,
    updateQuantity,
    selectedRecipe,
    handleSelectRecipe,
    orderedRecipe,
    selectedIngredients,
    toggleIngredientSelection,
    handleAddRecipeMissingToCart,
    searchQuery,
    setSearchQuery,
    isWhatsAppOpen,
    setIsWhatsAppOpen,
    restockedState,
    setRestockedState,
    messages,
    input,
    setInput,
    loading,
    handleSendMessage,
    depleting,
    totalCartItems,
    viewMode,
    setViewMode,
    addedBread,
    setAddedBread,
    orderStage,
    setOrderStage,
    chatContainerRef
  };
}
