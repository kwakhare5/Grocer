"use client";

import { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, User, Bot } from "lucide-react";

interface Message {
  sender: "user" | "bot";
  text: string;
  timestamp: string;
}

export default function ChatDrawer() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "bot",
      text: "🛒 Assistant initialized. I monitor your grocery consumption patterns. You can say 'YES' to reorder depleting items or request recipe ingredient checks.",
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

  // Fetch latest pending alert when sandbox is opened
  useEffect(() => {
    if (!isOpen) return;
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
            }
          }
        }
      } catch (err) {
        console.warn("Failed to fetch latest alert for simulator", err);
      }
    }
    loadLatestAlert();
  }, [isOpen]);

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
          className="bg-accent hover:bg-accent/90 text-white rounded-full p-4 shadow-[0_0_20px_rgba(255,102,0,0.3)] flex items-center gap-3 border border-accent/20 transition-all duration-300 hover:scale-105 active:scale-95"
        >
          <MessageSquare className="h-5 w-5" />
          <span className="text-xs font-bold uppercase tracking-wider pr-1 hidden sm:inline">WhatsApp Sandbox</span>
        </button>
      )}

      {/* ── Chat Widget Panel ────────────────────────────── */}
      {isOpen && (
        <div className="bg-white dark:bg-[#121110] border border-border rounded-2xl shadow-2xl w-80 sm:w-96 h-[460px] flex flex-col overflow-hidden animate-in slide-in-from-bottom-5 duration-300">
          
          {/* Header */}
          <div className="border-b border-border px-4 py-3 flex justify-between items-center bg-neutral-50 dark:bg-neutral-900/60">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-ok animate-pulse"></span>
              <span className="text-[10px] text-accent font-bold tracking-wider uppercase">
                WHATSAPP SANDBOX (+919999999999)
              </span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-muted hover:text-accent transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Messages Container */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-[#faf9f8] dark:bg-[#0c0b0a]">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex gap-2.5 max-w-[85%] ${
                  m.sender === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
                }`}
              >
                <div
                  className={`h-6 w-6 rounded-full flex items-center justify-center shrink-0 text-[10px] ${
                    m.sender === "user" ? "bg-accent/10 text-accent" : "bg-neutral-800 text-neutral-400"
                  }`}
                >
                  {m.sender === "user" ? <User className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
                </div>
                <div className="space-y-1">
                  <div
                    className={`rounded-lg px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap select-text border ${
                      m.sender === "user"
                        ? "bg-accent/5 border-accent/20 text-accent"
                        : "bg-white dark:bg-[#1c1a18] border-border text-foreground"
                    }`}
                  >
                    {m.text}
                  </div>
                  <div className="text-[9px] text-muted text-right font-light px-1">
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

          {/* Form Input */}
          <div className="p-3 border-t border-border flex bg-muted/20 gap-2">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSendMessage()}
              placeholder="Type YES, NO or ingredients..."
              className="flex-1 bg-white dark:bg-neutral-900 border border-border rounded-xl px-3 py-2 text-xs text-foreground placeholder:text-muted/70 focus:outline-none focus:border-accent transition-colors"
            />
            <button
              onClick={handleSendMessage}
              disabled={loading}
              className="bg-accent hover:bg-accent/90 disabled:opacity-50 text-white rounded p-2 transition-colors flex items-center justify-center"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
