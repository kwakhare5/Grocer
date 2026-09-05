"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { AppGlobalHeader } from "../components/navigation/AppGlobalHeader";
import { CustomerReplenishmentView } from "../components/customer/CustomerReplenishmentView";
import {
  INITIAL_STORES,
  DEFAULT_CUSTOMER_PERSONA,
} from "../lib/mockData";
import {
  DarkStore,
  CustomerPersona,
  CustomerOrderPayload,
} from "../lib/types";
import {
  grocerApi,
  transformStores,
  BackendCommerceAdapterInfo,
} from "../lib/apiClient";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Grocer Consumer WhatsApp Replenishment Application
// ---------------------------------------------------------------------------

function GrocerConsumerApp() {
  const [activeCustomer, setActiveCustomer] = useState<CustomerPersona>(DEFAULT_CUSTOMER_PERSONA);
  const [stores, setStores] = useState<DarkStore[]>(INITIAL_STORES);
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

      const [backendStores, backendRisks, adapter] = await Promise.all([
        grocerApi.getStores(),
        grocerApi.getRisks(),
        grocerApi.getCommerceAdapterInfo(),
      ]);

      if (adapter) {
        setAdapterInfo(adapter);
      }

      if (backendStores && backendStores.length > 0) {
        const transformedStores = transformStores(backendStores, backendRisks || []);
        setStores(transformedStores);
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
        const [backendStores, backendRisks, adapter] = await Promise.all([
          grocerApi.getStores(),
          grocerApi.getRisks(),
          grocerApi.getCommerceAdapterInfo(),
        ]);
        if (!isMounted) return;

        if (adapter) {
          setAdapterInfo(adapter);
        }

        if (backendStores && backendStores.length > 0) {
          const transformedStores = transformStores(backendStores, backendRisks || []);
          setStores(transformedStores);
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

  // Order Placement Handler (with Consequential Guard validation)
  const handleCustomerOrder = useCallback(
    async (payload: CustomerOrderPayload) => {
      // 1. Optimistic local stock reduction for household dark store
      setStores((prevStores) =>
        prevStores.map((store) => {
          if (
            store.code === payload.homeStoreCode ||
            store.name.toLowerCase().includes(payload.homeStoreName.toLowerCase())
          ) {
            const hasDairy = payload.items.some(
              (i) => i.productId.includes("milk") || i.productName.toLowerCase().includes("milk")
            );
            const hasBakery = payload.items.some(
              (i) => i.productId.includes("bread") || i.productName.toLowerCase().includes("bread")
            );

            return {
              ...store,
              inventoryHealth: {
                ...store.inventoryHealth,
                dairy: hasDairy
                  ? Math.max(10, store.inventoryHealth.dairy - 4)
                  : store.inventoryHealth.dairy,
                bakery: hasBakery
                  ? Math.max(10, store.inventoryHealth.bakery - 5)
                  : store.inventoryHealth.bakery,
              },
            };
          }
          return store;
        })
      );

      // 2. Call authoritative backend API if live
      if (isLiveApiConnected) {
        try {
          // Trigger checkout with explicit confirmation
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
          console.warn("Backend checkout call failed, relying on edge simulation:", err);
          toast.success(
            `Order Dispatched: ₹${payload.totalINR} to ${payload.address || activeCustomer.address} (Simulated Instamart)`
          );
        }
      } else {
        toast.success(
          `Order Dispatched: ₹${payload.totalINR} to ${payload.address || activeCustomer.address} (Simulated Instamart)`
        );
      }
    },
    [activeCustomer, isLiveApiConnected, syncWithBackend]
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

  // Reset Pantry Handler
  const handleResetPantry = useCallback(() => {
    setStores(INITIAL_STORES);
    toast.info("Pantry items & stock levels reset to baseline");
  }, []);

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-zinc-900 font-sans flex flex-col antialiased selection:bg-emerald-600 selection:text-white">
      {/* 1. Dedicated Header */}
      <AppGlobalHeader
        activeCustomer={activeCustomer}
        onCustomerChange={setActiveCustomer}
        isLiveApiConnected={isLiveApiConnected}
        adapterInfo={adapterInfo}
        onResetPantry={handleResetPantry}
      />

      {/* 2. Customer Proactive WhatsApp Replenishment View */}
      <main className="flex-1 flex flex-col w-full pb-16">
        <CustomerReplenishmentView
          activeCustomer={activeCustomer}
          onCustomerChange={setActiveCustomer}
          onPlaceOrder={handleCustomerOrder}
          onScheduleReminder={handleCustomerReminder}
          onSkipRestock={handleCustomerSkip}
          stores={stores}
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
