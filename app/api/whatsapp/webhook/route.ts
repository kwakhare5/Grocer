import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from "../../_lib/backend";

const verifyToken = process.env.WHATSAPP_VERIFY_TOKEN;

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const mode = searchParams.get("hub.mode");
    const token = searchParams.get("hub.verify_token");
    const challenge = searchParams.get("hub.challenge");

    if (verifyToken && mode === "subscribe" && token === verifyToken) {
      return new NextResponse(challenge || "", {
        status: 200,
        headers: { "Content-Type": "text/plain" },
      });
    }

    return new NextResponse("Forbidden", { status: 403 });
  } catch {
    return NextResponse.json({ error: "Webhook verification is unavailable." }, { status: 503 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const rawBody = await req.text();
    const signature = req.headers.get("x-hub-signature-256") || "";
    const backendEndpoint = `${getBackendUrl()}/api/whatsapp/webhook`;

    const res = await fetch(backendEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Hub-Signature-256': signature,
      },
      body: rawBody,
      signal: AbortSignal.timeout(10000),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error("WhatsApp webhook proxy encountered error or timeout:", error);
    // Return HTTP 200 to Meta so it does not trigger aggressive retry loops during backend cold-starts
    return NextResponse.json({ status: "acknowledged", error: "Proxy forwarded or timed out" }, { status: 200 });
  }
}
