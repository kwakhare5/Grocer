import { NextResponse } from "next/server";
import {
  getBackendUrl,
  USER_FACING_SERVICE_ERROR,
} from "../../_lib/backend";

export async function POST(request: Request) {
  try {
    const authHeader = request.headers.get("Authorization");
    const body = await request.json();
    const res = await fetch(`${getBackendUrl()}/api/simulator/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: USER_FACING_SERVICE_ERROR }, { status: 502 });
  }
}
