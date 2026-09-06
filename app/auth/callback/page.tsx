"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { SwiggyClient } from "../../../lib/swiggyClient";

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [statusText, setStatusText] = useState("Connecting your Swiggy Instamart account...");
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    let mounted = true;

    const exchange = async () => {
      const code = searchParams.get("code");
      const state = searchParams.get("state");
      const error = searchParams.get("error");
      const errorDescription = searchParams.get("error_description");

      if (error) {
        if (mounted) {
          setIsError(true);
          setStatusText(`Swiggy authorization error: ${errorDescription || error}`);
        }
        return;
      }

      if (!code || !state) {
        if (mounted) {
          setIsError(true);
          setStatusText("Missing authorization code or state in callback.");
        }
        return;
      }

      try {
        const success = await SwiggyClient.handleAuthCallback(code, state);
        if (!mounted) return;

        if (success) {
          setStatusText("Authenticated successfully! Redirecting...");
          setTimeout(() => {
            router.push("/");
          }, 1200);
        } else {
          setIsError(true);
          setStatusText("Failed to exchange Swiggy authorization code. Please try again.");
        }
      } catch (err: unknown) {
        if (!mounted) return;
        setIsError(true);
        const msg = err instanceof Error ? err.message : "Unknown error";
        setStatusText(`Authentication failed: ${msg}`);
      }
    };

    void exchange();

    return () => {
      mounted = false;
    };
  }, [searchParams, router]);

  return (
    <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-sm">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-orange-100 text-orange-600 font-bold text-xl">
        S
      </div>
      <h1 className="text-xl font-semibold tracking-tight">Swiggy Instamart OAuth</h1>
      <p className={`mt-3 text-sm ${isError ? "text-red-600 font-medium" : "text-zinc-600"}`}>
        {statusText}
      </p>
      {isError && (
        <button
          onClick={() => router.push("/")}
          className="mt-6 inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 transition-colors"
        >
          Back to Grocer
        </button>
      )}
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 p-6 text-zinc-900">
      <Suspense
        fallback={
          <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-sm">
            <p className="text-sm text-zinc-600">Loading callback...</p>
          </div>
        }
      >
        <CallbackContent />
      </Suspense>
    </div>
  );
}
