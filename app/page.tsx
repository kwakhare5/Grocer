"use client";

import React, { useEffect, useState, FormEvent } from "react";
import { AppGlobalHeader } from "../components/navigation/AppGlobalHeader";
import { Sparkles, ArrowRight, CheckCircle2, MessageCircle, Loader2 } from "lucide-react";
import { checkIntentBackend } from "../lib/apiClient";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://grocer-backend-qwk4.onrender.com";

export default function Home() {
  const [isBackendConnected, setIsBackendConnected] = useState(true);
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    let mounted = true;
    const probe = async () => {
      const connected = await checkIntentBackend();
      if (mounted) setIsBackendConnected(connected);
    };
    void probe();

    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");

    if (code && state) {
      setTimeout(() => setBusy(true), 0);
      fetch(`${BACKEND_URL}/api/auth/swiggy/callback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, state })
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            setIsConnected(true);
            window.history.replaceState({}, document.title, window.location.pathname);
          } else {
            throw new Error("Failed to link Swiggy account");
          }
        })
        .catch(err => { if (mounted) setError(err.message); })
        .finally(() => { if (mounted) setBusy(false); });
    }
    return () => { mounted = false; };
  }, []);

  const handleConnect = async (e: FormEvent) => {
    e.preventDefault();
    if (!phone || phone.length < 10) {
      setError("Please enter a valid WhatsApp number (e.g., 919876543210)");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/swiggy/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: phone })
      });
      if (!res.ok) throw new Error("Failed to initiate login");
      const data = await res.json();
      if (data.authorize_url) {
        window.location.href = data.authorize_url;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error connecting");
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#fafafa] text-zinc-900 antialiased flex flex-col">
      <AppGlobalHeader isBackendConnected={isBackendConnected} />
      
      <main className="flex-1 flex flex-col items-center justify-center p-6">
        <div className="max-w-md w-full bg-white p-8 rounded-3xl border border-zinc-200 shadow-sm">
          
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700">
            <Sparkles className="h-8 w-8" />
          </div>

          <h1 className="text-3xl font-editorial font-bold text-center text-zinc-950 mb-2">
            Grocer Assistant
          </h1>
          <p className="text-sm text-center text-zinc-500 mb-6 leading-relaxed">
            Link your Swiggy Instamart account to start ordering your weekly groceries directly through WhatsApp.
          </p>

          <div className="mb-8 rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-center">
            <div className="text-xs font-bold text-zinc-900 mb-1">start with intent, not products</div>
            <p className="text-[11px] leading-relaxed text-zinc-500">
              the interface is conversational. the backend treats your original shopping goal as a contract,
              verifies live cart state, and recovers before checkout.
            </p>
          </div>

          {error && (
            <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 text-center">
              {error}
            </div>
          )}

          {isConnected ? (
            <div className="space-y-6">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-center justify-center gap-2 text-emerald-800 font-bold">
                <CheckCircle2 className="h-5 w-5" />
                Swiggy Account Linked
              </div>
              
              <a 
                href="https://wa.me/15556631707?text=Hi%20Grocer!"
                target="_blank"
                rel="noreferrer"
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#25D366] px-4 py-4 text-sm font-bold text-white hover:bg-[#128C7E] transition shadow-md"
              >
                <MessageCircle className="h-5 w-5" />
                Start on WhatsApp
              </a>
            </div>
          ) : (
            <form onSubmit={handleConnect} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-zinc-700 mb-2 uppercase tracking-wider">
                  WhatsApp Number
                </label>
                <input
                  type="tel"
                  placeholder="e.g., 918237803170"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm outline-none focus:border-emerald-500 focus:bg-white transition"
                  disabled={busy}
                />
              </div>

              <button
                type="submit"
                disabled={busy}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#fc8019] px-4 py-4 text-sm font-bold text-white hover:bg-[#e47112] transition shadow-md disabled:opacity-50"
              >
                {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : (
                  <>
                    Connect Swiggy
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </form>
          )}

        </div>
        
        <div className="mt-8 flex items-center gap-2 text-xs font-mono">
          <span className={`h-2 w-2 rounded-full ${isBackendConnected ? "bg-emerald-500" : "bg-zinc-300"}`} />
          <span className="text-zinc-500">{isBackendConnected ? "backend online" : "backend offline"}</span>
        </div>
      </main>
    </div>
  );
}
