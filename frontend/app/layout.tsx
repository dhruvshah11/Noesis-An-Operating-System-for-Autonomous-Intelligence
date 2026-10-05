import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import Providers from "./providers";
import { NOESIS_BRAND } from "@/lib/brand";

export const metadata: Metadata = {
  applicationName: NOESIS_BRAND.appName,
  title: {
    default: NOESIS_BRAND.dashboardTitle,
    template: `%s · ${NOESIS_BRAND.product}`,
  },
  description: `${NOESIS_BRAND.appName}: explore agent executions, ${NOESIS_BRAND.memory.t3} memory tiers, documents, tokens & cost, and configure your autonomous workspace.`,
  metadataBase: new URL("http://localhost:3000"),
  openGraph: {
    type: "website",
    title: NOESIS_BRAND.appName,
    description: `${NOESIS_BRAND.product} — ${NOESIS_BRAND.tagline}`,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#1b1f2e" },
  ],
};

export default function RootLayout({ children }: { readonly children: ReactNode }): JSX.Element {
  return (
    <html lang="en" suppressHydrationWarning className="dark">
      <body className="min-h-dvh font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
