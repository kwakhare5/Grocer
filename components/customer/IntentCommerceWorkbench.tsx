"use client";

import React, { FormEvent, useMemo, useState } from "react";
import { CheckCircle2, Loader2, MessageCircle, RefreshCw, Send, ShieldCheck, ShoppingCart, Sparkles } from "lucide-react";
import {
  checkIntentPaymentStatus,
  chooseIntentAlternative,
  clearIntentSession,
  confirmIntentCheckout,
  createIntentSession,
  sendIntentTurn,
  type IntentBasketSummary,
  type IntentChoiceOption,
  type IntentTurnResponse,
} from "../../lib/apiClient";

interface IntentCommerceWorkbenchProps {
  isBackendConnected: boolean;
}

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

const STARTER_REQUEST = "get my weekly groceries under ₹2000, vegetarian, use my usual brands";

function formatMoney(value: number) {
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function BasketCard({ basket }: { basket: IntentBasketSummary | null }) {
  if (!basket) {
    return (
      <div className="rounded-2xl border border-dashed border-zinc-300 bg-zinc-50 p-6 text-center text-sm text-zinc-500">
        send a grocery request to build an intent-verified basket.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShoppingCart className="h-4 w-4 text-emerald-600" />
          <span className="text-sm font-bold">current basket</span>
        </div>
        <span className={`rounded-full px-2 py-1 text-[10px] font-bold ${basket.within_budget ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
          {basket.within_budget ? "intent preserved" : "needs recovery"}
        </span>
      </div>

      <div className="space-y-2">
        {basket.items.map((item) => (
          <div key={`${item.spin_id}-${item.name}`} className="flex items-start justify-between gap-3 rounded-xl bg-zinc-50 p-3">
            <div className="min-w-0">
              <div className="truncate text-xs font-semibold text-zinc-900">{item.quantity}× {item.name}</div>
              <div className="mt-1 text-[10px] text-zinc-500">{item.pack_size}</div>
            </div>
            <div className="shrink-0 text-xs font-mono font-semibold text-zinc-900">{formatMoney(item.line_total)}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 border-t border-zinc-100 pt-3">
        <div className="flex items-center justify-between text-xs text-zinc-500">
          <span>items</span><span>{formatMoney(basket.item_total)}</span>
        </div>
        <div className="mt-1 flex items-center justify-between text-xs text-zinc-500">
          <span>delivery</span><span>{formatMoney(basket.delivery_fee)}</span>
        </div>
        {basket.packaging_fee > 0 && (
          <div className="mt-1 flex items-center justify-between text-xs text-zinc-500">
            <span>packaging</span><span>{formatMoney(basket.packaging_fee)}</span>
          </div>
        )}
        {basket.discount > 0 && (
          <div className="mt-1 flex items-center justify-between text-xs text-emerald-700">
            <span>discount</span><span>−{formatMoney(basket.discount)}</span>
          </div>
        )}
        <div className="mt-2 flex items-center justify-between text-sm font-bold text-zinc-950">
          <span>total</span><span>{formatMoney(basket.grand_total)}</span>
        </div>
        <div className="mt-2 text-[10px] text-zinc-500">
          delivery to {basket.address_display || basket.address_id || "selected address"}
        </div>
      </div>

      {basket.recovery_notes.length > 0 && (
        <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-700">recovery applied</div>
          {basket.recovery_notes.map((note) => (
            <div key={note} className="mt-1 text-[11px] leading-relaxed text-emerald-900">• {note}</div>
          ))}
        </div>
      )}
    </div>
  );
}

export function IntentCommerceWorkbench({ isBackendConnected }: IntentCommerceWorkbenchProps) {
  const [sessionId, setSessionId] = useState("");
  const [sessionCapability, setSessionCapability] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [basket, setBasket] = useState<IntentBasketSummary | null>(null);
  const [options, setOptions] = useState<IntentChoiceOption[]>([]);
  const [choiceNonce, setChoiceNonce] = useState("");
  const [state, setState] = useState("READY");
  const [events, setEvents] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyResponse = (response: IntentTurnResponse) => {
    setState(response.conversation_state);
    setBasket(response.basket_summary);
    setOptions(response.clarification_options || []);
    setChoiceNonce(response.clarification_nonce || "");
    setEvents(response.events || []);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "assistant", text: response.user_message },
    ]);
  };

  const ensureSession = async () => {
    if (sessionId && sessionCapability) {
      return { sessionId, sessionCapability };
    }
    const created = await createIntentSession();
    setSessionId(created.session_id);
    setSessionCapability(created.session_capability);
    return {
      sessionId: created.session_id,
      sessionCapability: created.session_capability,
    };
  };

  const send = async (message: string) => {
    if (!message.trim() || busy) return;
    setBusy(true);
    setError(null);
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", text: message.trim() }]);
    setInput("");

    try {
      const credentials = await ensureSession();
      const response = await sendIntentTurn({
        sessionId: credentials.sessionId,
        sessionCapability: credentials.sessionCapability,
        message: message.trim(),
      });
      applyResponse(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "the intent service is unavailable");
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void send(input);
  };

  const handleChoice = async (option: IntentChoiceOption) => {
    if (busy || !sessionId || !sessionCapability || !choiceNonce) return;
    setBusy(true);
    setError(null);
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", text: `${option.index}` }]);
    try {
      const response = await chooseIntentAlternative(
        sessionId,
        sessionCapability,
        option.spin_id,
        choiceNonce,
      );
      applyResponse(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "choice failed");
    } finally {
      setBusy(false);
    }
  };

  const handleConfirm = async () => {
    if (busy || state !== "AWAITING_CONFIRMATION" || !sessionCapability) return;
    setBusy(true);
    setError(null);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text: "confirm order" },
    ]);
    try {
      if (!basket?.confirmation_nonce) {
        throw new Error("The basket confirmation expired. Please rebuild the basket.");
      }
      const response = await confirmIntentCheckout({
        sessionId,
        sessionCapability,
        paymentMethod: basket.selected_payment_method,
        confirmationNonce: basket.confirmation_nonce,
      });
      applyResponse(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "checkout failed");
    } finally {
      setBusy(false);
    }
  };

  const handlePaymentStatus = async () => {
    if (busy || state !== "PAYMENT_PENDING" || !sessionCapability) return;
    setBusy(true);
    setError(null);
    try {
      applyResponse(await checkIntentPaymentStatus(sessionId, sessionCapability));
    } catch (err) {
      setError(err instanceof Error ? err.message : "payment status check failed");
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    setBusy(true);
    try {
      if (sessionId && sessionCapability) {
        await clearIntentSession(sessionId, sessionCapability).catch(() => undefined);
      }
    } finally {
      setSessionId("");
      setSessionCapability("");
      setMessages([]);
      setBasket(null);
      setOptions([]);
      setChoiceNonce("");
      setState("READY");
      setEvents([]);
      setError(null);
      setBusy(false);
    }
  };

  const statusLabel = useMemo(() => state.toLowerCase().replaceAll("_", " "), [state]);

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-emerald-700">
            <Sparkles className="h-3 w-3" /> intent-preserving commerce
          </div>
          <h1 className="text-3xl font-editorial font-bold tracking-tight text-zinc-950">Grocer × WhatsApp</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-600">
            the interface is conversational. the backend treats the user&apos;s original shopping goal as a contract,
            verifies live cart state, and recovers before checkout.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono">
          <span className={`h-2.5 w-2.5 rounded-full ${isBackendConnected ? "bg-emerald-500" : "bg-zinc-300"}`} />
          <span className="text-zinc-500">{isBackendConnected ? "intent api connected" : "backend offline"}</span>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <section className="overflow-hidden rounded-3xl border border-zinc-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-zinc-100 bg-[#075E54] px-5 py-4 text-white">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/15">
                <MessageCircle className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm font-bold">Grocer Assistant</div>
                <div className="text-[10px] text-emerald-100">Demo household • {statusLabel}</div>
              </div>
            </div>
            <button type="button" onClick={() => void reset()} className="rounded-lg p-2 text-white/80 hover:bg-white/10 hover:text-white" title="Reset conversation">
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>

          <div className="min-h-[470px] space-y-3 bg-[#efeae2] p-4">
            {messages.length === 0 ? (
              <div className="flex min-h-[430px] items-center justify-center">
                <div className="max-w-sm rounded-2xl border border-zinc-200 bg-white p-5 text-center shadow-sm">
                  <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <div className="text-sm font-bold text-zinc-900">start with intent, not products</div>
                  <p className="mt-2 text-xs leading-relaxed text-zinc-500">
                    tell the agent what you are trying to accomplish. product selection and recovery happen underneath.
                  </p>
                  <button
                    type="button"
                    disabled={busy || !isBackendConnected}
                    onClick={() => void send(STARTER_REQUEST)}
                    className="mt-4 w-full rounded-xl bg-[#075E54] px-4 py-3 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    try a real grocery request
                  </button>
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[82%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-xs leading-relaxed shadow-sm ${message.role === "user" ? "rounded-br-md bg-[#d9fdd3] text-zinc-900" : "rounded-bl-md bg-white text-zinc-800"}`}>
                    {message.text}
                  </div>
                </div>
              ))
            )}

            {options.length > 0 && (
              <div className="grid gap-2 pt-1 sm:grid-cols-3">
                {options.map((option) => (
                  <button
                    key={option.spin_id}
                    type="button"
                    disabled={busy}
                    onClick={() => void handleChoice(option)}
                    className="rounded-xl border border-zinc-200 bg-white p-3 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-300 disabled:opacity-50"
                  >
                    <div className="text-[10px] font-bold text-emerald-700">{option.index}</div>
                    <div className="mt-1 text-xs font-semibold text-zinc-900">{option.name}</div>
                    <div className="mt-1 text-[10px] text-zinc-500">{option.pack_size} • {formatMoney(option.price)}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <form onSubmit={handleSubmit} className="border-t border-zinc-200 bg-white p-3">
            <div className="flex items-center gap-2 rounded-2xl bg-zinc-100 px-3 py-2">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={isBackendConnected ? "message Grocer..." : "start the FastAPI backend first"}
                disabled={busy || !isBackendConnected}
                className="min-w-0 flex-1 bg-transparent px-1 text-sm text-zinc-900 outline-none placeholder:text-zinc-400"
              />
              <button type="submit" disabled={busy || !input.trim() || !isBackendConnected} className="flex h-9 w-9 items-center justify-center rounded-full bg-[#075E54] text-white disabled:opacity-40">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          </form>
        </section>

        <aside className="space-y-4">
          <div className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <div className="text-sm font-bold text-zinc-950">commerce state</div>
                <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-zinc-400">session {sessionId.slice(-12)}</div>
              </div>
              <ShieldCheck className="h-5 w-5 text-emerald-600" />
            </div>
            <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
              {["intent parsed", "policy checked", "cart verified", "checkout guarded"].map((label) => (
                <div key={label} className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 text-zinc-600">
                  <CheckCircle2 className="mb-1 h-3.5 w-3.5 text-emerald-600" />
                  {label}
                </div>
              ))}
            </div>
          </div>

          <BasketCard basket={basket} />

          {state === "AWAITING_CONFIRMATION" && basket && (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
              <div className="text-xs font-bold text-emerald-950">ready to place order</div>
              <div className="mt-1 text-[11px] leading-relaxed text-emerald-900">
                the backend checked this basket against the original intent. checkout is blocked until this basket, address, and payment choice are explicitly approved.
              </div>
              <div className="mt-3 rounded-xl border border-emerald-200 bg-white px-3 py-2 text-xs text-emerald-900">
                Payment: <span className="font-bold">{basket.selected_payment_option_label || basket.selected_payment_method}</span>
              </div>
              <button type="button" disabled={busy} onClick={() => void handleConfirm()} className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-[#075E54] px-4 py-3 text-xs font-bold text-white disabled:opacity-50">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                confirm & place order
              </button>
            </div>
          )}

          {state === "ORDERED" && (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-900">
              order placed successfully. the intent contract made it all the way to checkout.
            </div>
          )}

          {state === "PAYMENT_PENDING" && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
              <div className="font-semibold">payment pending</div>
              <div className="mt-1 text-xs">No successful order is shown until the provider confirms payment.</div>
              <button type="button" disabled={busy} onClick={() => void handlePaymentStatus()} className="mt-3 rounded-xl bg-amber-900 px-4 py-2 text-xs font-bold text-white disabled:opacity-50">
                {busy ? "checking…" : "check payment status"}
              </button>
            </div>
          )}

          {state === "PARTIAL_ORDER" && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm font-semibold text-amber-950">
              only part of the order succeeded. Review the provider order details before continuing.
            </div>
          )}

          {(state === "PAYMENT_FAILED" || state === "ORDER_STATE_UNKNOWN") && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-900">
              {state === "PAYMENT_FAILED" ? "payment failed or was cancelled." : "checkout outcome is unknown; GROCER will not retry or claim success."}
            </div>
          )}

          {error && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-xs text-red-800">{error}</div>
          )}

          <div className="rounded-2xl border border-zinc-200 bg-zinc-950 p-4 text-zinc-100">
            <div className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">latest deterministic events</div>
            <div className="mt-3 space-y-1.5 font-mono text-[10px]">
              {events.length === 0 ? <div className="text-zinc-600">waiting for a turn…</div> : events.slice(-8).map((event) => <div key={event} className="text-zinc-300">{event}</div>)}
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}
