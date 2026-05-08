import { NextRequest } from "next/server";
import { proxyPost, proxyGet } from "@/lib/backend";

export async function GET() {
  return proxyGet("/dossiers");
}

export async function POST(request: NextRequest) {
  return proxyPost(request, "/dossiers");
}
