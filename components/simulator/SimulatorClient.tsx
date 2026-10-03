"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

type Action = { id: string; title: string };
type CartItem = { spin_id: string; name: string; quantity: number; total_price: number };
type Cart = { items: CartItem[]; grand_total: number; billing_complete: boolean };
type Reply = {
  text: string;
  conversation_state: string;
  interactive_actions: Action[];
  delivery_status: string;
  meta_payloads: unknown[];
  cart: Cart | null;
  commerce_mode: string;
  latency_ms: number | null;
};
type Message = { from: "customer" | "grocer"; text: string; actions?: Action[] };

const prompts = [
  "I want to make pizza. Keep the ingredients under ₹1,000, and add bread, Bournvita, tissues, and a pencil.",
  "I have a cold and sore throat. Suggest groceries I might want.",
  "Add two packs of milk and one bread.",
  "Show my cart.",
];

export function SimulatorClient() {
  const [token, setToken] = useState("");
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [cart, setCart] = useState<Cart | null>(null);
  const [lastReply, setLastReply] = useState<Reply | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(text: string, interactiveId?: string) {
    if (!token || !text.trim() || busy) return;
    setBusy(true);
    setError("");
    setMessages((current) => [...current, { from: "customer", text }]);
    setDraft("");
    try {
      const response = await fetch("/api/simulator/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ text, interactive_id: interactiveId ?? null }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      const reply = data as Reply;
      setMessages((current) => [...current, {
        from: "grocer", text: reply.text, actions: reply.interactive_actions,
      }]);
      setCart(reply.cart);
      setLastReply(reply);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The simulator request failed.");
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(draft);
  }

  return (
    <main className="min-h-screen bg-stone-100 px-4 py-8 text-stone-900">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-emerald-700">Local test console</p>
            <h1 className="text-3xl font-bold">GROCER WhatsApp simulator</h1>
            <p className="mt-2 text-sm text-stone-600">Signed webhook → PostgreSQL queue → agent → recorded Meta reply. Checkout stays in review mode.</p>
          </div>
          <Link href="/" className="rounded-full border border-stone-300 px-4 py-2 text-sm">Back</Link>
        </div>

        <label className="mb-5 block text-sm font-medium">
          Local simulator access token
          <input
            type="password" value={token} onChange={(event) => setToken(event.target.value)}
            autoComplete="off" placeholder="Enter SIMULATOR_ACCESS_TOKEN"
            className="mt-2 w-full rounded-xl border border-stone-300 bg-white px-4 py-3"
          />
        </label>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
          <section className="flex min-h-[600px] flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
            <div className="border-b border-stone-200 px-5 py-4 font-semibold">Conversation</div>
            <div className="flex-1 space-y-4 overflow-y-auto p-5">
              {messages.length === 0 && <p className="text-sm text-stone-500">Choose an example or type a customer message.</p>}
              {messages.map((message, index) => (
                <div key={index} className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm ${message.from === "customer" ? "ml-auto bg-emerald-100" : "bg-stone-100"}`}>
                  <p className="whitespace-pre-wrap">{message.text}</p>
                  {message.actions && message.actions.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {message.actions.map((action) => (
                        <button key={action.id} type="button" disabled={busy}
                          onClick={() => void send(action.title, action.id)}
                          className="rounded-full border border-emerald-600 px-3 py-1 text-emerald-800 disabled:opacity-50">
                          {action.title}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {busy && <p className="text-sm text-stone-500">GROCER is replying…</p>}
            </div>
            {error && <p role="alert" className="mx-5 mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
            <form onSubmit={submit} className="flex gap-2 border-t border-stone-200 p-4">
              <input value={draft} onChange={(event) => setDraft(event.target.value)}
                placeholder="Type a WhatsApp message" className="min-w-0 flex-1 rounded-xl border border-stone-300 px-4 py-3" />
              <button disabled={busy || !token || !draft.trim()} className="rounded-xl bg-emerald-700 px-5 py-3 font-semibold text-white disabled:opacity-50">Send</button>
            </form>
          </section>

          <aside className="space-y-5">
            <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
              <h2 className="font-semibold">Try a journey</h2>
              <div className="mt-3 space-y-2">
                {prompts.map((prompt) => (
                  <button key={prompt} type="button" disabled={busy || !token}
                    onClick={() => void send(prompt)}
                    className="block w-full rounded-xl border border-stone-200 px-3 py-2 text-left text-sm hover:bg-stone-50 disabled:opacity-50">
                    {prompt}
                  </button>
                ))}
                <button type="button" disabled={busy || !token} onClick={() => void send("delete all")}
                  className="block w-full rounded-xl border border-red-200 px-3 py-2 text-left text-sm text-red-800 disabled:opacity-50">
                  Clear basket through chat
                </button>
              </div>
            </section>
            <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
              <h2 className="font-semibold">Observed state</h2>
              <p className="mt-2 text-sm text-stone-600">Commerce: {lastReply?.commerce_mode ?? "Awaiting first reply"}</p>
              <p className="text-sm text-stone-600">Delivery: {lastReply?.delivery_status ?? "—"}</p>
              <p className="text-sm text-stone-600">Conversation: {lastReply?.conversation_state ?? "—"}</p>
              <p className="text-sm text-stone-600">Agent time: {lastReply?.latency_ms ?? "—"} ms</p>
              <h3 className="mt-5 font-medium">Provider basket</h3>
              {cart ? <>
                <ul className="mt-2 space-y-2 text-sm">
                  {cart.items.map((item) => <li key={item.spin_id}>{item.quantity} × {item.name} — ₹{item.total_price}</li>)}
                </ul>
                <p className="mt-3 border-t border-stone-200 pt-3 font-semibold">Payable total: ₹{cart.grand_total}</p>
                {!cart.billing_complete && <p className="text-sm text-amber-700">Billing is not yet complete.</p>}
              </> : <p className="mt-2 text-sm text-stone-500">Basket unavailable until the first reply.</p>}
            </section>
            {lastReply && <details className="rounded-2xl border border-stone-200 bg-white p-5 text-sm shadow-sm">
              <summary className="cursor-pointer font-semibold">Recorded Meta payload</summary>
              <pre className="mt-3 max-h-64 overflow-auto text-xs">{JSON.stringify(lastReply.meta_payloads, null, 2)}</pre>
            </details>}
          </aside>
        </div>
      </div>
    </main>
  );
}
