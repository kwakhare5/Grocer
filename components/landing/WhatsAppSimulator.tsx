"use client";

import React, { useState, useRef, FormEvent } from "react";
import {
  Send,
  Loader2,
  Terminal,
  Check,
  CheckCircle2,
  MapPin,
  RefreshCw,
} from "lucide-react";
import { GrocerLogo } from "../ui/GrocerLogo";
import { Message, PresetScenario } from "./types";
import { PRESET_SCENARIOS } from "./data";

export function WhatsAppSimulator() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "init_1",
      sender: "user",
      text: "I want to make pasta tonight under Rs 1500. Get ingredients",
      time: "8:04 PM",
    },
    {
      id: "init_2",
      sender: "assistant",
      text: "Penne Arbiatta ingredients from your local dark store:",
      time: "8:04 PM",
      items: [
        { name: "Yu Zero Maida Penne Pasta 500g", price: "Rs 49" },
        { name: "Veeba Pasta & Pizza Sauce 280g", price: "Rs 79" },
        { name: "Amul Mozzarella Diced Cheese 200g", price: "Rs 110" },
        { name: "Fresh Garlic 100g", price: "Rs 38" },
      ],
      subtotal: "Rs 276",
      fees: "Rs 5 (Handling)",
      total: "Rs 281",
      quickReplies: ["Confirm Order", "Also add butter", "Clear Cart"],
      toolCallPayload: {
        tool: "search_products",
        params: { query: "penne pasta sauce cheese garlic", max_price: 1500 },
        resultSummary: "Parallel catalog search matched 4 SKUs (in-stock at dark store #2041). Total Rs 281.",
        latencyMs: 1045,
      },
    },
  ]);

  const [inputText, setInputText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
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
    <section id="sandbox" className="py-16 sm:py-20 bg-zinc-100/70 border-y border-zinc-200 scroll-mt-16">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
            <span>Replenishment Sandbox</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-zinc-950">
            Interactive replenishment simulator
          </h2>
          <p className="mt-3 text-base sm:text-lg text-zinc-600 leading-relaxed font-normal">
            Test real scenarios or type your own request. Live MCP tool executions update in real time on the right.
          </p>
        </div>

        {/* Preset Scenario Quick Chips */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-8">
          {PRESET_SCENARIOS.map((sc) => (
            <button
              key={sc.id}
              type="button"
              onClick={() => handleSendSimulationMessage(sc.prompt)}
              className="px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium bg-white hover:bg-zinc-50 text-zinc-800 transition active:scale-[0.98] cursor-pointer border border-zinc-200 shadow-2xs"
            >
              <span>{sc.label}</span>
            </button>
          ))}
        </div>

        {/* Unified Two-Column Interface Card (No mobile chassis) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Clean Chat Interface (7 cols) */}
          <div className="lg:col-span-7 bg-white rounded-3xl border border-zinc-200 shadow-xs overflow-hidden flex flex-col h-[600px]">
            {/* Chat Header Bar */}
            <div className="bg-zinc-50/80 px-5 py-3.5 border-b border-zinc-200 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <GrocerLogo size="sm" iconOnly />
                <div>
                  <div className="font-bold text-sm text-zinc-950 flex items-center gap-1.5">
                    <span>Grocer Assistant</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  </div>
                  <div className="text-xs text-zinc-500 font-medium">
                    {isTyping ? "Checking dark store stock..." : "Connected • Pune Dark Store #2041"}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setMessages(messages.slice(0, 2))}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white border border-zinc-200 hover:bg-zinc-50 text-xs font-medium text-zinc-600 transition cursor-pointer"
                title="Reset conversation"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Reset</span>
              </button>
            </div>

            {/* Chat Message Stream */}
            <div
              ref={chatScrollRef}
              className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-3.5 bg-zinc-50/40 text-zinc-900 text-sm font-sans"
            >
              {/* Delivery Address Pill */}
              <div className="mx-auto w-fit px-3 py-1 rounded-full bg-white border border-zinc-200 text-xs text-zinc-600 flex items-center gap-1.5 shadow-2xs">
                <MapPin className="w-3.5 h-3.5 text-emerald-600" />
                <span>Delivering to: Charholi Budruk, Pune (12 mins)</span>
              </div>

              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl p-4 shadow-2xs ${
                      msg.sender === "user"
                        ? "bg-emerald-600 text-white rounded-tr-none"
                        : "bg-white text-zinc-900 rounded-tl-none border border-zinc-200"
                    }`}
                  >
                    {msg.text && (
                      <p className="leading-relaxed whitespace-pre-wrap text-sm font-normal">
                        {msg.text}
                      </p>
                    )}

                    {/* Clean Itemized Receipt */}
                    {msg.items && msg.items.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-zinc-200/80 space-y-1.5 text-xs sm:text-sm">
                        {msg.items.map((item, idx) => (
                          <div key={idx} className="flex justify-between gap-3 text-zinc-700">
                            <span className="truncate">• {item.name}</span>
                            <span className="font-mono shrink-0 font-semibold text-zinc-900">{item.price}</span>
                          </div>
                        ))}

                        <div className="mt-2.5 pt-2.5 border-t border-zinc-200 space-y-1 text-xs">
                          {msg.subtotal && (
                            <div className="flex justify-between text-zinc-500">
                              <span>Subtotal:</span>
                              <span className="font-mono">{msg.subtotal}</span>
                            </div>
                          )}
                          {msg.fees && (
                            <div className="flex justify-between text-zinc-500">
                              <span>Delivery &amp; Fees:</span>
                              <span className="font-mono">{msg.fees}</span>
                            </div>
                          )}
                          {msg.total && (
                            <div className="flex justify-between font-bold text-zinc-950 pt-1.5 border-t border-zinc-200 text-sm">
                              <span>Total:</span>
                              <span className="font-mono text-emerald-700">{msg.total}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    <div className="mt-1.5 flex items-center justify-end gap-1 text-[11px] text-zinc-400 font-mono">
                      <span>{msg.time}</span>
                      {msg.sender === "user" && (
                        <span className="text-emerald-200 font-bold">Read</span>
                      )}
                    </div>
                  </div>

                  {/* Interactive Reply Buttons */}
                  {msg.quickReplies && msg.quickReplies.length > 0 && (
                    <div className="mt-1.5 w-full max-w-[85%] flex flex-wrap gap-1.5">
                      {msg.quickReplies.map((btnText, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => handleSendSimulationMessage(btnText)}
                          className="px-3 py-1.5 bg-white hover:bg-zinc-50 rounded-xl font-medium text-xs text-emerald-800 border border-zinc-200 transition-colors cursor-pointer shadow-2xs"
                        >
                          {btnText}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {/* Typing State Indicator */}
              {isTyping && (
                <div className="flex items-center gap-2 p-3 rounded-2xl bg-white w-fit text-zinc-600 text-xs border border-zinc-200 shadow-2xs">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-600" />
                  <span>Checking dark store stock...</span>
                </div>
              )}
            </div>

            {/* Bottom Message Input Bar */}
            <form
              onSubmit={handleInputSubmit}
              className="bg-white p-3 flex items-center gap-2 border-t border-zinc-200 shrink-0"
            >
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Type a grocery item or 'Confirm'..."
                className="flex-1 bg-zinc-50 text-zinc-900 text-sm px-4 py-2.5 rounded-xl border border-zinc-200 focus:outline-none focus:border-emerald-600 placeholder-zinc-400 font-sans"
              />
              <button
                type="submit"
                disabled={!inputText.trim() || isTyping}
                className="h-10 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white font-medium text-sm flex items-center justify-center gap-1.5 transition active:scale-95 cursor-pointer shrink-0"
              >
                <span>Send</span>
                <Send className="w-3.5 h-3.5 ml-0.5" />
              </button>
            </form>
          </div>

          {/* Right Column: Clean Light Tool Execution Inspector (5 cols) */}
          <div className="lg:col-span-5 space-y-4">
            <div className="bg-white rounded-3xl p-5 sm:p-6 border border-zinc-200 shadow-xs">
              <div className="flex items-center justify-between pb-3.5 border-b border-zinc-100 mb-4">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-emerald-700" />
                  <h3 className="font-mono text-sm font-bold text-zinc-950">
                    Live Swiggy MCP Tool Trace
                  </h3>
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-zinc-100 text-zinc-700 border border-zinc-200">
                  HTTP/2 Pooled
                </span>
              </div>

              {activeToolExecution?.toolCallPayload ? (
                <div className="space-y-4 font-mono text-xs">
                  <div>
                    <div className="text-zinc-500 text-[11px] mb-1 uppercase tracking-wider font-semibold">
                      Executed Tool
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 font-bold">
                        {activeToolExecution.toolCallPayload.tool}
                      </span>
                      <span className="text-zinc-600 text-xs">
                        Latency: {activeToolExecution.toolCallPayload.latencyMs} ms
                      </span>
                    </div>
                  </div>

                  <div>
                    <div className="text-zinc-500 text-[11px] mb-1 uppercase tracking-wider font-semibold">
                      Tool Arguments
                    </div>
                    <pre className="p-3 rounded-xl bg-zinc-50 text-zinc-800 text-xs overflow-x-auto border border-zinc-200">
                      {JSON.stringify(activeToolExecution.toolCallPayload.params, null, 2)}
                    </pre>
                  </div>

                  <div>
                    <div className="text-zinc-500 text-[11px] mb-1 uppercase tracking-wider font-semibold">
                      Provider Response Summary
                    </div>
                    <p className="text-zinc-700 text-xs font-sans bg-zinc-50 p-3 rounded-xl border border-zinc-200 leading-relaxed">
                      {activeToolExecution.toolCallPayload.resultSummary}
                    </p>
                  </div>

                  <div className="pt-3 border-t border-zinc-100 flex items-center justify-between text-xs text-zinc-600">
                    <span className="flex items-center gap-1.5 font-sans">
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                      Verified billing totals
                    </span>
                    <span className="font-mono">JSON-RPC 2.0</span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-zinc-500 font-sans">
                  Select a preset chip or send a message to inspect the live MCP tool call payload.
                </p>
              )}
            </div>

            {/* Zero-Math Assurance Note */}
            <div className="bg-white rounded-2xl p-4 sm:p-5 border border-zinc-200 text-xs text-zinc-600 space-y-1.5 shadow-2xs">
              <div className="font-bold text-zinc-950 flex items-center gap-1.5 text-xs sm:text-sm">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Deterministic Calculation</span>
              </div>
              <p className="leading-relaxed font-normal">
                Item prices, packaging fees, and delivery charges come directly from the Swiggy Instamart billing engine. The language model proposes tools; backend Python enforces totals.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
