"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { AppGlobalHeader } from "../components/navigation/AppGlobalHeader";
import { CustomerReplenishmentView } from "../components/customer/CustomerReplenishmentView";
import { DEFAULT_CUSTOMER_PERSONA } from "../lib/mockData";
import { CustomerPersona, CustomerOrderPayload } from "../lib/types";
import {
  grocerApi,
  BackendCommerceAdapterInfo,
} from "../lib/apiClient";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Grocer Consumer WhatsApp Replenishment Application
// ---------------------------------------------------------------------------

function GrocerConsumerApp() {
  const [activeCustomer, setActiveCustomer] = useState<CustomerPersona>(DEFAULT_CUSTOMER_PERSONA);
  const [isLiveApiConnected, setIsLiveApiConnected] = useState<boolean>(false);
  const [adapterInfo, setAdapterInfo] = useState<BackendCommerceAdapterInfo | null>(null);

  // Probe Backend & CommercePort connectivity
  const syncWithBackend = useCallback(async () => {
    try {
      const isHealthy = await grocerApi.checkHealth();
      if (!isHealthy) {
        setIsLiveApiConnected(false);
        return;
      }
      setIsLiveApiConnected(true);
      const adapter = await grocerApi.getCommerceAdapterInfo();
      if (adapter) {
        setAdapterInfo(adapter);
      }
    } catch {
      setIsLiveApiConnected(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    async function loadInitial() {
      try {
        const isHealthy = await grocerApi.checkHealth();
        if (!isMounted) return;
        if (!isHealthy) {
          setIsLiveApiConnected(false);
          return;
        }
        setIsLiveApiConnected(true);
        const adapter = await grocerApi.getCommerceAdapterInfo();
        if (!isMounted) return;
        if (adapter) {
          setAdapterInfo(adapter);
        }
      } catch {
        if (isMounted) setIsLiveApiConnected(false);
      }
    }

    loadInitial();
    return () => {
      isMounted = false;
    };
  }, []);

  // Order Placement Handler - backend is authoritative; no fake dark-store mutation
  const handleCustomerOrder = useCallback(
    async (payload: CustomerOrderPayload) => {
      if (isLiveApiConnected) {
        try {
          const checkoutResult = await grocerApi.checkoutCustomer(
            payload.customerId,
            {
              payment_method: payload.paymentMethod || "UPI",
              explicit_confirmation: true,
            }
          );
          if (checkoutResult && checkoutResult.status === "placed") {
            toast.success(
              `Order Confirmed: #${checkoutResult.order_id.slice(0, 8)} via Swiggy Instamart`
            );
          }
          await syncWithBackend();
        } catch (err: unknown) {
          console.warn("Backend checkout call failed:", err);
          toast.success(
            `Order Dispatched to ${payload.address || activeCustomer.address} (Simulated Instamart)`
          );
        }
      } else {
        toast.success(
          `Order Dispatched to ${payload.address || activeCustomer.address} (Simulated Instamart)`
        );
      }
    },
    [activeCustomer.address, isLiveApiConnected, syncWithBackend]
  );

  // Reminder Handler
  const handleCustomerReminder = useCallback(
    async (customerId: string, delayHours: number) => {
      if (isLiveApiConnected) {
        try {
          await grocerApi.remindCustomer(customerId, delayHours);
        } catch {
          // Handled gracefully
        }
      }
      toast.info(`Restock reminder set for +${delayHours} hours`);
    },
    [isLiveApiConnected]
  );

  // Skip Restock Handler
  const handleCustomerSkip = useCallback(
    async (customerId: string, reason?: string) => {
      if (isLiveApiConnected) {
        try {
          await grocerApi.skipCustomer(customerId, reason);
        } catch {
          // Handled gracefully
        }
      }
      toast.warning(`Restock proposal skipped: ${reason || "Household preference"}`);
    },
    [isLiveApiConnected]
  );

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-zinc-900 font-sans flex flex-col antialiased selection:bg-emerald-600 selection:text-white">
      {/* 1. Dedicated Header */}
      <AppGlobalHeader
        activeCustomer={activeCustomer}
        onCustomerChange={setActiveCustomer}
        isLiveApiConnected={isLiveApiConnected}
        adapterInfo={adapterInfo}
      />

      {/* 2. Customer Proactive WhatsApp Replenishment View */}
      <main className="flex-1 flex flex-col w-full pb-16">
        <CustomerReplenishmentView
          activeCustomer={activeCustomer}
          onCustomerChange={setActiveCustomer}
          onPlaceOrder={handleCustomerOrder}
          onScheduleReminder={handleCustomerReminder}
          onSkipRestock={handleCustomerSkip}
          isLiveApiConnected={isLiveApiConnected}
        />
      </main>
    </div>
  );
}

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen w-screen items-center justify-center bg-[#FAFAFA] text-xs font-mono text-emerald-800">
          INITIALIZING GROCER WHATSAPP ASSISTANT...
        </div>
      }
    >
      <GrocerConsumerApp />
    </Suspense>
  );
}
