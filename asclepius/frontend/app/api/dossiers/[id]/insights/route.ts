import { NextRequest } from "next/server";
import { proxyGet } from "@/lib/backend";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyGet(`/dossiers/${id}/insights`);
}
