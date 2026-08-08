import type { Metadata, Viewport } from "next";
import { Ubuntu, JetBrains_Mono } from "next/font/google";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/ui/toast";
import { ViewTransitions } from "@/components/layout/view-transitions";
import { SiteLoader } from "@/components/layout/site-loader";
import "./globals.css";

/**
 * The single text face, display and body both. Ubuntu has no variable cut, so
 * the four static weights are loaded; 300 is unused at present but is what the
 * large display sizes fall back to if the scale is ever loosened.
 *
 * Ubuntu reads soft at display sizes without tight tracking — that is set on
 * the type scale in globals.css, not here.
 */
const ubuntu = Ubuntu({
  variable: "--font-ubuntu",
  subsets: ["latin"],
  weight: ["300", "400", "500", "700"],
  display: "swap",
  preload: true,
});

/**
 * Data face. Load-bearing, not garnish: every piece of machine-produced value
 * in this product is set in mono, which is how a user learns at a glance what
 * came from the system versus what came from a person.
 *
 * Kept as JetBrains Mono rather than moving to Ubuntu Mono with the rest of the
 * family. Ubuntu Mono is narrow and light, and this face carries every table
 * header, phone number, duration and cost in the dashboard — legibility in
 * dense data beats family coherence here.
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
  themeColor: "#F5F6F6",
  colorScheme: "light",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${ubuntu.variable} ${jetbrainsMono.variable}`}
    >
      <body className="min-h-dvh bg-surface text-text">
        <NuqsAdapter>
          <TooltipProvider>
            <ToastProvider>{children}</ToastProvider>
          </TooltipProvider>
        </NuqsAdapter>
        <SiteLoader />
        <ViewTransitions />
      </body>
    </html>
  );
}
