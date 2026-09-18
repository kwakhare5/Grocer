const backendUrl = process.env.BACKEND_INTERNAL_URL?.replace(/\/+$/, "");

/**
 * Returns the private backend origin used by Next.js route handlers.
 *
 * This value is deliberately server-only: browser-visible environment variables
 * and deployed-host fallbacks are not appropriate for an authenticated proxy.
 */
export function getBackendUrl(): string {
  if (!backendUrl) {
    throw new Error("BACKEND_INTERNAL_URL is not configured");
  }

  return backendUrl;
}

export const USER_FACING_SERVICE_ERROR =
  "Grocer is temporarily unavailable. Please try again shortly.";
