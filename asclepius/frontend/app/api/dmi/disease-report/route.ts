import { NextRequest } from "next/server";
import { proxyPost } from "@/lib/backend";

// Report generation runs several LLM passes; allow it past Vercel's default timeout.
export const maxDuration = 300;

export async function POST(request: NextRequest) {
  return proxyPost(request, "/dmi/disease-report");
}
