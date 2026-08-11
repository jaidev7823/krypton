import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Krypton — Living World Simulator",
  description: "Learn real skills inside living fictional worlds.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
