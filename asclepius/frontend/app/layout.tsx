import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import "./globals.css";

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

// Applies the saved (or ?theme=) colour theme before first paint, so there is no flash.
const THEME_INIT = `(function(){try{var q=new URLSearchParams(location.search).get("theme");var t=q||localStorage.getItem("asclepius-theme")||"verdigris";if(["verdigris","indigo","lagoon","helix"].indexOf(t)<0)t="verdigris";document.documentElement.setAttribute("data-theme",t);if(q)localStorage.setItem("asclepius-theme",t)}catch(e){}})()`;

const clerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const content = (
    <html
      lang="en"
      data-theme="verdigris"
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body className="min-h-screen bg-bg text-ink antialiased font-sans">
        {children}
      </body>
    </html>
  );

  if (clerkKey) {
    return <ClerkProvider>{content}</ClerkProvider>;
  }

  return content;
}
