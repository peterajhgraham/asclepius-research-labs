import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import AuthHeader from "@/components/AuthHeader";
import "./globals.css";

export const metadata: Metadata = {
  title: "Asclepian Research Labs — Immune Reasoning Copilot",
  description: "AI-powered immune reasoning copilot for autoimmune hypothesis generation and therapeutic target discovery.",
};

const clerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const content = (
    <html lang="en">
      <body className="min-h-screen bg-surface-0 text-gray-200 antialiased">
        {clerkKey && <AuthHeader />}
        {children}
      </body>
    </html>
  );

  if (clerkKey) {
    return <ClerkProvider>{content}</ClerkProvider>;
  }

  return content;
}
