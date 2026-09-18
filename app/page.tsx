"use client";

import React, { useEffect, useState } from "react";
import { AppGlobalHeader } from "../components/navigation/AppGlobalHeader";
import { IntentCommerceWorkbench } from "../components/customer/IntentCommerceWorkbench";
import { DEFAULT_CUSTOMER_PERSONA } from "../lib/mockData";
import type { CustomerPersona } from "../lib/types";
import { checkIntentBackend } from "../lib/apiClient";

export default function Home() {
  const [activeCustomer, setActiveCustomer] = useState<CustomerPersona>(DEFAULT_CUSTOMER_PERSONA);
  const [isBackendConnected, setIsBackendConnected] = useState(false);

  useEffect(() => {
    let mounted = true;
    const probe = async () => {
      const connected = await checkIntentBackend();
      if (mounted) setIsBackendConnected(connected);
    };
    void probe();

    // If user arrived from Swiggy OAuth redirect with ?code= and ?state=
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      const state = params.get("state");
      if (code && state) {
        window.location.replace(`/auth/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`);
        return;
      }
    }

    const timer = window.setInterval(() => void probe(), 15_000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#fafafa] text-zinc-900 antialiased">
      <AppGlobalHeader
        activeCustomer={activeCustomer}
        onCustomerChange={setActiveCustomer}
        isLiveApiConnected={isBackendConnected}
      />
      <IntentCommerceWorkbench
        key={activeCustomer.id}
        customer={activeCustomer}
        isBackendConnected={isBackendConnected}
      />
    </div>
  );
}
