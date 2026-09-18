import { NextResponse } from "next/server";
import {
  getBackendUrl,
  USER_FACING_SERVICE_ERROR,
} from "../../../_lib/backend";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const res = await fetch(`${getBackendUrl()}/api/auth/swiggy/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: "Unable to start the Swiggy connection. Please try again." },
        { status: res.status },
      );
    }

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: USER_FACING_SERVICE_ERROR }, { status: 502 });
  }
}
