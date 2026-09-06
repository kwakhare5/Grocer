import { NextRequest, NextResponse } from "next/server";

const SWIGGY_AUTH_BASE = "https://mcp.swiggy.com/auth";
const DEFAULT_REDIRECT_URI = "https://grocerr.vercel.app";

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
    console.warn("Failed to dynamically register Swiggy client, using fallback:", err);
  }

  return "swiggy-mcp";
}

export async function POST(req: NextRequest) {
  try {
    const { code, code_verifier, redirect_uri, customer_id } = await req.json();

    if (!code || !code_verifier) {
      return NextResponse.json(
        { error: "Missing required parameters: code and code_verifier" },
        { status: 400 }
      );
    }

    const effectiveRedirect = redirect_uri || DEFAULT_REDIRECT_URI;
    const clientId = await getOrRegisterClientId(effectiveRedirect);

    const payload = {
      grant_type: "authorization_code",
      client_id: clientId,
      code,
      code_verifier,
      redirect_uri: effectiveRedirect,
    };

    const swiggyRes = await fetch(`${SWIGGY_AUTH_BASE}/token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await swiggyRes.json();

    if (!swiggyRes.ok) {
      return NextResponse.json(
        { error: data.error_description || data.error || "Failed to exchange token" },
        { status: swiggyRes.status }
      );
    }

    const expiresIn = typeof data.expires_in === "number" ? data.expires_in : 432000;
    const customer = customer_id || "cust-default";

    // Create response without exposing raw token in body
    const response = NextResponse.json({
      success: true,
      authenticated: true,
      customer_id: customer,
      expires_in: expiresIn,
      scope: data.scope || "mcp:tools",
    });

    // Set secure HTTP-only cookie with SameSite=Lax
    response.cookies.set("swiggy_session", data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production" || effectiveRedirect.startsWith("https://"),
      sameSite: "lax",
      maxAge: expiresIn,
      path: "/",
    });

    return response;
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Internal server error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
