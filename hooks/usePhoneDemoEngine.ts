"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { toast } from "sonner";
import {
  StapleItem,
  WhatsAppMessage,
  CustomerPersona,
  CustomerOrderPayload,
  CustomerOrderItem,
} from "../lib/types";
import { DEFAULT_CUSTOMER_PERSONA, DEFAULT_PANTRY_STAPLES } from "../lib/mockData";
import {
  getSimulatedPantryStaples,
  processWhatsAppSimulationMessage,
} from "../lib/simulationEngine";

export function usePhoneDemoEngine(
  activeScenario?: string,
  initialViewMode?: "whatsapp",
  activeCustomer: CustomerPersona = DEFAULT_CUSTOMER_PERSONA,
  onPlaceOrder?: (payload: CustomerOrderPayload) => void,
  onScheduleReminder?: (customerId: string, delayHours: number) => void,
  onSkipRestock?: (customerId: string, reason?: string) => void
) {
  const [hostTab, setHostTab] = useState<"home" | "quick" | "grocer" | "account">("grocer");
  const [userSelectedTab, setUserSelectedTab] = useState<"pantry" | null>(null);

  const grocerSubTab = userSelectedTab ?? "pantry";

  const [itemQuantities, setItemQuantities] = useState<Record<string, number>>({});
  const [viewMode, setViewMode] = useState<"whatsapp">("whatsapp");
  const [searchQuery, setSearchQuery] = useState("");
  const [isWhatsAppOpen, setIsWhatsAppOpen] = useState(false);
  const [restockedState, setRestockedState] = useState(false);
  const [addedBread, setAddedBread] = useState(false);
  const [orderStage, setOrderStage] = useState<
    "initial" | "item_added" | "breakdown" | "confirmed" | "reminded" | "skipped"
  >("initial");

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  // Initial personalized WhatsApp message
  const initialBotText = useMemo(() => {
    const firstName = activeCustomer.name.split(" ")[0];
    const item = activeCustomer.primaryDepletionItem || "Amul Taaza Milk 1L";
    return `Hi ${firstName}, your ${item} is almost finished. Tap below to order now.`;
  }, [activeCustomer.name, activeCustomer.primaryDepletionItem]);

  const [messages, setMessages] = useState<WhatsAppMessage[]>([
    {
      sender: "bot",
      text: initialBotText,
      timestamp: "08:00 AM",
    },
  ]);

  // Adjust state during render when active customer changes (React official pattern)
  const [prevCustomerId, setPrevCustomerId] = useState(activeCustomer.id);
  if (prevCustomerId !== activeCustomer.id) {
    setPrevCustomerId(activeCustomer.id);
    const firstName = activeCustomer.name.split(" ")[0];
    const item = activeCustomer.primaryDepletionItem || "Amul Taaza Milk 1L";
    setMessages([
      {
        sender: "bot",
        text: `Hi ${firstName}, your ${item} is almost finished. Tap below to order now.`,
        timestamp: "08:00 AM",
      },
    ]);
    setRestockedState(false);
    setAddedBread(false);
    setOrderStage("initial");
  }

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

  // Place order action
  const confirmOrder = useCallback(
    (paymentMethod: "UPI" | "COD" = "UPI") => {
      const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

      const primaryItemName = activeCustomer.primaryDepletionItem || "Amul Taaza Milk 1L";
      const staple = DEFAULT_PANTRY_STAPLES.find(
        (s) => s.name.toLowerCase() === primaryItemName.toLowerCase()
      ) || {
        id: "primary",
        name: primaryItemName,
        price: 66,
      };

      const items: CustomerOrderItem[] = [
        {
          productId: `prod-${staple.id}`,
          productName: staple.name,
          quantity: 1,
          priceINR: staple.price,
        },
      ];

      if (addedBread && !staple.name.toLowerCase().includes("bread")) {
        items.push({
          productId: "prod-wheat-bread",
          productName: "Whole Wheat Bread 400g",
          quantity: 1,
          priceINR: 50,
        });
      }

      const totalINR = items.reduce((sum, it) => sum + it.priceINR * it.quantity, 0);

      // Trigger order placement callback to update dark store state
      const payload: CustomerOrderPayload = {
        customerId: activeCustomer.id,
        customerName: activeCustomer.name,
        homeStoreCode: activeCustomer.homeStoreCode,
        homeStoreName: activeCustomer.homeStoreName,
        items,
        totalINR,
        paymentMethod,
      };

      onPlaceOrder?.(payload);

      setMessages((prev) => [
        ...prev,
        {
          sender: "user",
          text: `Paid ₹${totalINR} via ${paymentMethod === "UPI" ? "UPI" : "Cash on Delivery"}`,
          timestamp: timeStr,
        },
        {
          sender: "bot",
          text: `Order Confirmed! Arriving in 10 mins from ${activeCustomer.homeStoreName} Hub.`,
          timestamp: timeStr,
        },
      ]);

      setOrderStage("confirmed");
      setRestockedState(true);
      setItemQuantities({});
      toast.success(`Order Confirmed! Dispatched from ${activeCustomer.homeStoreName}`);
    },
    [activeCustomer, addedBread, onPlaceOrder]
  );

  // Remind Later action
  const scheduleReminder = useCallback(
    (delayHours = 24) => {
      const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      onScheduleReminder?.(activeCustomer.id, delayHours);

      setMessages((prev) => [
        ...prev,
        {
          sender: "user",
          text: `Remind me tomorrow at 08:00 AM`,
          timestamp: timeStr,
        },
        {
          sender: "bot",
          text: `Reminder set for tomorrow morning. We'll check back with you then.`,
          timestamp: timeStr,
        },
      ]);

      setOrderStage("reminded");
      toast.info(`Reminder set for tomorrow morning`);
    },
    [activeCustomer.id, onScheduleReminder]
  );

  // Skip Restock action
  const skipRestock = useCallback(
    (reason = "user_skipped") => {
      const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      onSkipRestock?.(activeCustomer.id, reason);

      setMessages((prev) => [
        ...prev,
        {
          sender: "user",
          text: `Skip restock for this week`,
          timestamp: timeStr,
        },
        {
          sender: "bot",
          text: `No problem, restock skipped for this week.`,
          timestamp: timeStr,
        },
      ]);

      setOrderStage("skipped");
      toast.info(`Restock alert paused for this cycle`);
    },
    [activeCustomer, onSkipRestock]
  );

  const handleSendMessage = useCallback(
    async (textToSend?: string) => {
      const msgText = textToSend || input;
      if (!msgText.trim() || loading) return;

      const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setMessages((prev) => [...prev, { sender: "user", text: msgText, timestamp: timeStr }]);
      if (!textToSend) setInput("");
      setLoading(true);

      setTimeout(() => {
        const firstName = activeCustomer.name.split(" ")[0];
        const primaryItem = activeCustomer.primaryDepletionItem || "Amul Taaza Milk 1L";
        const result = processWhatsAppSimulationMessage(msgText, orderStage, firstName, primaryItem);

        setMessages((prev) => [
          ...prev,
          {
            sender: "bot",
            text: result.reply,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          } as WhatsAppMessage,
        ]);

        setOrderStage(result.nextStage);

        if (result.restockPantry) {
          confirmOrder("UPI");
        } else if (result.isReminder) {
          onScheduleReminder?.(activeCustomer.id, 24);
        } else if (result.isSkip) {
          onSkipRestock?.(activeCustomer.id, "chat_skipped");
        }

        setLoading(false);
      }, 500);
    },
    [input, loading, activeCustomer, orderStage, confirmOrder, onScheduleReminder, onSkipRestock]
  );

  const totalCartItems = Object.values(itemQuantities).reduce((a, b) => a + b, 0);

  return {
    hostTab,
    setHostTab,
    grocerSubTab,
    setUserSelectedTab,
    itemQuantities,
    setItemQuantities,
    updateQuantity,
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
    confirmOrder,
    scheduleReminder,
    skipRestock,
    depleting,
    totalCartItems,
    viewMode,
    setViewMode,
    addedBread,
    setAddedBread,
    orderStage,
    setOrderStage,
    chatContainerRef,
  };
}
