"use client";

import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";

const clerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function AuthHeader() {
  if (!clerkKey) return null;

  return (
    <div className="flex items-center gap-3">
      <SignedOut>
        <SignInButton mode="modal">
          <button className="rounded-lg bg-green px-3 py-1.5 text-xs font-semibold text-bg shadow-sm transition hover:brightness-110">
            Sign In
          </button>
        </SignInButton>
      </SignedOut>
      <SignedIn>
        <UserButton />
      </SignedIn>
    </div>
  );
}
