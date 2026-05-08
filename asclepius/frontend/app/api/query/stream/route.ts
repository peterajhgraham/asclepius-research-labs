import { NextRequest } from "next/server";
import { BACKEND_URL } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const question = searchParams.get("question") ?? "";
  const includePubmed = searchParams.get("include_pubmed") ?? "false";

  if (!question.trim()) {
    return new Response(
      'data: {"type":"error","message":"Missing question"}\n\n',
      { status: 400, headers: { "Content-Type": "text/event-stream" } },
    );
  }

  const backendUrl =
    `${BACKEND_URL}/query/stream` +
    `?question=${encodeURIComponent(question)}` +
    `&include_pubmed=${includePubmed}`;

  try {
    const upstream = await fetch(backendUrl, {
      method: "GET",
      headers: { Accept: "text/event-stream", "Cache-Control": "no-cache" },
    });

    if (!upstream.ok || !upstream.body) {
      return new Response(
        `data: {"type":"error","message":"Backend error ${upstream.status}"}\n\n`,
        { status: 502, headers: { "Content-Type": "text/event-stream" } },
      );
    }

    // Pipe the SSE stream directly through to the client
    return new Response(upstream.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        Connection: "keep-alive",
      },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(
      `data: {"type":"error","message":"${msg.replace(/"/g, "'")}"}\n\n`,
      { status: 502, headers: { "Content-Type": "text/event-stream" } },
    );
  }
}
