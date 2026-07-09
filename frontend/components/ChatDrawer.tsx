"use client";

import { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, User, Bot } from "lucide-react";

interface Message {
  sender: "user" | "bot";
  text: string;
  timestamp: string;
}

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export default function ChatDrawer() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "bot",
      text: `${getGreeting()}, Karan! 👋\n\nWhat would you like to order? You can tell me item names (e.g. "2 milk and eggs") or tap 🔍 Check Stock to see what's running low.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Listen for open-whatsapp-chat event to open the drawer
  useEffect(() => {
    const handleOpenChat = () => setIsOpen(true);
    window.addEventListener("open-whatsapp-chat", handleOpenChat);
    return () => window.removeEventListener("open-whatsapp-chat", handleOpenChat);
  }, []);

  // Listen for scenario-switched event to reset the chat history
  useEffect(() => {
    const handleScenarioSwitched = () => {
      setMessages([
        {
          sender: "bot",
          text: `🔄 Inventory refreshed, Dev! What would you like to order? Or tap 🔍 Check Stock to see what's running low.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    };
    window.addEventListener("scenario-switched", handleScenarioSwitched);
    return () => window.removeEventListener("scenario-switched", handleScenarioSwitched);
  }, []);

  // Fetch latest pending alert on mount and dispatch push notification if pending
  useEffect(() => {
    async function loadLatestAlert() {
      try {
        const res = await fetch("http://localhost:8000/api/restock/demo_user_001/history");
        if (res.ok) {
          const data = await res.json();
          if (data.alerts && data.alerts.length > 0) {
            const latest = data.alerts[0];
            // If the alert is pending, show the real message as the starting point!
            if (latest.status === "pending" && latest.message) {
              const timeStr = latest.sent_at 
                ? new Date(latest.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
              
              setMessages([
                {
                  sender: "bot",
                  text: latest.message,
                  timestamp: timeStr
                }
              ]);

              // Dispatch push notification alert
              window.dispatchEvent(new CustomEvent("whatsapp-alert", { detail: { text: latest.message } }));
            }
          }
        }
      } catch (err) {
        console.warn("Failed to fetch latest alert for simulator", err);
      }
    }
    loadLatestAlert();
  }, []);

  interface SuggestionChip {
    label: string;
    value: string;
  }

  const getSuggestionChips = (): SuggestionChip[] => {
    if (loading) return [];
    
    // Find last bot message
    const lastMsg = [...messages].reverse().find(m => m.sender === "bot");
    if (!lastMsg) return [{ label: "🔍 Check Stock", value: "check" }];

    const txt = lastMsg.text;

    // Stage: confirm_add_to_cart — bot found items and is asking to add to cart
    if (txt.includes("Would you like to add them to your cart?") || txt.includes("add them to your cart")) {
      return [
        { label: "👍 YES, Add to Cart", value: "YES" },
        { label: "❌ NO, Cancel", value: "NO" }
      ];
    }

    // Stage: awaiting_confirm — cart is ready, asking to place the order
    if (txt.includes("Reply CONFIRM to place order") || txt.includes("CONFIRM to place")) {
      return [
        { label: "🚀 CONFIRM Order", value: "CONFIRM" },
        { label: "❌ CANCEL", value: "CANCEL" }
      ];
    }

    // Stage: awaiting_reply — bot shows low stock alert and asks if user wants to order
    if (txt.includes("Would you like to order them?") || txt.includes("reorder all, or tell me which ones")) {
      return [
        { label: "✅ YES, Order All", value: "YES" },
        { label: "❌ NO, Thanks", value: "NO" }
      ];
    }
    
    return [{ label: "🔍 Check Stock", value: "check" }];
  };

  const handleChipClick = async (value: string) => {
    if (loading) return;
    const timeString = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMessages(prev => [...prev, { sender: "user", text: value, timestamp: timeString }]);
    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/webhook/whatsapp", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          phone: "+919999999999", // Sandbox demo phone
          message: value
        })
      });

      if (!res.ok) {
        throw new Error("API Connection error");
      }

      const data = await res.json();
      setMessages(prev => [
        ...prev,
        {
          sender: "bot",
          text: data.response_message || "Received, processing.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);

      if (data.response_message) {
        window.dispatchEvent(new CustomEvent("whatsapp-alert", { detail: { text: data.response_message } }));
        if (data.response_message.includes("Order placed") || data.response_message.includes("Order #") || data.response_message.includes("✅ Order")) {
          window.dispatchEvent(new CustomEvent("order-placed"));
        }
        window.dispatchEvent(new CustomEvent("refresh-dashboard"));
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [
        ...prev,
        {
          sender: "bot",
          text: "⚠️ System Offline: Webhook connection refused. Make sure backend FastAPI is running on port 8000.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim() || loading) return;
    const userText = input;
    const timeString = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    setMessages(prev => [...prev, { sender: "user", text: userText, timestamp: timeString }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/webhook/whatsapp", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          phone: "+919999999999", // Sandbox demo phone
          message: userText
        })
      });

      if (!res.ok) {
        throw new Error("API Connection error");
      }

      const data = await res.json();
      setMessages(prev => [
        ...prev,
        {
          sender: "bot",
          text: data.response_message || "Received, processing.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);

      if (data.response_message) {
        window.dispatchEvent(new CustomEvent("whatsapp-alert", { detail: { text: data.response_message } }));
        if (data.response_message.includes("Order placed") || data.response_message.includes("Order #") || data.response_message.includes("✅ Order")) {
          window.dispatchEvent(new CustomEvent("order-placed"));
        }
        window.dispatchEvent(new CustomEvent("refresh-dashboard"));
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [
        ...prev,
        {
          sender: "bot",
          text: "⚠️ System Offline: Webhook connection refused. Make sure backend FastAPI is running on port 8000.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 font-mono">
      {/* ── Chat Float Button ────────────────────────────── */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="btn-premium-dark rounded-2xl p-4 flex items-center gap-3 transition-all duration-300 hover:scale-[1.03] active:scale-95 cursor-pointer"
        >
          <MessageSquare className="h-5 w-5" />
          <span className="text-xs font-bold uppercase tracking-wider pr-1 hidden sm:inline">WhatsApp Sandbox</span>
        </button>
      )}

      {/* ── Chat Widget Panel ────────────────────────────── */}
      {isOpen && (
        <div className="bg-[#FAFAF9] border border-border/80 rounded-2xl shadow-[0_12px_40px_-12px_rgba(0,0,0,0.15)] flex flex-col overflow-hidden w-80 sm:w-96 h-[460px] animate-in slide-in-from-bottom-5 duration-300">
          
          {/* Header */}
          <div className="border-b border-[#2D2A28] px-4 py-3 flex justify-between items-center bg-[#1C1917] text-white">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              <div className="flex flex-col">
                <span className="text-[10px] font-black tracking-wider uppercase font-display leading-none text-white">
                  WhatsApp Sandbox
                </span>
                <span className="text-[8px] text-neutral-400 font-medium font-mono mt-1 leading-none">
                  PreFill Assistant (+91 99999 99999)
                </span>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-neutral-400 hover:text-white transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Messages Container */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-white/70 backdrop-blur-sm">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex gap-2.5 max-w-[85%] ${
                  m.sender === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
                }`}
              >
                <div
                  className={`h-6 w-6 rounded-full flex items-center justify-center shrink-0 text-[10px] ${
                    m.sender === "user" ? "bg-[#005EEE]/10 text-[#005EEE]" : "bg-neutral-200 text-neutral-600"
                  }`}
                >
                  {m.sender === "user" ? <User className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
                </div>
                <div className="space-y-1">
                  <div
                    className={`rounded-xl px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap select-text shadow-sm ${
                      m.sender === "user"
                        ? "bg-gradient-to-b from-[#0F6CFF] to-[#005EEE] border border-[#0F6CFF] text-white"
                        : "bg-white dark:bg-[#1c1a18] border border-border text-foreground"
                    }`}
                  >
                    {m.text}
                  </div>
                  <div className="text-[8px] text-muted/80 text-right font-light px-1">
                    {m.timestamp}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex gap-2 max-w-[85%] mr-auto items-center">
                <div className="h-6 w-6 rounded-full bg-neutral-800 text-neutral-400 flex items-center justify-center shrink-0">
                  <Bot className="h-3.5 w-3.5" />
                </div>
                <div className="bg-surface border border-border rounded-lg px-3 py-2 text-xs text-muted">
                  <span className="inline-flex gap-1">
                    <span className="animate-bounce">●</span>
                    <span className="animate-bounce delay-100">●</span>
                    <span className="animate-bounce delay-200">●</span>
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Dynamic Suggestion Chips */}
          {!loading && (
            <div className="px-3 py-1.5 flex gap-1.5 overflow-x-auto bg-white/80 border-t border-border/40 shrink-0">
              {getSuggestionChips().map((chip, idx) => {
                const colors = [
                  { text: "#0066CC", bg: "#E6F5FF", border: "rgba(0,102,204,0.15)", hover: "#CCE6FF" }, // Blue
                  { text: "#D96B27", bg: "#FFF3E6", border: "rgba(217,107,39,0.15)", hover: "#FFEADA" }, // Orange
                  { text: "#0F9940", bg: "#E8F8EE", border: "rgba(15,153,64,0.15)", hover: "#D4F5DF" },  // Green
                ];
                const c = colors[idx % colors.length];
                return (
                  <button
                    key={chip.value}
                    onClick={() => handleChipClick(chip.value)}
                    className="font-bold text-[9px] uppercase px-3 py-1.5 rounded-md border cursor-pointer transition-all duration-200 shrink-0 select-none hover:scale-[1.02] active:scale-[0.98]"
                    style={{ 
                      color: c.text, 
                      borderColor: c.border, 
                      backgroundColor: c.bg 
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = c.hover}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = c.bg}
                  >
                    {chip.label}
                  </button>
                );
              })}
            </div>
          )}

          {/* Form Input */}
          <div className="p-3 border-t border-border/60 flex bg-white/90 gap-2">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSendMessage()}
              placeholder="e.g. '2 milk, eggs' or type 'check'..."
              className="flex-1 bg-neutral-50/50 border border-border/80 rounded-xl px-3 py-2 text-xs text-foreground placeholder:text-muted/60 focus:outline-none focus:border-[#005EEE] focus:ring-1 focus:ring-[#005EEE]/30 transition-all"
            />
            <button
              onClick={handleSendMessage}
              disabled={loading}
              className="bg-gradient-to-b from-[#0F6CFF] to-[#005EEE] border border-[#0F6CFF] text-white shadow-[0_1px_2px_rgba(0,0,0,0.15),inset_0_1px_0_rgba(255,255,255,0.1)] hover:from-[#297CFF] disabled:opacity-50 rounded-md p-2 flex items-center justify-center cursor-pointer transition-all duration-200"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
