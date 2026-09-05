"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import PhoneMockup from "./PhoneMockup";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";
import {
  Users,
  CheckCircle2,
  RotateCcw,
  Copy,
  Check,
  MapPin,
  Truck,
  Zap,
  ShoppingBag,
  Milk,
  Wheat,
  Egg,
  Apple,
  ShieldCheck,
  RefreshCw,
  Minus,
  Plus,
} from "lucide-react";
import {
  CustomerPersona,
  CustomerOrderPayload,
  DarkStore,
} from "../../lib/types";
import {
  SIMULATED_CUSTOMERS,
  DEFAULT_CUSTOMER_PERSONA,
} from "../../lib/mockData";
import {
  grocerApi,
  BackendCommerceAdapterInfo,
  BackendCommerceCart,
  BackendCommerceOrderResult,
  BackendCommerceTracking,
  BackendCommerceProductItem,
} from "../../lib/apiClient";
import { toast } from "sonner";

interface CustomerReplenishmentViewProps {
  activeCustomer?: CustomerPersona;
  onCustomerChange?: (customer: CustomerPersona) => void;
  onPlaceOrder?: (payload: CustomerOrderPayload) => void;
  onScheduleReminder?: (customerId: string, delayHours: number) => void;
  onSkipRestock?: (customerId: string, reason?: string) => void;
  stores?: DarkStore[];
  isLiveApiConnected?: boolean;
}

const PANTRY_ITEMS = [
  {
    name: "Amul Taaza Milk 1L",
    shortName: "Milk",
    category: "Dairy",
    price: 66,
    icon: Milk,
    defaultPct: 12,
    threshold: 15,
  },
  {
    name: "Whole Wheat Bread 400g",
    shortName: "Bread",
    category: "Bakery",
    price: 50,
    icon: Wheat,
    defaultPct: 10,
    threshold: 20,
  },
  {
    name: "Farm Fresh Eggs (12 pcs)",
    shortName: "Eggs",
    category: "Poultry",
    price: 90,
    icon: Egg,
    defaultPct: 35,
    threshold: 25,
  },
  {
    name: "Fresh Hybrid Tomatoes 500g",
    shortName: "Tomatoes",
    category: "Produce",
    price: 32,
    icon: Apple,
    defaultPct: 14,
    threshold: 20,
  },
];

const DEFAULT_FALLBACK_ADAPTER: BackendCommerceAdapterInfo = {
  adapter_type: "mock",
  endpoint: "POST mcp.swiggy.com/im",
  mode: "Deterministic Mumbai Dark Store Fleet",
};

const DEFAULT_FALLBACK_CART: BackendCommerceCart = {
  cart_id: "cart-mumbai-sim",
  items: [
    {
      spin_id: "spin-milk-amul-1l",
      name: "Amul Taaza Homogenised Toned Milk",
      pack_size: "1 L",
      unit_price: 66,
      quantity: 1,
      total_price: 66,
    },
  ],
  item_total: 66,
  delivery_fee: 25,
  packaging_fee: 6,
  discount: 0,
  grand_total: 97,
  is_serviceable: true,
};

const DEFAULT_GO_TO_ITEMS: BackendCommerceProductItem[] = [
  {
    product_id: "prod-milk-01",
    name: "Amul Taaza Homogenised Toned Milk",
    category: "Dairy",
    variants: [
      {
        spin_id: "spin-milk-amul-1l",
        name: "Amul Taaza Homogenised Toned Milk",
        pack_size: "1 L",
        price: 66,
        mrp: 72,
        in_stock: true,
      },
    ],
  },
  {
    product_id: "prod-bread-01",
    name: "Whole Wheat Brown Bread",
    category: "Bakery",
    variants: [
      {
        spin_id: "spin-bread-wheat-400g",
        name: "Whole Wheat Brown Bread",
        pack_size: "400 g",
        price: 50,
        mrp: 55,
        in_stock: true,
      },
    ],
  },
  {
    product_id: "prod-eggs-01",
    name: "Farm Fresh White Eggs",
    category: "Poultry",
    variants: [
      {
        spin_id: "spin-eggs-pack-12",
        name: "Farm Fresh White Eggs (Pack of 12)",
        pack_size: "12 pcs",
        price: 90,
        mrp: 100,
        in_stock: true,
      },
    ],
  },
  {
    product_id: "prod-tomatoes-01",
    name: "Fresh Hybrid Tomatoes",
    category: "Produce",
    variants: [
      {
        spin_id: "spin-tomatoes-500g",
        name: "Fresh Hybrid Tomatoes",
        pack_size: "500 g",
        price: 32,
        mrp: 40,
        in_stock: true,
      },
    ],
  },
];

