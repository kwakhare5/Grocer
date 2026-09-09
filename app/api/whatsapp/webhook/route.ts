import { NextRequest, NextResponse } from 'next/server';

const VERIFY_TOKEN = process.env.WHATSAPP_VERIFY_TOKEN || "grocer_whatsapp_verify_token";
const BACKEND_URL = process.env.INTENT_BACKEND_URL || "https://grocer-backend-qwk4.onrender.com";

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const mode = searchParams.get("hub.mode");
    const token = searchParams.get("hub.verify_token");
    const challenge = searchParams.get("hub.challenge");

    if (mode === "subscribe" && token === VERIFY_TOKEN) {
      return new NextResponse(challenge || "", {
        status: 200,
        headers: { "Content-Type": "text/plain" },
      });
    }

    return new NextResponse("Forbidden", { status: 403 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Verification error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const rawBody = await req.text();
    const signature = req.headers.get("x-hub-signature-256") || "";
    const backendEndpoint = `${BACKEND_URL}/api/whatsapp/webhook`;

    const res = await fetch(backendEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Hub-Signature-256': signature,
      },
      body: rawBody,
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Proxy error';
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
