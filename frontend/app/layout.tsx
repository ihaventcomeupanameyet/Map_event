import "leaflet/dist/leaflet.css";
import "./globals.css";

import type { Metadata } from "next";


export const metadata: Metadata = {
  title: "Vancouver Event Map",
  description: "Discover Vancouver events on a Leaflet map.",
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

