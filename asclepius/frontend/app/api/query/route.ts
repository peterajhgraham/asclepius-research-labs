import { NextRequest } from "next/server";
import { BACKEND_URL, proxyPost } from "@/lib/backend";

export const maxDuration = 300;

export async function POST(request: NextRequest) {
  return proxyPost(request, "/query");
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const question = searchParams.get("question") ?? "";
  const mode = searchParams.get("mode") ?? "standard";
  const includePubmed = searchParams.get("include_pubmed") ?? "false";
  const verify = searchParams.get("verify") ?? "false";

  const url = new URL(`${BACKEND_URL}/query/stream`);
  url.searchParams.set("question", question);
  url.searchParams.set("mode", mode);
  url.searchParams.set("include_pubmed", includePubmed);
  url.searchParams.set("verify", verify);

  try {
    const resp = await fetch(url.toString(), {
      headers: { Accept: "text/event-stream" },
    });

    if (!resp.ok || !resp.body) {
      const errorEvent = `data: ${JSON.stringify({ type: "error", message: `Backend returned ${resp.status}` })}\n\n`;
      return new Response(errorEvent, {
        headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
      });
    }

    return new Response(resp.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch {
    const errorEvent = `data: ${JSON.stringify({ type: "error", message: "Backend unreachable" })}\n\n`;
    return new Response(errorEvent, {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });
  }
}
