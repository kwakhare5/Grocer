import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { code, code_verifier, redirect_uri } = await req.json();

    if (!code || !code_verifier) {
      return NextResponse.json(
        { error: "Missing required parameters: code and code_verifier" },
        { status: 400 }
      );
    }

    const payload = {
      grant_type: "authorization_code",
      client_id: "swiggy-mcp",
      code,
      code_verifier,
      redirect_uri: redirect_uri || "https://grocerr.vercel.app",
    };

    const swiggyRes = await fetch("https://mcp.swiggy.com/auth/token", {
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

    return NextResponse.json(data);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Internal server error";
    return NextResponse.json(
      { error: message },
      { status: 500 }
    );
  }
}

