/**
 * GROCER's consumer-facing HTTP client.
 *
 * The browser talks only to the Intent API. Commerce execution remains behind
 * the FastAPI CommercePort boundary.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://grocer-backend-qwk4.onrender.com";

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
  address_display: string | null;
  budget: number | null;
  within_budget: boolean;
  recovery_notes: string[];
  payment_options: IntentPaymentOption[];
  selected_payment_method: string;
  selected_payment_option_id: string | null;
  selected_payment_option_kind: string | null;
  selected_payment_option_label: string | null;
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
  clarification_nonce: string | null;
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
    error: string | null;
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

export interface IntentSessionCredentials {
  session_id: string;
  customer_id: string;
  session_capability: string;
}

function capabilityHeaders(sessionCapability: string): HeadersInit {
  return { "X-Grocer-Session-Capability": sessionCapability };
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

export async function createIntentSession(): Promise<IntentSessionCredentials> {
  return request<IntentSessionCredentials>("/api/intent/sessions", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function sendIntentTurn(input: {
  sessionId: string;
  sessionCapability: string;
  message: string;
  addressId?: string;
}): Promise<IntentTurnResponse> {
  return request<IntentTurnResponse>("/api/intent/chat", {
    method: "POST",
    body: JSON.stringify({
      session_id: input.sessionId,
      message: input.message,
      address_id: input.addressId,
    }),
    headers: capabilityHeaders(input.sessionCapability),
  });
}

export async function chooseIntentAlternative(
  sessionId: string,
  sessionCapability: string,
  chosenSpinId: string,
  clarificationNonce: string,
): Promise<IntentTurnResponse> {
  return request<IntentTurnResponse>(
    `/api/intent/sessions/${encodeURIComponent(sessionId)}/choice`,
    {
      method: "POST",
      body: JSON.stringify({
        chosen_spin_id: chosenSpinId,
        clarification_nonce: clarificationNonce,
      }),
      headers: capabilityHeaders(sessionCapability),
    },
  );
}

export async function confirmIntentCheckout(input: {
  sessionId: string;
  sessionCapability: string;
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
      headers: capabilityHeaders(input.sessionCapability),
    },
  );
}

export async function checkIntentPaymentStatus(
  sessionId: string,
  sessionCapability: string,
): Promise<IntentTurnResponse> {
  return request<IntentTurnResponse>(
    `/api/intent/sessions/${encodeURIComponent(sessionId)}/payment-status`,
    { method: "POST", headers: capabilityHeaders(sessionCapability) },
  );
}

export async function getIntentSession(
  sessionId: string,
  sessionCapability: string,
): Promise<IntentSessionState> {
  return request<IntentSessionState>(
    `/api/intent/sessions/${encodeURIComponent(sessionId)}`,
    { headers: capabilityHeaders(sessionCapability) },
  );
}

export async function clearIntentSession(
  sessionId: string,
  sessionCapability: string,
): Promise<void> {
  await request<{ cleared: boolean }>(
    `/api/intent/sessions/${encodeURIComponent(sessionId)}`,
    { method: "DELETE", headers: capabilityHeaders(sessionCapability) },
  );
}

// ---------------------------------------------------------------------------
// Developer Live-Debug Telemetry
// ---------------------------------------------------------------------------

export interface DebugItemTelemetry {
  item_id: string;
  name: string;
  original_requested_quantity: string;
  interpreted_meaning: string;
  dimension: string | null;
  canonical_amount: number | null;
  quantity_is_explicit: boolean;
  pack_size_preference: string | null;
  selected_provider_product: string | null;
  selected_spin_id: string | null;
  provider_pack_size: string | null;
  planned_cart_quantity: number | null;
  expected_fulfillment: string;
  actual_canonical_cart_quantity: number | null;
  actual_fulfillment: string;
  provider_max_quantity: number | null;
  is_mock: boolean;
  integration_note: string | null;
}

export interface DebugSessionSummary {
  session_id: string;
  customer_id: string;
  conversation_state: string;
  turn_count: number;
  original_user_request: string;
  event_count: number;
  has_cart: boolean;
  is_active: boolean;
}

export interface DebugLiveInspectionResponse {
  has_session: boolean;
  session_id: string;
  masked_customer_id: string;
  conversation_state: string;
  turn_count: number;
  original_user_request: string;
  sanitized_address: string | null;
  cart_id: string | null;
  order_id: string | null;
  items: DebugItemTelemetry[];
  verification_result: {
    status?: string;
    violations?: Array<{ violation_code: string; target: string; detail: string; is_hard: boolean }>;
    deviations?: Array<{ preference_type: string; target: string; expected: string; actual: string }>;
    budget_delta?: number;
    is_stale?: boolean;
    confidence?: number;
    [key: string]: unknown;
  };
  recovery_classification: {
    state?: string;
    has_recovery?: boolean;
    failure_class?: string;
    can_auto_apply?: boolean;
    attempt_number?: number;
    [key: string]: unknown;
  };
  clarification_required: boolean;
  clarification_details: {
    item_name?: string;
    question?: string;
    candidate_count?: number;
    candidates?: Array<{ spin_id: string; name: string; pack_size: string; price: number; score: number }>;
  } | null;
  relevant_safe_event_names: string[];
  is_mock: boolean;
  integration_points: string[];
}

export async function fetchLatestDebugTelemetry(): Promise<DebugLiveInspectionResponse> {
  return request<DebugLiveInspectionResponse>("/api/debug/latest");
}

export async function fetchDebugSessions(): Promise<DebugSessionSummary[]> {
  return request<DebugSessionSummary[]>("/api/debug/sessions");
}

export async function fetchDebugSessionById(sessionId: string): Promise<DebugLiveInspectionResponse> {
  return request<DebugLiveInspectionResponse>(`/api/debug/sessions/${encodeURIComponent(sessionId)}`);
}
