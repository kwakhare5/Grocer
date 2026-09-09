"use client";

import React, { useEffect, useState } from "react";
import { AppGlobalHeader } from "../components/navigation/AppGlobalHeader";
import { IntentCommerceWorkbench } from "../components/customer/IntentCommerceWorkbench";
import { checkIntentBackend } from "../lib/apiClient";

export default function Home() {
  const [isBackendConnected, setIsBackendConnected] = useState(false);

  useEffect(() => {
    let mounted = true;
    const probe = async () => {
      const connected = await checkIntentBackend();
      if (mounted) setIsBackendConnected(connected);
    };
    void probe();

    const timer = window.setInterval(() => void probe(), 15_000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#fafafa] text-zinc-900 antialiased">
      <AppGlobalHeader isBackendConnected={isBackendConnected} />
      <IntentCommerceWorkbench isBackendConnected={isBackendConnected} />
    </div>
  );
}
