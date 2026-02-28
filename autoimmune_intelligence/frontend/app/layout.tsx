import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Autoimmune Intelligence",
  description: "AI-powered query interface for autoimmune disease research.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-gray-900 antialiased">
        {children}
      </body>
    </html>
  );
}
