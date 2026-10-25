import { NextRequest, NextResponse } from "next/server";
import { getBackendUrl } from "../../../_lib/backend";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { code, state } = body || {};

    if (!code || !state) {
      return NextResponse.json(
        { error: "Authorization code and state are required" },
        { status: 400 }
      );
    }

    const backendUrl = getBackendUrl();
    const response = await fetch(`${backendUrl}/api/auth/swiggy/callback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, state }),
    });

    const data = await response.json();
    if (!response.ok) {
      return NextResponse.json(
        { error: data.error || data.detail || "Token exchange failed" },
        { status: response.status }
      );
    }

    return NextResponse.json(data);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Failed to reach Grocer backend service during token exchange";
    return NextResponse.json(
      { error: message },
      { status: 502 }
    );
  }
}