export function CustomerReplenishmentView({
  activeCustomer = DEFAULT_CUSTOMER_PERSONA,
  onCustomerChange,
  onPlaceOrder,
  onScheduleReminder,
  onSkipRestock,
  isLiveApiConnected = false,
}: CustomerReplenishmentViewProps) {
  const [resetKey, setResetKey] = useState(0);
  const [lastOrder, setLastOrder] = useState<CustomerOrderPayload | null>(null);
  const [copied, setCopied] = useState(false);

  // Phase 8: CommercePort & Swiggy Instamart State
  const [adapterInfo, setAdapterInfo] = useState<BackendCommerceAdapterInfo>(DEFAULT_FALLBACK_ADAPTER);
  const [cart, setCart] = useState<BackendCommerceCart>(DEFAULT_FALLBACK_CART);
  const [goToItems, setGoToItems] = useState<BackendCommerceProductItem[]>(DEFAULT_GO_TO_ITEMS);
  const [orderResult, setOrderResult] = useState<BackendCommerceOrderResult | null>(null);
  const [trackingInfo, setTrackingInfo] = useState<BackendCommerceTracking | null>(null);
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [checkoutConfirmationOpen, setCheckoutConfirmationOpen] = useState(false);
  const [explicitConfirmedCheckbox, setExplicitConfirmedCheckbox] = useState(false);
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<"UPI" | "COD">("UPI");
  const [isTrackingLoading, setIsTrackingLoading] = useState(false);

  // Load commerce adapter info and customer cart
  useEffect(() => {
    let isMounted = true;
    async function loadCommerce() {
      try {
        const [info, cartRes, goToRes] = await Promise.all([
          grocerApi.getCommerceAdapterInfo(),
          grocerApi.getCustomerCart(activeCustomer.id),
          grocerApi.getCustomerGoToItems(activeCustomer.id),
        ]);
        if (!isMounted) return;
        if (info) setAdapterInfo(info);
        if (cartRes) setCart(cartRes);
        if (goToRes && goToRes.length > 0) setGoToItems(goToRes);
      } catch {
        // Graceful fallback to offline defaults
      }
    }
    loadCommerce();
    return () => {
      isMounted = false;
    };
  }, [activeCustomer.id]);

  // Handle quantity modification in the active cart
  const handleUpdateQuantity = async (spinId: string, delta: number) => {
    if (!cart) return;
    const currentItem = cart.items.find((i) => i.spin_id === spinId);
    if (!currentItem && delta < 0) return;

    const currentQty = currentItem?.quantity ?? 0;
    const newQty = Math.max(0, currentQty + delta);

    const updatedItems = cart.items
      .map((i) => (i.spin_id === spinId ? { ...i, quantity: newQty, total_price: i.unit_price * newQty } : i))
      .filter((i) => i.quantity > 0);

    // If item was not in cart and adding it, lookup in go-to items
    if (!currentItem && delta > 0) {
      const foundGoTo = goToItems.find((g) => g.variants.some((v) => v.spin_id === spinId));
      const variant = foundGoTo?.variants.find((v) => v.spin_id === spinId);
      if (foundGoTo && variant) {
        updatedItems.push({
          spin_id: variant.spin_id,
          name: foundGoTo.name,
          pack_size: variant.pack_size,
          unit_price: variant.price,
          quantity: 1,
          total_price: variant.price,
        });
      }
    }

    const itemTotal = updatedItems.reduce((acc, it) => acc + it.total_price, 0);
    const deliveryFee = itemTotal > 0 ? (itemTotal >= 200 ? 0 : 25) : 0;
    const packagingFee = itemTotal > 0 ? 6 : 0;
    const grandTotal = itemTotal + deliveryFee + packagingFee;

    const newCart: BackendCommerceCart = {
      ...cart,
      items: updatedItems,
      item_total: itemTotal,
      delivery_fee: deliveryFee,
      packaging_fee: packagingFee,
      grand_total: grandTotal,
    };
    setCart(newCart);

    if (isLiveApiConnected) {
      try {
        const apiCart = await grocerApi.updateCustomerCart(
          activeCustomer.id,
          updatedItems.map((it) => ({ spin_id: it.spin_id, quantity: it.quantity }))
        );
        if (apiCart) setCart(apiCart);
      } catch {
        // Fallback kept
      }
    }
  };

  // Consequential checkout execution with explicit confirmation assertion (Spec §28.3)
  const handleExecuteCheckout = async () => {
    if (!explicitConfirmedCheckbox) {
      toast.error("Spec §28.3 Guard: Explicit human confirmation checkbox is mandatory.");
      return;
    }
    setIsCheckingOut(true);
    try {
      let result: BackendCommerceOrderResult | null = null;
      if (isLiveApiConnected) {
        result = await grocerApi.checkoutCustomer(activeCustomer.id, {
          payment_method: selectedPaymentMethod,
          explicit_confirmation: true,
        });
      }

      if (!result) {
        const orderId = `ORD-MUM-${Math.floor(1000 + Math.random() * 9000)}`;
        result = {
          order_id: orderId,
          cart_id: cart.cart_id,
          status: "ORDER_CONFIRMED",
          items: cart.items,
          payment_method: selectedPaymentMethod,
          grand_total: cart.grand_total,
          delivery_address: {
            id: "addr-01",
            label: "Home",
            street: activeCustomer.address,
            city: "Mumbai",
            postal_code: "400050",
            is_serviceable: true,
          },
          placed_at: new Date().toISOString(),
          tracking_url: `https://swiggy.com/track/${orderId}`,
        };
      }

      setOrderResult(result);
      setCheckoutConfirmationOpen(false);
      toast.success(`Order #${result.order_id} placed via ${adapterInfo.adapter_type === "swiggy_mcp" ? "Swiggy MCP Live" : "Simulated Instamart"}`);

      if (isLiveApiConnected) {
        const tracking = await grocerApi.trackCustomerOrder(activeCustomer.id, result.order_id);
        if (tracking) setTrackingInfo(tracking);
      } else {
        setTrackingInfo({
          order_id: result.order_id,
          status: "PACKING",
          eta_minutes: 11,
          driver_name: "Ramesh Kamble",
          driver_phone: "+91 98200 12345",
          last_updated_at: new Date().toISOString(),
        });
      }

      // Propagate order to parent page
      onPlaceOrder?.({
        customerId: activeCustomer.id,
        customerName: activeCustomer.name,
        homeStoreCode: activeCustomer.homeStoreCode,
        homeStoreName: activeCustomer.homeStoreName,
        items: result.items.map((it) => ({
          productId: it.spin_id,
          productName: it.name,
          quantity: it.quantity,
          priceINR: it.unit_price,
        })),
        totalINR: result.grand_total,
        paymentMethod: selectedPaymentMethod,
        address: activeCustomer.address,
      });
    } catch {
      toast.error("Checkout failed. Please verify authorization.");
    } finally {
      setIsCheckingOut(false);
    }
  };

  // Poll or advance real-time tracking
  const handleRefreshTracking = async () => {
    if (!orderResult) return;
    setIsTrackingLoading(true);
    try {
      if (isLiveApiConnected) {
        const tracking = await grocerApi.trackCustomerOrder(activeCustomer.id, orderResult.order_id);
        if (tracking) {
          setTrackingInfo(tracking);
          toast.success(`Tracking updated: ${tracking.status} (ETA ${tracking.eta_minutes}m)`);
        }
      } else {
        setTrackingInfo((prev) => {
          if (!prev) return null;
          const nextStatus = prev.status === "PACKING" ? "OUT_FOR_DELIVERY" : prev.status;
          const nextEta = Math.max(3, prev.eta_minutes - 2);
          return {
            ...prev,
            status: nextStatus,
            eta_minutes: nextEta,
            last_updated_at: new Date().toISOString(),
          };
        });
        toast.success("Tracking updated: Rider on route");
      }
    } finally {
      setIsTrackingLoading(false);
    }
  };

  // Handle order placement from PhoneMockup
  const handleOrderConfirmed = useCallback(
    async (payload: CustomerOrderPayload) => {
      setLastOrder(payload);
      onPlaceOrder?.(payload);

      try {
        let result: BackendCommerceOrderResult | null = null;
        if (isLiveApiConnected) {
          result = await grocerApi.checkoutCustomer(payload.customerId, {
            payment_method: payload.paymentMethod || "UPI",
            explicit_confirmation: true,
          });
        }
        if (!result) {
          const orderId = `ORD-MUM-${Math.floor(1000 + Math.random() * 9000)}`;
          result = {
            order_id: orderId,
            cart_id: "cart-mumbai-sim",
            status: "OUT_FOR_DELIVERY",
            items: payload.items.map((it) => ({
              spin_id: it.productId,
              name: it.productName,
              pack_size: "Standard",
              unit_price: it.priceINR,
              quantity: it.quantity,
              total_price: it.priceINR * it.quantity,
            })),
            payment_method: payload.paymentMethod || "UPI",
            grand_total: payload.totalINR,
            delivery_address: {
              id: "addr-01",
              label: "Home",
              street: payload.address || activeCustomer.address,
              city: "Mumbai",
              postal_code: "400050",
              is_serviceable: true,
            },
            placed_at: new Date().toISOString(),
            tracking_url: `https://swiggy.com/track/${orderId}`,
          };
        }
        setOrderResult(result);
        setTrackingInfo({
          order_id: result.order_id,
          status: "OUT_FOR_DELIVERY",
          eta_minutes: 11,
          driver_name: "Ramesh Kamble",
          driver_phone: "+91 98200 12345",
          last_updated_at: new Date().toISOString(),
        });
      } catch {
        // Continue
      }
    },
    [onPlaceOrder, isLiveApiConnected, activeCustomer.address]
  );

  // Reset phone simulation and commerce state
  const handleResetSimulator = useCallback(() => {
    setResetKey((prev) => prev + 1);
    setLastOrder(null);
    setOrderResult(null);
    setTrackingInfo(null);
    setExplicitConfirmedCheckbox(false);
    toast.info("Customer replenishment simulation reset");
  }, []);

  // Copy bot text
  const handleCopyMessage = () => {
    const firstName = activeCustomer.name.split(" ")[0];
    const item = activeCustomer.primaryDepletionItem || "Amul Taaza Milk 1L";
    const text = `Hi ${firstName}, your ${item} is almost finished. Tap below to order now.`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success("WhatsApp message copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  // Deplete an item to trigger phone alert
  const handleTriggerDepletion = (itemName: string) => {
    if (onCustomerChange) {
      onCustomerChange({
        ...activeCustomer,
        primaryDepletionItem: itemName,
      });
    }
    setResetKey((prev) => prev + 1);
    setLastOrder(null);
    toast.success(`Simulated depletion for ${itemName.split(" ")[0]}`);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6"
    >
      {/* 1. Header & Sub-Navigation Segmented Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-zinc-200">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
              <WhatsAppIcon className="w-3.5 h-3.5 shrink-0" />
              <span>Customer Replenishment Engine</span>
            </div>
            <div
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-medium border ${
                adapterInfo.adapter_type === "swiggy_mcp"
                  ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                  : "bg-zinc-100 text-zinc-700 border-zinc-200"
              }`}
              title={`Commerce Adapter: ${adapterInfo.endpoint}`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  adapterInfo.adapter_type === "swiggy_mcp" ? "bg-emerald-500 animate-pulse" : "bg-blue-500"
                }`}
              />
              <span className="font-bold">
                {adapterInfo.adapter_type === "swiggy_mcp" ? "Swiggy Instamart Live MCP" : "Simulated Instamart Adapter"}
              </span>
              <span className="text-zinc-400">|</span>
              <span className="text-[10px] text-zinc-500">{adapterInfo.endpoint.replace("POST ", "")}</span>
            </div>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-zinc-950 font-sans mt-2">
            Pantry-Aware Reordering via WhatsApp
          </h1>
          <p className="text-xs sm:text-sm text-zinc-600 max-w-2xl mt-1">
            Predicts when household essentials run low and sends a timely WhatsApp message.
            Households reorder in one tap without opening an app or searching catalogs.
          </p>
        </div>

      </div>

      {/* 3-Column Interactive Workbench: Household & Pantry Depletion (4 cols) | WhatsApp Simulator (4 cols) | Instamart Cart & Checkout (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* Column A: Household & Pantry Depletion Controls (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            
            {/* Household Persona Card */}
            <div className="p-4 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-zinc-700" />
                  <span className="text-xs font-bold text-zinc-900">Active Household</span>
                </div>
                <span className="text-[11px] font-mono text-zinc-500">25 Profiles</span>
              </div>

              {/* Persona Quick Grid */}
              <div className="grid grid-cols-2 gap-2">
                {SIMULATED_CUSTOMERS.slice(0, 4).map((cust) => {
                  const isSelected = cust.id === activeCustomer.id;
                  return (
                    <button
                      key={cust.id}
                      type="button"
                      onClick={() => {
                        onCustomerChange?.(cust);
                        setResetKey((prev) => prev + 1);
                        setLastOrder(null);
                      }}
                      className={`p-2 rounded-lg border text-left transition-all cursor-pointer ${
                        isSelected
                          ? "bg-blue-50/80 border-blue-500 ring-1 ring-blue-500 text-blue-950"
                          : "bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded-md bg-white border border-zinc-300 flex items-center justify-center font-mono font-bold text-[9px] text-zinc-800 shrink-0">
                          {cust.avatar}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="text-[11px] font-bold truncate leading-tight">{cust.name}</div>
                          <div className="text-[9px] text-zinc-500 truncate leading-tight mt-0.5 font-mono">
                            {cust.householdSize} People
                          </div>
                        </div>
                        {isSelected && <CheckCircle2 className="w-3 h-3 text-blue-600 shrink-0" />}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Household Metadata */}
              <div className="pt-2 border-t border-zinc-100 flex items-center justify-between text-[11px] text-zinc-600">
                <div className="flex items-center gap-1.5 truncate">
                  <MapPin className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                  <span className="truncate">{activeCustomer.address}</span>
                </div>
                <span className="font-mono font-medium shrink-0 ml-2">Every {activeCustomer.orderFrequencyDays}d</span>
              </div>
            </div>

            {/* Household Fridge & Pantry Monitor */}
            <div className="p-4 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-zinc-900 block">Fridge & Pantry Levels</span>
                  <span className="text-[10px] text-zinc-500">Tap an item to simulate running out</span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-700 font-semibold">
                  Live Gauges
                </span>
              </div>

              {/* Pantry Gauges List */}
              <div className="space-y-2.5">
                {PANTRY_ITEMS.map((item) => {
                  const isDepleted = activeCustomer.primaryDepletionItem === item.name;
                  const Icon = item.icon;
                  const levelPct = isDepleted ? item.defaultPct : 75;
                  const isLow = levelPct <= item.threshold;

                  return (
                    <div
                      key={item.name}
                      onClick={() => handleTriggerDepletion(item.name)}
                      className={`p-2.5 rounded-lg border transition-all cursor-pointer ${
                        isDepleted
                          ? "bg-amber-50/70 border-amber-300 ring-1 ring-amber-300"
                          : "bg-zinc-50 hover:bg-zinc-100/80 border-zinc-200"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <div className="flex items-center gap-2">
                          <div className={`w-6 h-6 rounded-md flex items-center justify-center ${
                            isDepleted ? "bg-amber-100 text-amber-800" : "bg-white text-zinc-600 border border-zinc-200"
                          }`}>
                            <Icon className="w-3.5 h-3.5" />
                          </div>
                          <div>
                            <span className="font-semibold text-zinc-900 text-[11px] block leading-tight">
                              {item.shortName}
                            </span>
                            <span className="text-[9px] text-zinc-500 font-mono">₹{item.price}</span>
                          </div>
                        </div>

                        <div className="text-right">
                          <span className={`text-[10.5px] font-mono font-bold ${
                            isLow ? "text-amber-700" : "text-emerald-700"
                          }`}>
                            {levelPct}%
                          </span>
                          <span className="text-[9px] text-zinc-400 block font-sans">
                            {isLow ? "⚠️ Reorder Alert" : "Adequate"}
                          </span>
                        </div>
                      </div>

                      {/* Level Progress Bar */}
                      <div className="w-full bg-zinc-200 h-1.5 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${
                            isLow ? "bg-amber-500" : "bg-emerald-500"
                          }`}
                          style={{ width: `${levelPct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Quick Scenario Triggers */}
              <div className="pt-2 border-t border-zinc-100 space-y-1.5">
                <span className="text-[10.5px] font-medium text-zinc-500 block">Simulate Morning Scenarios:</span>
                <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                  <button
                    type="button"
                    onClick={() => handleTriggerDepletion("Amul Taaza Milk 1L")}
                    className="p-1.5 rounded-md bg-zinc-50 hover:bg-zinc-100 border border-zinc-200 text-zinc-800 text-left font-medium transition-colors cursor-pointer truncate"
                  >
                    🥛 Morning Tea Rush
                  </button>
                  <button
                    type="button"
                    onClick={() => handleTriggerDepletion("Whole Wheat Bread 400g")}
                    className="p-1.5 rounded-md bg-zinc-50 hover:bg-zinc-100 border border-zinc-200 text-zinc-800 text-left font-medium transition-colors cursor-pointer truncate"
                  >
                    🍞 Breakfast Toast Alert
                  </button>
                </div>
              </div>
            </div>

            {/* Consumer Experience Highlights */}
            <div className="p-3.5 rounded-xl bg-zinc-50 border border-zinc-200/80 space-y-2 text-xs">
              <div className="flex items-center gap-2 font-bold text-zinc-900">
                <Zap className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>Zero-App Friction</span>
              </div>
              <p className="text-[11px] text-zinc-600 leading-relaxed">
                Households never have to unlock an app, search 50 brands, or remember to reorder milk. The notification arrives at their usual morning tea time.
              </p>
            </div>
          </div>

          {/* Column B: Authentic iPhone 17 Pro Spotlight (4 cols) */}
          <div className="lg:col-span-4 flex flex-col items-center">
            
            {/* Top Device Control Strip */}
            <div className="w-[290px] mb-2.5 flex items-center justify-between px-2.5 py-1.5 bg-white rounded-lg border border-zinc-200 shadow-2xs text-xs">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-[11px] font-semibold text-zinc-800">WhatsApp Simulator</span>
              </div>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleCopyMessage}
                  title="Copy WhatsApp Message"
                  className="p-1 rounded hover:bg-zinc-100 text-zinc-500 hover:text-zinc-800 transition-colors cursor-pointer"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
                <button
                  type="button"
                  onClick={handleResetSimulator}
                  title="Reset WhatsApp Conversation"
                  className="p-1 rounded hover:bg-zinc-100 text-zinc-500 hover:text-zinc-800 transition-colors cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Calibrated iPhone 17 Pro Frame */}
            <div className="w-[290px] h-[593px] aspect-[1800/3680] shrink-0 relative z-10">
              <PhoneMockup
                key={`${activeCustomer.id}-${activeCustomer.primaryDepletionItem}-${resetKey}`}
                activeScenario="milk_shortage"
                initialViewMode="whatsapp"
                activeCustomer={activeCustomer}
                onCustomerChange={onCustomerChange}
                onPlaceOrder={handleOrderConfirmed}
                onScheduleReminder={onScheduleReminder}
                onSkipRestock={onSkipRestock}
              />
            </div>
          </div>

          {/* Column C: Consumer Order Receipt & Express ETA (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            
            {/* Live Order Confirmation & Express Tracking Card */}
            <div className="p-4 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShoppingBag className="w-4 h-4 text-emerald-600" />
                  <span className="text-xs font-bold text-zinc-900">
                    {orderResult || lastOrder ? "Consumer Order Status" : "Instamart Commerce Cart"}
                  </span>
                </div>
                {orderResult || lastOrder ? (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] font-mono px-2 py-0.5 rounded-full font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                      {trackingInfo?.status || orderResult?.status || "DISPATCHED"}
                    </span>
                    <span className="text-[10px] font-mono text-zinc-400">
                      #{orderResult?.order_id || "ORD-MUM-8492"}
                    </span>
                  </div>
                ) : (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full font-bold bg-zinc-100 text-zinc-700 border border-zinc-200">
                    {cart.items.length} {cart.items.length === 1 ? "Item" : "Items"}
                  </span>
                )}
              </div>

              {orderResult || lastOrder ? (
                <div className="space-y-3 pt-1">
                  {/* Delivery ETA Pill */}
                  <div className="p-3 bg-emerald-50/80 rounded-lg border border-emerald-200 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 text-emerald-950 font-bold text-xs">
                        <Truck className="w-4 h-4 text-emerald-700" />
                        <span>Arriving in {trackingInfo?.eta_minutes ?? 11} Mins</span>
                      </div>
                      <button
                        type="button"
                        onClick={handleRefreshTracking}
                        disabled={isTrackingLoading}
                        className="text-[10px] font-mono font-semibold text-emerald-800 hover:text-emerald-950 flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-emerald-100 transition-colors cursor-pointer"
                        title="Poll Real-Time Delivery Tracking"
                      >
                        <RefreshCw className={`w-3 h-3 ${isTrackingLoading ? "animate-spin" : ""}`} />
                        <span>Refresh</span>
                      </button>
                    </div>
                    <p className="text-[10.5px] text-emerald-800 leading-snug">
                      Express rider dispatched to {orderResult?.delivery_address?.street || lastOrder?.address || activeCustomer.address}.
                    </p>

                    {/* Rider details card */}
                    <div className="pt-2 border-t border-emerald-200/60 flex items-center justify-between text-[11px] text-emerald-900">
                      <div className="flex items-center gap-1.5">
                        <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-[9px] font-mono">
                          RK
                        </span>
                        <div>
                          <span className="font-bold">{trackingInfo?.driver_name || "Ramesh Kamble"}</span>
                          <span className="text-[9.5px] text-emerald-700 block font-mono">
                            {trackingInfo?.driver_phone || "+91 98200 12345"} • Bajaj Chetak EV
                          </span>
                        </div>
                      </div>
                      <span className="text-[9px] font-mono font-bold bg-emerald-100 text-emerald-900 px-1.5 py-0.5 rounded">
                        LIVE GPS
                      </span>
                    </div>
                  </div>

                  {/* Itemized Breakdown */}
                  <div className="p-3 bg-zinc-50 rounded-lg border border-zinc-100 space-y-2">
                    <span className="text-[10px] font-mono text-zinc-500 block uppercase tracking-wider">
                      Itemized Receipt (Verified)
                    </span>
                    <div className="space-y-1.5">
                      {(orderResult?.items || (lastOrder ? lastOrder.items.map((it) => ({
                        spin_id: it.productId,
                        name: it.productName,
                        pack_size: "Standard",
                        unit_price: it.priceINR,
                        quantity: it.quantity,
                        total_price: it.priceINR * it.quantity,
                      })) : cart.items)).map((item, idx) => (
                        <div key={idx} className="flex items-center justify-between text-xs">
                          <span className="text-zinc-800 font-medium truncate max-w-[180px]">
                            {item.quantity}× {item.name.split(" ").slice(0, 3).join(" ")}
                          </span>
                          <span className="font-mono font-semibold text-zinc-900">
                            ₹{item.total_price || item.unit_price * item.quantity}
                          </span>
                        </div>
                      ))}
                    </div>

                    <div className="pt-2 border-t border-zinc-200 flex items-center justify-between text-xs font-bold text-zinc-950">
                      <span>Total ({orderResult?.payment_method || lastOrder?.paymentMethod || "UPI"})</span>
                      <span className="font-mono text-emerald-700">
                        ₹{orderResult?.grand_total || lastOrder?.totalINR || cart.grand_total}
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleResetSimulator}
                    className="w-full py-2 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-zinc-800 text-xs font-semibold transition-colors cursor-pointer flex items-center justify-center gap-1.5"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Test Another Order</span>
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Cart Items List */}
                  <div className="space-y-2">
                    {cart.items.length === 0 ? (
                      <div className="py-4 text-center text-xs text-zinc-500">
                        Cart is empty. Add pantry staples below.
                      </div>
                    ) : (
                      cart.items.map((item) => (
                        <div
                          key={item.spin_id}
                          className="p-2.5 rounded-lg border border-zinc-200 bg-zinc-50/70 flex items-center justify-between gap-2"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="text-xs font-bold text-zinc-900 truncate leading-tight">
                              {item.name}
                            </div>
                            <div className="flex items-center gap-1.5 mt-0.5">
                              <span className="text-[9px] font-mono bg-zinc-200/80 text-zinc-700 px-1.5 py-0.2 rounded">
                                {item.pack_size}
                              </span>
                              <span className="text-[9px] font-mono text-zinc-500">
                                ₹{item.unit_price} each
                              </span>
                            </div>
                          </div>

                          {/* Quantity stepper */}
                          <div className="flex items-center gap-1 bg-white border border-zinc-200 rounded-md p-0.5 shrink-0">
                            <button
                              type="button"
                              onClick={() => handleUpdateQuantity(item.spin_id, -1)}
                              className="w-5 h-5 rounded flex items-center justify-center text-zinc-600 hover:bg-zinc-100 transition-colors cursor-pointer"
                              title="Decrease quantity"
                            >
                              <Minus className="w-3 h-3" />
                            </button>
                            <span className="w-5 text-center font-mono text-xs font-bold text-zinc-900">
                              {item.quantity}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleUpdateQuantity(item.spin_id, 1)}
                              className="w-5 h-5 rounded flex items-center justify-center text-zinc-600 hover:bg-zinc-100 transition-colors cursor-pointer"
                              title="Increase quantity"
                            >
                              <Plus className="w-3 h-3" />
                            </button>
                          </div>

                          <div className="w-12 text-right font-mono font-bold text-xs text-zinc-900 shrink-0">
                            ₹{item.total_price}
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Quick-Add Staples (Go-To Items) */}
                  <div className="pt-2 border-t border-zinc-100 space-y-1.5">
                    <span className="text-[10.5px] font-medium text-zinc-500 block">
                      Quick-Add Household Staples:
                    </span>
                    <div className="grid grid-cols-2 gap-1.5">
                      {goToItems.slice(0, 4).map((item) => {
                        const variant = item.variants[0];
                        if (!variant) return null;
                        const isInCart = cart.items.some((i) => i.spin_id === variant.spin_id);
                        return (
                          <button
                            key={item.product_id}
                            type="button"
                            onClick={() => handleUpdateQuantity(variant.spin_id, 1)}
                            className={`p-1.5 rounded-md border text-left text-[10px] transition-colors cursor-pointer truncate flex items-center justify-between ${
                              isInCart
                                ? "bg-blue-50/60 border-blue-200 text-blue-900"
                                : "bg-white hover:bg-zinc-50 border-zinc-200 text-zinc-800"
                            }`}
                          >
                            <span className="truncate font-medium">
                              + {item.name.split(" ")[0]} ({variant.pack_size})
                            </span>
                            <span className="font-mono font-semibold ml-1 shrink-0">
                              ₹{variant.price}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Transparent Pricing Breakdown */}
                  <div className="p-3 bg-zinc-50 rounded-lg border border-zinc-100 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between text-zinc-600">
                      <span>Items Subtotal</span>
                      <span className="font-mono text-zinc-900">₹{cart.item_total}</span>
                    </div>
                    <div className="flex items-center justify-between text-zinc-600">
                      <span>Delivery Partner Fee</span>
                      <span className="font-mono text-zinc-900">
                        {cart.delivery_fee === 0 ? "FREE" : `₹${cart.delivery_fee}`}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-zinc-600">
                      <span>Packaging & Handling</span>
                      <span className="font-mono text-zinc-900">₹{cart.packaging_fee}</span>
                    </div>
                    {cart.discount > 0 && (
                      <div className="flex items-center justify-between text-emerald-700">
                        <span>Promo Discount</span>
                        <span className="font-mono">-₹{cart.discount}</span>
                      </div>
                    )}
                    <div className="pt-2 border-t border-zinc-200 flex items-center justify-between font-bold text-zinc-950">
                      <span>Grand Total</span>
                      <span className="font-mono text-emerald-700 text-sm">₹{cart.grand_total}</span>
                    </div>
                  </div>

                  {/* Consequential Action Checkout Button */}
                  <button
                    type="button"
                    onClick={() => {
                      setExplicitConfirmedCheckbox(false);
                      setCheckoutConfirmationOpen(true);
                    }}
                    disabled={cart.items.length === 0}
                    className="w-full py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors cursor-pointer shadow-2xs flex items-center justify-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>Consequential Checkout (Spec §28.3)</span>
                  </button>
                  <p className="text-[10px] text-zinc-400 text-center leading-snug">
                    Asserts explicit human confirmation before dispatching commercial order to fleet.
                  </p>
                </div>
              )}
            </div>

            {/* How It Replaces Traditional Apps */}
            <div className="p-4 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-3">
              <span className="text-xs font-bold text-zinc-900 block">Why WhatsApp Works Better</span>
              
              <div className="space-y-2 text-[11px]">
                <div className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">✓</span>
                  <div>
                    <strong className="text-zinc-900 block font-semibold">1-Tap Quick Action</strong>
                    <span className="text-zinc-500">Native buttons inside WhatsApp — no password, no OTP, no cart checkout screen.</span>
                  </div>
                </div>

                <div className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">✓</span>
                  <div>
                    <strong className="text-zinc-900 block font-semibold">Smart Complementary Suggestion</strong>
                    <span className="text-zinc-500">Pairs frequently consumed items like Fresh Bread with milk automatically.</span>
                  </div>
                </div>

                <div className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">✓</span>
                  <div>
                    <strong className="text-zinc-900 block font-semibold">Flexible Snooze</strong>
                    <span className="text-zinc-500">Customer not home? Tap &apos;Remind Later&apos; to defer notification by 2 hours.</span>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>

      {/* Consequential Checkout Authorization Modal (Spec §28.3 & §39.15) */}
      <AnimatePresence>
        {checkoutConfirmationOpen && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="w-full max-w-lg bg-white rounded-2xl border border-zinc-200 shadow-2xl overflow-hidden p-6 space-y-5"
            >
              {/* Modal Header */}
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-700 shrink-0">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-zinc-950 font-sans">
                      Consequential Checkout Authorization
                    </h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full font-bold bg-amber-100 text-amber-800 border border-amber-300">
                      Spec §28.3 Guard
                    </span>
                  </div>
                  <p className="text-xs text-zinc-500 mt-0.5 leading-snug">
                    Autonomous replenishment agents cannot execute financial or delivery transactions without explicit human authorization.
                  </p>
                </div>
              </div>

              {/* Order Verification Summary */}
              <div className="p-3.5 bg-zinc-50 rounded-xl border border-zinc-200 space-y-2.5 text-xs">
                <div className="flex items-center justify-between pb-2 border-b border-zinc-200 text-zinc-700">
                  <span className="font-medium">Customer & Destination:</span>
                  <span className="font-bold text-zinc-950 text-right truncate max-w-[240px]">
                    {activeCustomer.name} • {activeCustomer.address}
                  </span>
                </div>
                <div className="flex items-center justify-between text-zinc-700">
                  <span className="font-medium">Active Commerce Port:</span>
                  <span className="font-mono text-xs font-bold text-zinc-900">
                    {adapterInfo.adapter_type === "swiggy_mcp" ? "Swiggy Instamart Live MCP" : "Simulated Instamart Adapter"}
                  </span>
                </div>
                <div className="flex items-center justify-between text-zinc-700">
                  <span className="font-medium">Items to Fulfill:</span>
                  <span className="font-mono font-bold text-zinc-900">
                    {cart.items.reduce((acc, it) => acc + it.quantity, 0)} Units ({cart.items.length} SKUs)
                  </span>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-zinc-200 font-bold text-zinc-950">
                  <span>Grand Total Payable:</span>
                  <span className="font-mono text-emerald-700 text-sm">₹{cart.grand_total}</span>
                </div>
              </div>

              {/* Payment Method Selector */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-zinc-800 block">
                  Select Settlement Method:
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedPaymentMethod("UPI")}
                    className={`p-2.5 rounded-lg border text-left text-xs font-semibold flex items-center gap-2 transition-colors cursor-pointer ${
                      selectedPaymentMethod === "UPI"
                        ? "bg-emerald-50 border-emerald-500 text-emerald-950 ring-1 ring-emerald-500"
                        : "bg-white hover:bg-zinc-50 border-zinc-200 text-zinc-700"
                    }`}
                  >
                    <CheckCircle2 className={`w-4 h-4 ${selectedPaymentMethod === "UPI" ? "text-emerald-600" : "text-zinc-400"}`} />
                    <div>
                      <span className="block font-bold">UPI / Instant QR</span>
                      <span className="text-[10px] text-zinc-500 font-normal">GPay, PhonePe, Paytm</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedPaymentMethod("COD")}
                    className={`p-2.5 rounded-lg border text-left text-xs font-semibold flex items-center gap-2 transition-colors cursor-pointer ${
                      selectedPaymentMethod === "COD"
                        ? "bg-emerald-50 border-emerald-500 text-emerald-950 ring-1 ring-emerald-500"
                        : "bg-white hover:bg-zinc-50 border-zinc-200 text-zinc-700"
                    }`}
                  >
                    <CheckCircle2 className={`w-4 h-4 ${selectedPaymentMethod === "COD" ? "text-emerald-600" : "text-zinc-400"}`} />
                    <div>
                      <span className="block font-bold">Cash On Delivery</span>
                      <span className="text-[10px] text-zinc-500 font-normal">Pay rider at doorstep</span>
                    </div>
                  </button>
                </div>
              </div>

              {/* Mandatory Invariant Checkbox */}
              <label className="flex items-start gap-2.5 p-3 rounded-xl bg-amber-50/70 border border-amber-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={explicitConfirmedCheckbox}
                  onChange={(e) => setExplicitConfirmedCheckbox(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                />
                <span className="text-[11px] text-amber-950 leading-snug font-medium">
                  <strong>Explicit Confirmation:</strong> I authorize placing this commercial replenishment order for ₹{cart.grand_total} through the {adapterInfo.mode}. I confirm this checkout cannot be silently undone.
                </span>
              </label>

              {/* Modal Actions */}
              <div className="flex items-center justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setCheckoutConfirmationOpen(false)}
                  disabled={isCheckingOut}
                  className="px-4 py-2 rounded-lg border border-zinc-200 text-zinc-700 hover:bg-zinc-50 text-xs font-semibold transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleExecuteCheckout}
                  disabled={!explicitConfirmedCheckbox || isCheckingOut}
                  className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors cursor-pointer shadow-2xs flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isCheckingOut ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Fulfilling Order...</span>
                    </>
                  ) : (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      <span>Authorize & Dispatch Order</span>
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </motion.div>
  );
}
