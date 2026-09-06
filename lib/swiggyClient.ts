/**
 * Client library for Swiggy Instamart MCP OAuth 2.1 PKCE Flow and Tool Execution.
 */

const SWIGGY_AUTH_URL = "https://mcp.swiggy.com/auth/authorize";
const CLIENT_ID = "swiggy-mcp";
const REDIRECT_URI = "https://grocerr.vercel.app";

// Helper for Base64URL encoding
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

// Generate random string
function generateRandomString(length: number): string {
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return base64UrlEncode(array.buffer);
}

// Compute SHA-256 code challenge
async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64UrlEncode(digest);
}

export interface SwiggyTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  scope: string;
}

export class SwiggyClient {
  private static TOKEN_KEY = "swiggy_access_token";
  private static EXPIRES_KEY = "swiggy_token_expires_at";
  private static VERIFIER_KEY = "swiggy_pkce_verifier";
  private static STATE_KEY = "swiggy_oauth_state";

  /**
   * Initiates Swiggy OAuth 2.1 PKCE login flow.
   * Redirects user to Swiggy consent UI.
   */
  static async startLogin(): Promise<void> {
    if (typeof window === "undefined") return;

    const verifier = generateRandomString(32);
    const challenge = await generateCodeChallenge(verifier);
    const state = generateRandomString(16);

    // Persist in localStorage for recovery after redirect
    localStorage.setItem(this.VERIFIER_KEY, verifier);
    localStorage.setItem(this.STATE_KEY, state);

    // Current origin fallback for local dev vs production
    const redirectUri = window.location.origin.includes("localhost")
      ? window.location.origin
      : REDIRECT_URI;

    const params = new URLSearchParams({
      response_type: "code",
      client_id: CLIENT_ID,
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
   */
  static async handleAuthCallback(code: string, state: string): Promise<boolean> {
    if (typeof window === "undefined") return false;

    const savedState = localStorage.getItem(this.STATE_KEY);
    const verifier = localStorage.getItem(this.VERIFIER_KEY);

    if (!verifier || (savedState && savedState !== state)) {
      console.error("Swiggy OAuth state/verifier validation failed");
      return false;
    }

    const redirectUri = window.location.origin.includes("localhost")
      ? window.location.origin
      : REDIRECT_URI;

    try {
      const resp = await fetch("/api/swiggy/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          code_verifier: verifier,
          redirect_uri: redirectUri,
        }),
      });

      if (!resp.ok) {
        const err = await resp.json();
        console.error("Failed to exchange Swiggy code:", err);
        return false;
      }

      const data: SwiggyTokenResponse = await resp.json();
      const expiresAt = Date.now() + data.expires_in * 1000;

      localStorage.setItem(this.TOKEN_KEY, data.access_token);
      localStorage.setItem(this.EXPIRES_KEY, expiresAt.toString());

      // Clean up verifier
      localStorage.removeItem(this.VERIFIER_KEY);
      localStorage.removeItem(this.STATE_KEY);

      return true;
    } catch (err) {
      console.error("Error exchanging Swiggy code:", err);
      return false;
    }
  }

  /**
   * Get active access token if not expired.
   */
  static getAccessToken(): string | null {
    if (typeof window === "undefined") return null;

    const token = localStorage.getItem(this.TOKEN_KEY);
    const expiresAt = localStorage.getItem(this.EXPIRES_KEY);

    if (!token || !expiresAt) return null;

    // Check expiry with 60s buffer
    if (Date.now() > parseInt(expiresAt, 10) - 60000) {
      this.disconnect();
      return null;
    }

    return token;
  }

  /**
   * Check if Swiggy Instamart is connected.
   */
  static isConnected(): boolean {
    return !!this.getAccessToken();
  }

  /**
   * Disconnect active Swiggy session.
   */
  static disconnect(): void {
    if (typeof window === "undefined") return;
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.EXPIRES_KEY);
  }

  /**
   * Execute JSON-RPC tool call against Swiggy Instamart MCP gateway.
   */
  static async callTool<T = unknown>(
    toolName: string,
    args: Record<string, unknown> = {}
  ): Promise<T | null> {

    const token = this.getAccessToken();
    if (!token) return null;

    try {
      const resp = await fetch("/api/swiggy/mcp", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          tool_name: toolName,
          arguments: args,
        }),
      });

      if (resp.status === 401) {
        this.disconnect();
        return null;
      }

      const data = await resp.json();
      return data?.result || data;
    } catch (err) {
      console.error(`Failed to call Swiggy tool ${toolName}:`, err);
      return null;
    }
  }
}
