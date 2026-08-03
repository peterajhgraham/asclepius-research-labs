import { NextRequest } from "next/server";
import { proxyGet, proxyDelete } from "@/lib/backend";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyGet(`/dossiers/${id}`);
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyDelete(`/dossiers/${id}`);
}
