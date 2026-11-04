import { NextRequest, NextResponse } from "next/server";
import { getBackendUrl } from "../../../_lib/backend";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const phone = body?.phone;

    if (!phone || typeof phone !== "string") {
      return NextResponse.json(
        { error: "Enter a 10-digit Indian mobile number." },
        { status: 400 },
      );
    }

    const forwarded = req.headers.get("x-forwarded-for");
    const backendUrl = getBackendUrl();
    const response = await fetch(`${backendUrl}/api/auth/whatsapp/start`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(forwarded ? { "x-forwarded-for": forwarded } : {}),
      },
      body: JSON.stringify({ phone }),
    });

    const data = await response.json();
    if (!response.ok) {
      return NextResponse.json(
        { error: data.error || data.detail || "Could not create a connect code." },
        { status: response.status },
      );
    }

    return NextResponse.json(data);
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Failed to reach Grocer backend service";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
