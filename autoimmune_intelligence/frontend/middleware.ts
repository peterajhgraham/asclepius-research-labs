import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const clerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

function noopMiddleware(_request: NextRequest) {
  return NextResponse.next();
}

export default clerkKey ? clerkMiddleware() : noopMiddleware;

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)"],
};
