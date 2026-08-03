import { NextRequest } from "next/server";
import { proxyPut } from "@/lib/backend";

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; entryId: string }> },
) {
  const { id, entryId } = await params;
  return proxyPut(request, `/dossiers/${id}/entries/${entryId}/notes`);
}
