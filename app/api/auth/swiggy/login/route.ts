import { NextRequest, NextResponse } from "next/server";
import { getBackendUrl } from "../../../_lib/backend";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const token = body?.token;

    if (!token || typeof token !== "string") {
      return NextResponse.json(
        { error: "Open the connect link sent by the Grocer bot on WhatsApp." },
        { status: 400 },
      );
    }

    const backendUrl = getBackendUrl();
    const response = await fetch(`${backendUrl}/api/auth/swiggy/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });

    const data = await response.json();
    if (!response.ok) {
      return NextResponse.json(
        { error: data.error || data.detail || "Backend login initiation failed" },
        { status: response.status }
      );
    }

    return NextResponse.json(data);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Failed to reach Grocer backend service";
    return NextResponse.json(
      { error: message },
      { status: 502 }
    );
  }
}
