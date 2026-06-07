import { NextRequest } from "next/server";
import { proxyPost } from "@/lib/backend";

// Comparative synthesis runs several LLM passes; allow it past the default timeout.
export const maxDuration = 300;

export async function POST(request: NextRequest) {
  return proxyPost(request, "/compare");
}
