import { NextRequest } from "next/server";
import { proxyPost } from "@/lib/backend";

export async function POST(request: NextRequest) {
  return proxyPost(request, "/graph/subgraph");
}
