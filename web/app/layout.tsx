import type { Metadata, Viewport } from "next";
import { Archivo, Inter_Tight, JetBrains_Mono } from "next/font/google";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/ui/toast";
import "./globals.css";

/**
 * Display face. Archivo is variable on the width axis, and the design calls for
 * width 112 ("Expanded") — set via `font-variation-settings` in `.font-display`
 * rather than a static weight. This is the only preloaded face.
 */
const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  axes: ["wdth"],
  display: "swap",
  preload: true,
});

const interTight = Inter_Tight({
  variable: "--font-inter-tight",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  preload: false,
});

/**
 * Data face. Load-bearing, not garnish: every piece of machine-produced value
 * in this product is set in mono, which is how a user learns at a glance what
 * came from the system versus what came from a person.
 */
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
  preload: false,
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL?.trim() || "https://callflow.ai";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "CallFlow AI — every call comes back as data",
    template: "%s · CallFlow AI",
  },
  description:
    "CallFlow dials your contact list, holds a real conversation, and returns typed results — outcome, sentiment, and the fields you defined. Clean calls close themselves. Only the ones that need a person reach one.",
  applicationName: "CallFlow AI",
  openGraph: {
    type: "website",
    siteName: "CallFlow AI",
    title: "CallFlow AI — every call comes back as data",
    description:
      "CallFlow dials your contact list, holds a real conversation, and returns typed results — outcome, sentiment, and the fields you defined.",
    url: "/",
  },
  twitter: {
    card: "summary_large_image",
    title: "CallFlow AI — every call comes back as data",
    description:
      "CallFlow dials your contact list, holds a real conversation, and returns typed results.",
  },
  // Icons are not declared here: `app/icon.svg` and `app/apple-icon.tsx` are
  // file-convention assets, so Next generates them and injects the links itself.
  manifest: "/manifest.webmanifest",
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  // Light only — there is no dark theme, so the browser chrome should not
  // pretend there is one.
  themeColor: "#F4F6F5",
  colorScheme: "light",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${interTight.variable} ${jetbrainsMono.variable}`}
    >
      <body className="min-h-dvh bg-surface text-text">
        <NuqsAdapter>
          <TooltipProvider>
            <ToastProvider>{children}</ToastProvider>
          </TooltipProvider>
        </NuqsAdapter>
      </body>
    </html>
  );
}
