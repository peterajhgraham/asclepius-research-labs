import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/backend";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ hash: string }> },
) {
  const { hash } = await params;
  if (!/^[a-fA-F0-9]{16,128}$/.test(hash)) {
    return NextResponse.json({ error: "Invalid image hash" }, { status: 400 });
  }
  try {
    const res = await fetch(`${BACKEND_URL}/images/${hash}`);
    if (!res.ok) {
      return NextResponse.json(
        { error: `Image not found (${res.status})` },
        { status: res.status },
      );
    }
    const arrayBuffer = await res.arrayBuffer();
    return new NextResponse(arrayBuffer, {
      status: 200,
      headers: {
        "Content-Type": res.headers.get("Content-Type") ?? "image/jpeg",
        "Cache-Control": "public, max-age=31536000, immutable",
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { error: `Image proxy failed: ${message}` },
      { status: 502 },
    );
  }
}
