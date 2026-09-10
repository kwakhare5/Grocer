import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://grocer-backend-qwk4.onrender.com";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}/api/auth/swiggy/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Failed to contact auth server";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
