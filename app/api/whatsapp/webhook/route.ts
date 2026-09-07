import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.INTENT_BACKEND_URL || 'http://127.0.0.1:8000';

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const qs = searchParams.toString();
    const backendEndpoint = `${BACKEND_URL}/api/whatsapp/webhook${qs ? `?${qs}` : ""}`;
    const res = await fetch(backendEndpoint, { method: "GET" });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": "text/plain" },
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Proxy error";
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
