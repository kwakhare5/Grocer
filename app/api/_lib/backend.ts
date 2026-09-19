const backendUrl = (
  process.env.BACKEND_INTERNAL_URL ||
  process.env.INTENT_BACKEND_URL ||
  "https://grocer-backend-qwk4.onrender.com"
).replace(/\/+$/, "");

/**
 * Returns the private backend origin used by Next.js route handlers.
 */
export function getBackendUrl(): string {
  return backendUrl;
}

export const USER_FACING_SERVICE_ERROR =
  "Grocer is temporarily unavailable. Please try again shortly.";
