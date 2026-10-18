import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "react-hot-toast";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "LoopSight v2 — Active-Perception Optical Nephelometry & Metrology",
  description:
    "Household drinking-water turbidity screening and structural crack metrology. Flags cloudy water for follow-up. OpenCV 5 + MCP active perception under different lighting.",
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className={`${inter.className} bg-[#0a1628] text-[#e6f0ff] antialiased`}>
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "#0f2942",
              color: "#e6f0ff",
              border: "1px solid #1e3a5f",
              fontSize: "14px",
            },
            success: {
              iconTheme: { primary: "#22c55e", secondary: "#fff" },
            },
            error: {
              iconTheme: { primary: "#ef4444", secondary: "#fff" },
            },
          }}
        />
      </body>
    </html>
  );
}
