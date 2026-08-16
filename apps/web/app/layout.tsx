import type { Metadata, Viewport } from 'next';
import { Geist, JetBrains_Mono, Space_Grotesk } from 'next/font/google';
import { NuqsAdapter } from 'nuqs/adapters/next/app';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ToastProvider } from '@/components/ui/toast';
import { ViewTransitions } from '@/components/layout/view-transitions';
import { SiteLoader } from '@/components/layout/site-loader';
import { THEME_PRE_PAINT_SCRIPT } from '@/lib/theme';
import './globals.css';

/**
 * Display face. Space Grotesk's drawing comes out of technical lettering - the
 * squared bowls and the single-storey `a` read as instrument panel rather than
 * brochure, which is the right register for a product that reports what
 * happened on a phone call. The only preloaded face.
 */
const spaceGrotesk = Space_Grotesk({
  variable: '--font-space-grotesk',
  subsets: ['latin'],
  weight: ['500', '600', '700'],
  display: 'swap',
  preload: true,
});

/**
 * Text face. Geist rather than Inter: Inter is the default every product
 * reaches for, and at the small sizes this interface lives at, Geist's wider
 * apertures and taller x-height hold up better in dense rows of data.
 */
const geist = Geist({
  variable: '--font-geist',
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  display: 'swap',
  preload: false,
});

/**
 * Data face. Load-bearing, not garnish: every piece of machine-produced value
 * in this product is set in mono, which is how a user learns at a glance what
 * came from the system versus what came from a person.
 */
const jetbrainsMono = JetBrains_Mono({
  variable: '--font-jetbrains-mono',
  subsets: ['latin'],
  weight: ['400', '500'],
  display: 'swap',
  preload: false,
});

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.trim() || 'https://callflow.ai';

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'CallFlow AI - every call comes back as data',
    template: '%s · CallFlow AI',
  },
  description:
    'CallFlow dials your contact list, holds a real conversation, and returns typed results - outcome, sentiment, and the fields you defined. Clean calls close themselves. Only the ones that need a person reach one.',
  applicationName: 'CallFlow AI',
  openGraph: {
    type: 'website',
    siteName: 'CallFlow AI',
    title: 'CallFlow AI - every call comes back as data',
    description:
      'CallFlow dials your contact list, holds a real conversation, and returns typed results - outcome, sentiment, and the fields you defined.',
    url: '/',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'CallFlow AI - every call comes back as data',
    description:
      'CallFlow dials your contact list, holds a real conversation, and returns typed results.',
  },
  // Icons are not declared here: `app/icon.svg` and `app/apple-icon.tsx` are
  // file-convention assets, so Next generates them and injects the links itself.
  manifest: '/manifest.webmanifest',
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  // Both, now that the theme is real. `themeColor` takes a media-keyed list so
  // the browser's own chrome (the address bar on mobile, the window frame on
  // some desktops) matches the page instead of framing a dark page in a light
  // bar. These are `--surface`'s two values; keep them in step with globals.css.
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f3f4f6' },
    { media: '(prefers-color-scheme: dark)', color: '#050505' },
  ],
  colorScheme: 'light dark',
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${geist.variable} ${jetbrainsMono.variable}`}
      // The pre-paint script sets `data-theme` on this element before React
      // hydrates, so the server-rendered markup and the DOM legitimately differ
      // by that one attribute. Without this, React warns on every load.
      suppressHydrationWarning
    >
      <head>
        {/*
          Before first paint, not in a provider or an effect. A dark-theme user
          who waits for React has already been shown a white page. See
          `lib/theme.ts` for why this is a hand-written ES5 string.
        */}
        <script
          dangerouslySetInnerHTML={{ __html: THEME_PRE_PAINT_SCRIPT }}
        />
      </head>
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
