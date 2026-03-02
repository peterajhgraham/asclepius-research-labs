import { NextRequest, NextResponse } from "next/server";

function resolveBackendUrl(): string {
  const raw =
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
  // Ensure the URL has a protocol — Railway / Vercel env vars sometimes omit it
  if (raw.startsWith("http://") || raw.startsWith("https://")) {
    return raw;
  }
  return `https://${raw}`;
}

const BACKEND_URL = resolveBackendUrl();

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      {
        error: `Backend unreachable at ${BACKEND_URL}/query — ${message}`,
      },
      { status: 502 },
    );
  }
}
