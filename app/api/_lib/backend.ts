/**
 * Grocer — Backend Service Discovery Helper.
 * Resolves the private FastAPI backend origin for Next.js API routes.
 */
export function getBackendUrl(): string {
  const url =
    process.env.BACKEND_INTERNAL_URL ||
    process.env.INTENT_BACKEND_URL ||
    "https://grocer-backend-qwk4.onrender.com";
  return url.replace(/\/+$/, "");
}
