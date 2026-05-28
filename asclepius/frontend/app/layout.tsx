import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Newsreader, Inter } from "next/font/google";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  weight: ["300", "400", "500", "600"],
  style: ["normal", "italic"],
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Asclepius Research Labs",
  description: "Biomedical Research Intelligence: a multimodal, agentic hybrid RAG system over PubMed for mechanism mapping, target risk, and hypothesis generation, combining a research agent with dense retrieval, knowledge graphs, and VLMs.",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon.png", type: "image/png", sizes: "192x192" },
    ],
    apple: "/apple-touch-icon.png",
  },
};

const clerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const content = (
    <html
      lang="en"
      className={`${newsreader.variable} ${inter.variable} ${GeistSans.variable} ${GeistMono.variable}`}
    >
      <body className="min-h-screen bg-bg text-ink-2 antialiased font-sans">
        {children}
      </body>
    </html>
  );

  if (clerkKey) {
    return <ClerkProvider>{content}</ClerkProvider>;
  }

  return content;
}
