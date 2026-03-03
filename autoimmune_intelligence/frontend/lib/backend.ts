import { NextRequest, NextResponse } from "next/server";

function resolveBackendUrl(): string {
  const raw =
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
  if (raw.startsWith("http://") || raw.startsWith("https://")) {
    return raw;
  }
  return `https://${raw}`;
}

export const BACKEND_URL = resolveBackendUrl();

export async function proxyPost(request: NextRequest, path: string) {
  try {
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { error: `Backend unreachable at ${BACKEND_URL}${path} — ${message}` },
      { status: 502 },
    );
  }
}

export async function proxyGet(path: string) {
  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { error: `Backend unreachable at ${BACKEND_URL}${path} — ${message}` },
      { status: 502 },
    );
  }
}
