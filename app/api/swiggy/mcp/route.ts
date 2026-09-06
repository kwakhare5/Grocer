import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const authHeader = req.headers.get("authorization");
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return NextResponse.json(
        { error: "Unauthorized: Missing Bearer token" },
        { status: 401 }
      );
    }

    const { tool_name, arguments: toolArgs } = await req.json();
    if (!tool_name) {
      return NextResponse.json(
        { error: "Missing required tool_name" },
        { status: 400 }
      );
    }

    const mcpPayload = {
      jsonrpc: "2.0",
      method: "tools/call",
      params: {
        name: tool_name,
        arguments: toolArgs || {},
      },
      id: Date.now(),
    };

    const resp = await fetch("https://mcp.swiggy.com/im", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: authHeader,
      },
      body: JSON.stringify(mcpPayload),
    });

    const data = await resp.json();

    if (!resp.ok) {
      return NextResponse.json(
        { error: data.error || `Swiggy MCP error: ${resp.status}` },
        { status: resp.status }
      );
    }

    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Internal server error" },
      { status: 500 }
    );
  }
}
