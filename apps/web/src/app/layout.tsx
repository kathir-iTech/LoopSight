import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LoopSight",
  description: "Uncertainty-triggered active-perception inspection agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
