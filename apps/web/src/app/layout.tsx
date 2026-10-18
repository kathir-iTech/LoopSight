import type { Metadata } from "next";
import "@fontsource-variable/inter";
import { Toaster } from "react-hot-toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "LoopSight — Evidence-Guided Visual Screening",
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
    <html lang="en">
      <body className="bg-[#0a1628] text-[#e6f0ff] antialiased">
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
