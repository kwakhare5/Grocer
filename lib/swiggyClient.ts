/**
 * Client library for Swiggy Instamart OAuth 2.1 PKCE Flow.
 *
 * Security Invariants:
 * - No raw access tokens stored in plaintext browser localStorage.
 * - Sensitive credentials remain server-side in HttpOnly cookies and TokenVault.
 * - Dynamic Client Registration (RFC 7591) and S256 PKCE challenge supported.
 */

const SWIGGY_AUTH_URL = "https://mcp.swiggy.com/auth/authorize";
const DEFAULT_REDIRECT_URI = "https://grocerr.vercel.app";

function base64UrlEncode(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function generateRandomString(length: number): string {
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return base64UrlEncode(array.buffer);
}

async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64UrlEncode(digest);
}

export class SwiggyClient {
  private static AUTH_FLAG_KEY = "swiggy_authenticated";
  private static VERIFIER_KEY = "swiggy_pkce_verifier";
  private static STATE_KEY = "swiggy_oauth_state";

  /**
   * Initiates Swiggy OAuth 2.1 PKCE login flow.
   * Fetches registered client_id & redirect from server or generates S256 PKCE locally.
   */
  static async startLogin(customRedirect?: string): Promise<void> {
    if (typeof window === "undefined") return;

    const redirectUri =
      customRedirect ||
      (window.location.origin.includes("localhost")
        ? window.location.origin
        : DEFAULT_REDIRECT_URI);

    try {
      // Prefer server-side authorize endpoint if available
      const resp = await fetch(
        `/api/swiggy/authorize?redirect_uri=${encodeURIComponent(redirectUri)}&customer_id=cust-web`,
        { method: "GET" }
      );
      if (resp.ok) {
        const data = await resp.json();
        if (data.authorize_url) {
          if (data.code_verifier) {
            sessionStorage.setItem(this.VERIFIER_KEY, data.code_verifier);
          }
          if (data.state) {
            sessionStorage.setItem(this.STATE_KEY, data.state);
          }
          window.location.href = data.authorize_url;
          return;
        }
      }
    } catch {
      // Fall back to client-side PKCE generation
    }

    const verifier = generateRandomString(32);
    const challenge = await generateCodeChallenge(verifier);
    const state = generateRandomString(16);

    sessionStorage.setItem(this.VERIFIER_KEY, verifier);
    sessionStorage.setItem(this.STATE_KEY, state);

    const params = new URLSearchParams({
      response_type: "code",
      client_id: "swiggy-mcp",
      redirect_uri: redirectUri,
      code_challenge: challenge,
      code_challenge_method: "S256",
      state: state,
      scope: "mcp:tools",
    });

    window.location.href = `${SWIGGY_AUTH_URL}?${params.toString()}`;
  }

  /**
   * Handles callback redirect when `?code=` is detected.
   * Exchanges authorization code server-side and stores session securely in HttpOnly cookie.
   */
  static async handleAuthCallback(
    code: string,
    state: string,
    customRedirect?: string
  ): Promise<boolean> {
    if (typeof window === "undefined") return false;

    const savedState = sessionStorage.getItem(this.STATE_KEY);
    const verifier = sessionStorage.getItem(this.VERIFIER_KEY);

    if (savedState && savedState !== state) {
      console.error("Swiggy OAuth state mismatch: anti-CSRF check failed");
      return false;
    }

    const redirectUri =
      customRedirect ||
      (window.location.origin.includes("localhost")
        ? window.location.origin
        : DEFAULT_REDIRECT_URI);

    try {
      const resp = await fetch("/api/swiggy/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          state,
          code_verifier: verifier || undefined,
          redirect_uri: redirectUri,
          customer_id: "cust-web",
        }),
      });

      if (!resp.ok) {
        const err = await resp.json();
        console.error("Failed to exchange Swiggy code:", err);
        return false;
      }

      // Cleanup ephemeral PKCE handshake verifiers
      sessionStorage.removeItem(this.VERIFIER_KEY);
      sessionStorage.removeItem(this.STATE_KEY);

      // Record authenticated session flag in sessionStorage (never raw token)
      sessionStorage.setItem(this.AUTH_FLAG_KEY, "true");
      return true;
    } catch (err) {
      console.error("Error exchanging Swiggy code:", err);
      return false;
    }
  }

  /**
   * Check if Swiggy Instamart is connected.
   */
  static async isConnected(customerId: string = "cust-web"): Promise<boolean> {
    if (typeof window === "undefined") return false;

    try {
      const res = await fetch(`/api/swiggy/status?customer_id=${encodeURIComponent(customerId)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.authenticated) {
          sessionStorage.setItem(this.AUTH_FLAG_KEY, "true");
          return true;
        }
      }
    } catch {
      // Fall back to session storage flag
    }

    return sessionStorage.getItem(this.AUTH_FLAG_KEY) === "true";
  }

  /**
   * Disconnect active Swiggy session.
   */
  static async disconnect(customerId: string = "cust-web"): Promise<void> {
    if (typeof window === "undefined") return;
    sessionStorage.removeItem(this.AUTH_FLAG_KEY);
    sessionStorage.removeItem(this.VERIFIER_KEY);
    sessionStorage.removeItem(this.STATE_KEY);

    try {
      await fetch("/api/swiggy/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_id: customerId }),
      });
    } catch {
      // Ignore network errors on logout
    }
  }
}
