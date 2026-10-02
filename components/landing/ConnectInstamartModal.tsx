"use client";

import React, { useState, FormEvent } from "react";
import {
  ShoppingBag,
  CheckCircle2,
  X,
  Loader2,
  ArrowRight,
} from "lucide-react";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";

export interface ConnectInstamartModalProps {
  isOpen: boolean;
  onClose: () => void;
  isConnected: boolean;
  connectTicket?: string | null;
  initialError?: string | null;
}

export function ConnectInstamartModal({
  isOpen,
  onClose,
  isConnected,
  connectTicket,
  initialError,
}: ConnectInstamartModalProps) {
  const [authError, setAuthError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!isOpen) return null;

  const handleStartAuth = async (e: FormEvent) => {
    e.preventDefault();
    setAuthError(null);

    const ticket = connectTicket;
    if (!ticket) {
      setAuthError("Request a fresh connection link in your WhatsApp chat with Grocer.");
      return;
    }

    setBusy(true);
    try {
      const res = await fetch("/api/auth/swiggy/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to start Swiggy connection");
      }

      if (data.authorize_url) {
        window.location.href = data.authorize_url;
      } else {
        throw new Error("No authentication URL returned from server.");
      }
    } catch (err: unknown) {
      setAuthError(
        err instanceof Error
          ? err.message
          : "Unable to start the connection. Please try again.",
      );
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/40 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-zinc-200 shadow-2xl max-w-md w-full relative">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-5 right-5 text-zinc-400 hover:text-zinc-700 p-1.5 rounded-lg hover:bg-zinc-100 transition cursor-pointer"
          title="Close"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="w-11 h-11 rounded-2xl bg-emerald-50 flex items-center justify-center text-emerald-700 shrink-0 border border-emerald-200">
            <ShoppingBag className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base sm:text-lg font-bold text-zinc-950 leading-tight">
              Connect Store Account
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5 flex items-center gap-1.5">
              <span>OAuth 2.1 Gateway</span>
              <span>•</span>
              <WhatsAppIcon className="w-3.5 h-3.5 inline shrink-0" />
              <span>WhatsApp Replenishment</span>
            </p>
          </div>
        </div>

        {(authError || initialError) && (
          <div
            className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-xs sm:text-sm text-red-800 leading-relaxed"
            role="alert"
          >
            {authError || initialError}
          </div>
        )}

        {isConnected ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-center gap-3 text-emerald-800 text-xs sm:text-sm font-semibold">
              <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
              <span>Your quick-commerce store account is successfully linked!</span>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-xs sm:text-sm font-semibold text-white hover:bg-zinc-800 transition cursor-pointer"
            >
              <span>Back to Demo</span>
            </button>
          </div>
        ) : (
          <form onSubmit={handleStartAuth} className="space-y-4">
            <p className="text-xs sm:text-sm text-zinc-600 leading-relaxed font-normal">
              Open the one-time link Grocer sent to your WhatsApp chat, then continue here to connect your Swiggy account.
            </p>

            <button
              type="submit"
              disabled={busy}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 px-4 py-3 text-xs sm:text-sm font-semibold text-white shadow-xs transition active:scale-[0.98] cursor-pointer"
            >
              {busy ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Connecting to gateway...</span>
                </>
              ) : (
                <>
                  <span>Verify &amp; Connect</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>

            <p className="text-xs text-zinc-400 text-center leading-normal">
              Your Swiggy access token is stored encrypted. We never store banking credentials.
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
