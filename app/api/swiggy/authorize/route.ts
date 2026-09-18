import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

const SWIGGY_AUTH_BASE = "https://mcp.swiggy.com/auth";
const DEFAULT_REDIRECT_URI = "https://grocerr.vercel.app";

function base64Url(buffer: Buffer): string {
  return buffer
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

async function getOrRegisterClientId(redirectUri: string): Promise<string> {
  const envClientId = process.env.SWIGGY_CLIENT_ID;
  if (envClientId) {
    return envClientId;
  }

  try {
    const regRes = await fetch(`${SWIGGY_AUTH_BASE}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_name: "GROCER",
        redirect_uris: [redirectUri],
      }),
    });

    if (regRes.ok) {
      const regData = await regRes.json();
      if (regData.client_id) {
        return regData.client_id;
      }
    }
  } catch (err) {
    console.warn("Failed to dynamically register Swiggy client:", err);
  }

  return "swiggy-mcp";
}

export async function GET(req: NextRequest) {
  try {
    const searchParams = req.nextUrl.searchParams;
    const redirectUriParam = searchParams.get("redirect_uri");
    const redirectUri = redirectUriParam || DEFAULT_REDIRECT_URI;

    const clientId = await getOrRegisterClientId(redirectUri);

    // PKCE S256 verifier & challenge
    const verifierBuffer = crypto.randomBytes(32);
    const codeVerifier = base64Url(verifierBuffer);
    const challengeHash = crypto.createHash("sha256").update(codeVerifier).digest();
    const codeChallenge = base64Url(challengeHash);
    const state = base64Url(crypto.randomBytes(16));

    const params = new URLSearchParams({
      response_type: "code",
      client_id: clientId,
      redirect_uri: redirectUri,
      code_challenge: codeChallenge,
      code_challenge_method: "S256",
      state: state,
      scope: "mcp:tools",
    });

    const authorizeUrl = `${SWIGGY_AUTH_BASE}/authorize?${params.toString()}`;

    const res = NextResponse.json({
      authorize_url: authorizeUrl,
      state: state,
      code_verifier: codeVerifier,
    });

    // Store state and verifier in temporary cookie (10 min TTL)
    res.cookies.set("swiggy_oauth_state", state, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production" || redirectUri.startsWith("https://"),
      sameSite: "lax",
      maxAge: 600,
      path: "/",
    });
    res.cookies.set("swiggy_pkce_verifier", codeVerifier, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production" || redirectUri.startsWith("https://"),
      sameSite: "lax",
      maxAge: 600,
      path: "/",
    });

    return res;
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Internal server error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
