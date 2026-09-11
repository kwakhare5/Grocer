import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://grocer-backend-qwk4.onrender.com";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const phone = searchParams.get("phone_number");
    const targetUrl = phone
      ? `${BACKEND_URL}/api/auth/swiggy/status?phone_number=${encodeURIComponent(phone)}`
      : `${BACKEND_URL}/api/auth/swiggy/status`;

    const res = await fetch(targetUrl, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Failed to check auth status";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
