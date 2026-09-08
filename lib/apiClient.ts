/**
 * GROCER's consumer-facing HTTP client.
 *
 * The browser talks only to the Intent API. Commerce execution remains behind
 * the FastAPI CommercePort boundary.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface BackendCommerceAdapterInfo {
  adapter_type: "mock" | "swiggy_mcp" | string;
  endpoint: string;
  mode: string;
}

export interface IntentBasketItem {
  spin_id: string;
  name: string;
  pack_size: string;
  quantity: number;
  unit_price: number;
  line_total: number;
  substituted: boolean;
}

export interface IntentPaymentOption {
  method: string;
  label: string;
  is_available: boolean;
  description: string | null;
  id: string | null;
  kind: string | null;
}

export interface IntentBasketSummary {
  cart_id: string;
  items: IntentBasketItem[];
  item_total: number;
  delivery_fee: number;
  packaging_fee: number;
  discount: number;
  grand_total: number;
  address_id: string | null;
  budget: number | null;
  within_budget: boolean;
  recovery_notes: string[];
  payment_options: IntentPaymentOption[];
  selected_payment_method: string;
  selected_payment_option_id: string | null;
  confirmation_nonce: string;
  confirmation_expires_at: string;
}

export interface IntentChoiceOption {
  index: number;
  spin_id: string;
  name: string;
  pack_size: string;
  price: number;
  score: number;
}

export interface IntentTurnResponse {
  session_id: string;
  conversation_state: string;
  user_message: string;
  basket_summary: IntentBasketSummary | null;
  clarification_options: IntentChoiceOption[] | null;
  requires_confirmation: boolean;
  order_id: string | null;
  order_total: number | null;
  payment_status: string | null;
  payment_url: string | null;
  child_orders: Array<{
    order_id: string | null;
    status: string;
    raw_status: string | null;
    success: boolean | null;
    grand_total: number | null;
  }>;
  events: string[];
}

export interface IntentSessionState {
  session_id: string;
  customer_id: string;
  conversation_state: string;
  cart_id: string | null;
  turn_count: number;
  has_pending_clarification: boolean;
  order_id: string | null;
  order_total: number | null;
  events: string[];
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = `request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // Preserve the HTTP status when the server did not return JSON.
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export async function checkIntentBackend(): Promise<boolean> {
  try {
    const response = await request<{ status: string }>("/api/health");
    return response.status === "healthy";
  } catch {
    return false;
  }
}

export async function sendIntentTurn(input: {
  sessionId: string;
  customerId: string;
  message: string;
  addressId?: string;
}): Promise<IntentTurnResponse> {
  return request<IntentTurnResponse>("/api/intent/chat", {
    method: "POST",
    body: JSON.stringify({
      session_id: input.sessionId,
      customer_id: input.customerId,
      message: input.message,
      address_id: input.addressId,
    }),
  });
}

export async function chooseIntentAlternative(
  sessionId: string,
  chosenSpinId: string,
): Promise<IntentTurnResponse> {
  return request<IntentTurnResponse>(
    `/api/intent/sessions/${encodeURIComponent(sessionId)}/choice`,
    {
      method: "POST",
      body: JSON.stringify({ chosen_spin_id: chosenSpinId }),
    },
  );
}

export async function confirmIntentCheckout(input: {
  sessionId: string;
  paymentMethod: string;
  addressId?: string;
  confirmationNonce: string;
}): Promise<IntentTurnResponse> {
  return request<IntentTurnResponse>(
    `/api/intent/sessions/${encodeURIComponent(input.sessionId)}/confirm`,
    {
      method: "POST",
      body: JSON.stringify({
        explicit_confirmation: true,
        payment_method: input.paymentMethod,
        address_id: input.addressId,
        confirmation_nonce: input.confirmationNonce,
      }),
    },
  );
}

export async function checkIntentPaymentStatus(
  sessionId: string,
): Promise<IntentTurnResponse> {
  return request<IntentTurnResponse>(
    `/api/intent/sessions/${encodeURIComponent(sessionId)}/payment-status`,
    { method: "POST" },
  );
}

export async function getIntentSession(sessionId: string): Promise<IntentSessionState> {
  return request<IntentSessionState>(
    `/api/intent/sessions/${encodeURIComponent(sessionId)}`,
  );
}

export async function clearIntentSession(sessionId: string): Promise<void> {
  await request<{ cleared: boolean }>(
    `/api/intent/sessions/${encodeURIComponent(sessionId)}`,
    { method: "DELETE" },
  );
}
