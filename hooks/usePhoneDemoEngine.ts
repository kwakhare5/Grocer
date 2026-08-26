"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { toast } from "sonner";
import { StapleItem, WhatsAppMessage } from "../lib/types";
import { RECIPE_DB, PRICE_SIGNALS } from "../lib/mockData";
import { getSimulatedPantryStaples, processWhatsAppSimulationMessage } from "../lib/simulationEngine";

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
      text: "👋 Good morning, Karan!\n\nProphet ML detected your 1L Amul Taaza Milk will run out tomorrow morning (15% stock left).\n\nWould you like to restock now?",
      timestamp: "08:00 AM"
    }
  ]);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, orderStage, viewMode]);

  const depleting: StapleItem[] = useMemo(() => {
    return getSimulatedPantryStaples(restockedState, activeScenario);
  }, [restockedState, activeScenario]);

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

    setTimeout(() => {
      const result = processWhatsAppSimulationMessage(msgText, orderStage);
      setMessages(prev => [
        ...prev,
        {
          sender: "bot",
          text: result.reply,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      setOrderStage(result.nextStage);
      if (result.restockPantry) {
        setRestockedState(true);
        setItemQuantities({});
        toast.success("1-Tap Restock Confirmed! Household pantry restocked.");
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("order-placed"));
        }
      }
      setLoading(false);
    }, 600);
  }, [input, loading, orderStage]);

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
    chatContainerRef,
    priceSignals: PRICE_SIGNALS
  };
}
