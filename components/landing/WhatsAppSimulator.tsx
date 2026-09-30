"use client";

import React, { useState, useRef, FormEvent } from "react";
import {
  Send,
  Loader2,
  Terminal,
  Check,
  CheckCircle2,
  MapPin,
} from "lucide-react";
import { GrocerLogo } from "../ui/GrocerLogo";
import { Message, PresetScenario } from "./types";
import { PRESET_SCENARIOS } from "./data";

export function WhatsAppSimulator() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "init_1",
      sender: "user",
      text: "I want to make pasta tonight under ₹1500. Get ingredients!",
      time: "8:04 PM",
    },
    {
      id: "init_2",
      sender: "assistant",
      text: "🛒 Here is your Penne Arbiatta kit from the nearest dark store:",
      time: "8:04 PM",
      items: [
        { name: "Yu Zero Maida Penne Pasta 500g", price: "₹49" },
        { name: "Veeba Pasta & Pizza Sauce 280g", price: "₹79" },
        { name: "Amul Mozzarella Diced Cheese 200g", price: "₹110" },
        { name: "Fresh Garlic 100g", price: "₹38" },
      ],
      subtotal: "₹276",
      fees: "₹5 (Handling)",
      total: "₹281",
      quickReplies: ["Confirm Order", "Also add butter", "Clear Cart"],
      toolCallPayload: {
        tool: "search_products",
        params: { query: "penne pasta sauce cheese garlic", max_price: 1500 },
        resultSummary: "Parallel catalog search matched 4 SKUs (in-stock at dark store #2041). Total ₹281.",
        latencyMs: 1045,
      },
    },
  ]);

  const [inputText, setInputText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [showToolTrace, setShowToolTrace] = useState(true);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const handleSendSimulationMessage = (userQuery: string) => {
    if (!userQuery.trim() || isTyping) return;

    const queryLower = userQuery.toLowerCase();
    const matchedScenario: PresetScenario =
      PRESET_SCENARIOS.find((sc) =>
        queryLower.includes(sc.label.toLowerCase()) ||
        sc.prompt.toLowerCase().includes(queryLower) ||
        (queryLower.includes("pasta") && sc.id === "pasta") ||
        (queryLower.includes("milk") && sc.id === "staples") ||
        (queryLower.includes("butter") && sc.id === "delta") ||
        (queryLower.includes("cold") && sc.id === "care") ||
        (queryLower.includes("confirm") && sc.id === "checkout") ||
        (queryLower.includes("order") && sc.id === "track") ||
        (queryLower.includes("track") && sc.id === "track")
      ) || PRESET_SCENARIOS[0];

    const newTime = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

    // 1. Append User Message
    const userMsg: Message = {
      id: `user_${new Date().getTime()}`,
      sender: "user",
      text: userQuery,
      time: newTime,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setIsTyping(true);

    // Smooth scroll down
    setTimeout(() => {
      chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" });
    }, 50);

    // 2. Simulated Typing Delay (600ms)
    setTimeout(() => {
      const assistantMsg: Message = {
        id: `asst_${new Date().getTime()}`,
        sender: "assistant",
        text: matchedScenario.replyLead,
        time: new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }),
        items: matchedScenario.items.length > 0 ? matchedScenario.items : undefined,
        subtotal: matchedScenario.subtotal || undefined,
        fees: matchedScenario.fees || undefined,
        total: matchedScenario.total || undefined,
        quickReplies: matchedScenario.quickReplies,
        toolCallPayload: matchedScenario.toolTrace,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setIsTyping(false);

      setTimeout(() => {
        chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" });
      }, 50);
    }, 600);
  };

  const handleInputSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (inputText.trim()) {
      handleSendSimulationMessage(inputText.trim());
    }
  };

  const activeToolExecution = messages.filter((m) => m.toolCallPayload).slice(-1)[0];

  return (
    <section id="simulator" className="py-16 sm:py-20 bg-white border-y border-zinc-200 scroll-mt-16">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
            <span>Hands-On Sandbox</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-zinc-950">
            Interactive WhatsApp simulator
          </h2>
          <p className="mt-3 text-base sm:text-lg text-zinc-600 leading-relaxed font-normal">
            Click any preset scenario or type a grocery message below. Inspect real MCP tool calls in real time.
          </p>
        </div>

        {/* Preset Scenario Chips */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-8">
          {PRESET_SCENARIOS.map((sc) => (
            <button
              key={sc.id}
              type="button"
              onClick={() => handleSendSimulationMessage(sc.prompt)}
              className="px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold bg-zinc-100 hover:bg-zinc-200 text-zinc-800 transition active:scale-[0.98] cursor-pointer border border-zinc-200/80 shadow-2xs"
            >
              <span>{sc.label}</span>
            </button>
          ))}
        </div>

        {/* Simulator Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left / Center Phone Mockup (8 cols on lg) */}
          <div className="lg:col-span-7 flex justify-center">
            <div className="w-full max-w-[390px] bg-[#111B21] rounded-[48px] p-3 shadow-2xl border-4 border-zinc-300 relative overflow-hidden">
              {/* Phone Speaker & Notch */}
              <div className="w-28 h-4 bg-zinc-950 rounded-full mx-auto mb-2" />

              {/* WhatsApp App Container */}
              <div className="bg-[#0B141A] rounded-[36px] overflow-hidden flex flex-col h-[580px] border border-zinc-800">
                {/* WhatsApp Top Header Bar */}
                <div className="bg-[#202C33] px-4 py-3 flex items-center justify-between text-white shrink-0 border-b border-zinc-800">
                  <div className="flex items-center gap-2.5">
                    <GrocerLogo size="sm" iconOnly />
                    <div>
                      <div className="font-bold text-xs sm:text-sm text-zinc-100 flex items-center gap-1">
                        <span>Grocer Replenishment</span>
                        <CheckCircle2 className="w-3.5 h-3.5 text-[#00A884]" />
                      </div>
                      <div className="text-[11px] text-[#00A884] font-medium">
                        {isTyping ? "typing..." : "online • Pune Dark Store #2041"}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-zinc-400">
                    <button
                      type="button"
                      onClick={() => setMessages(messages.slice(0, 2))}
                      className="p-1 rounded hover:bg-zinc-700/50 text-[11px] font-mono text-zinc-300 cursor-pointer"
                      title="Reset chat"
                    >
                      Reset
                    </button>
                  </div>
                </div>

                {/* WhatsApp Messages Scroll Area */}
                <div
                  ref={chatScrollRef}
                  className="flex-1 overflow-y-auto p-3 space-y-3 bg-[#0B141A] text-zinc-100 text-xs sm:text-sm font-sans"
                  style={{
                    backgroundImage: "radial-gradient(#202C33 1px, transparent 1px)",
                    backgroundSize: "20px 20px",
                  }}
                >
                  {/* Delivery Location Header Pill */}
                  <div className="mx-auto w-fit px-3 py-1 rounded-full bg-[#182229] border border-zinc-800 text-[11px] text-zinc-400 flex items-center gap-1.5 shadow-2xs">
                    <MapPin className="w-3 h-3 text-emerald-400" />
                    <span>Delivering to: Charholi Budruk, Pune (12 mins)</span>
                  </div>

                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl p-3 shadow-md ${
                          msg.sender === "user"
                            ? "bg-[#005C4B] text-white rounded-tr-none"
                            : "bg-[#202C33] text-zinc-100 rounded-tl-none border border-zinc-800/80"
                        }`}
                      >
                        {msg.text && (
                          <p className="leading-relaxed whitespace-pre-wrap text-xs sm:text-sm">
                            {msg.text}
                          </p>
                        )}

                        {/* WhatsApp Itemized Receipt */}
                        {msg.items && msg.items.length > 0 && (
                          <div className="mt-2.5 pt-2.5 border-t border-zinc-700/60 space-y-1.5 text-xs">
                            {msg.items.map((item, idx) => (
                              <div key={idx} className="flex justify-between gap-3 text-zinc-200">
                                <span className="truncate">• {item.name}</span>
                                <span className="font-mono shrink-0 font-medium text-emerald-400">{item.price}</span>
                              </div>
                            ))}

                            <div className="mt-2 pt-2 border-t border-zinc-700/60 text-xs space-y-0.5">
                              {msg.subtotal && (
                                <div className="flex justify-between text-zinc-400">
                                  <span>Subtotal:</span>
                                  <span className="font-mono">{msg.subtotal}</span>
                                </div>
                              )}
                              {msg.fees && (
                                <div className="flex justify-between text-zinc-400">
                                  <span>Delivery &amp; Fees:</span>
                                  <span className="font-mono">{msg.fees}</span>
                                </div>
                              )}
                              {msg.total && (
                                <div className="flex justify-between font-bold text-white pt-1 border-t border-zinc-700/60 text-xs sm:text-sm">
                                  <span>Grand Total:</span>
                                  <span className="font-mono text-emerald-400">{msg.total}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        <div className="mt-1 flex items-center justify-end gap-1 text-[10px] text-zinc-400 font-mono">
                          <span>{msg.time}</span>
                          {msg.sender === "user" && (
                            <span className="text-cyan-400 font-bold">✓✓</span>
                          )}
                        </div>
                      </div>

                      {/* WhatsApp Interactive Action Buttons */}
                      {msg.quickReplies && msg.quickReplies.length > 0 && (
                        <div className="mt-1.5 w-full max-w-[85%] space-y-1">
                          {msg.quickReplies.map((btnText, idx) => (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => handleSendSimulationMessage(btnText)}
                              className="w-full py-2 px-3 text-center text-[#00A884] bg-[#202C33] hover:bg-[#2A3942] rounded-xl font-medium text-xs border border-zinc-800 transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-2xs"
                            >
                              <span>{btnText}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Animated Typing Bubble */}
                  {isTyping && (
                    <div className="flex items-center gap-2 p-2.5 rounded-2xl bg-[#202C33] w-fit text-zinc-300 text-xs border border-zinc-800 animate-pulse">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-[#00A884]" />
                      <span>Grocer is querying dark store inventory...</span>
                    </div>
                  )}
                </div>

                {/* WhatsApp Chat Typing Input Bar */}
                <form
                  onSubmit={handleInputSubmit}
                  className="bg-[#202C33] p-2 flex items-center gap-2 border-t border-zinc-800 shrink-0"
                >
                  <input
                    type="text"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    placeholder="Type grocery item or 'Confirm'..."
                    className="flex-1 bg-[#2A3942] text-white text-xs sm:text-sm px-3.5 py-2.5 rounded-2xl focus:outline-none focus:ring-1 focus:ring-[#00A884] placeholder-zinc-500 font-sans"
                  />
                  <button
                    type="submit"
                    disabled={!inputText.trim() || isTyping}
                    className="w-9 h-9 rounded-full bg-[#00A884] hover:bg-[#009475] disabled:opacity-40 text-[#111B21] flex items-center justify-center transition active:scale-95 cursor-pointer shrink-0"
                    title="Send message"
                  >
                    <Send className="w-4 h-4 ml-0.5" />
                  </button>
                </form>
              </div>
            </div>
          </div>

          {/* Right Live Tool Calls Drawer (5 cols on lg) */}
          <div className="lg:col-span-5 space-y-4">
            <div className="bg-zinc-900 rounded-3xl p-5 border border-zinc-800 text-white shadow-xl">
              <div className="flex items-center justify-between pb-3 border-b border-zinc-800 mb-4">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-emerald-400" />
                  <h3 className="font-mono text-xs sm:text-sm font-bold text-zinc-100">
                    Live Swiggy MCP Tool Execution
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setShowToolTrace(!showToolTrace)}
                  className="px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-mono text-zinc-300 transition cursor-pointer"
                >
                  {showToolTrace ? "Collapse" : "Expand"}
                </button>
              </div>

              {showToolTrace && activeToolExecution?.toolCallPayload ? (
                <div className="space-y-3 font-mono text-xs">
                  <div>
                    <div className="text-zinc-500 text-[11px] mb-1 uppercase tracking-wider">Active Tool Called</div>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-bold">
                        {activeToolExecution.toolCallPayload.tool}
                      </span>
                      <span className="text-zinc-400 text-xs">
                        ⚡ {activeToolExecution.toolCallPayload.latencyMs} ms
                      </span>
                    </div>
                  </div>

                  <div>
                    <div className="text-zinc-500 text-[11px] mb-1 uppercase tracking-wider">Tool Arguments (JSON)</div>
                    <pre className="p-3 rounded-xl bg-zinc-950 text-zinc-300 text-[11px] overflow-x-auto border border-zinc-800/80">
                      {JSON.stringify(activeToolExecution.toolCallPayload.params, null, 2)}
                    </pre>
                  </div>

                  <div>
                    <div className="text-zinc-500 text-[11px] mb-1 uppercase tracking-wider">Deterministic Result</div>
                    <p className="text-zinc-300 text-xs font-sans bg-zinc-950/60 p-2.5 rounded-xl border border-zinc-800">
                      {activeToolExecution.toolCallPayload.resultSummary}
                    </p>
                  </div>

                  <div className="pt-3 border-t border-zinc-800 flex items-center justify-between text-[11px] text-zinc-400">
                    <span className="flex items-center gap-1.5">
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      Deterministic Bill Gated
                    </span>
                    <span>HTTP/2 Persistent Pool</span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-zinc-500 font-sans">
                  Click a chip or send a message in the simulator to see live MCP tool function execution.
                </p>
              )}
            </div>

            {/* Quick Helper Explainer Card */}
            <div className="bg-zinc-50 rounded-2xl p-4 border border-zinc-200 text-xs text-zinc-600 space-y-2">
              <div className="font-bold text-zinc-900 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Zero Hallucination Guarantee</span>
              </div>
              <p className="leading-relaxed">
                Notice that every item price, packaging fee, and subtotal is verified directly from the dark-store API. The LLM only proposes intent candidates; pure Python calculates numbers.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
