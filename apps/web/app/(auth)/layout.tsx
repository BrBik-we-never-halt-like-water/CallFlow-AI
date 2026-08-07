import Link from "next/link";
import { BrandLockup } from "@/components/brand/wordmark";

/**
 * Auth shell. A single centred card, with the same quiet grid the hero uses so the
 * doorway to the product looks like part of it.
 */
export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="relative flex min-h-dvh flex-col">
      <div
        aria-hidden
        className="grid-field pointer-events-none absolute inset-x-0 top-0 h-80"
      />
      <header className="flex h-16 shrink-0 items-center px-4 sm:px-6">
        <Link href="/" className="text-text transition-opacity hover:opacity-70">
          <BrandLockup />
          <span className="sr-only">CallFlow AI home</span>
        </Link>
      </header>

      <main className="relative flex flex-1 items-start justify-center px-4 pb-16 pt-4 sm:items-center sm:pt-0">
        <div className="w-full max-w-100">{children}</div>
      </main>

      <footer className="shrink-0 px-4 pb-6 sm:px-6">
        <nav aria-label="Legal" className="flex flex-wrap justify-center gap-x-5 gap-y-2">
          {[
            { label: "Privacy", href: "/trust" },
            { label: "Terms", href: "/trust" },
            { label: "Trust", href: "/trust" },
            { label: "Docs", href: "/docs" },
          ].map((link) => (
            <Link
              key={link.label}
              href={link.href}
              className="text-small text-text-mute transition-colors hover:text-text"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </footer>
    </div>
  );
}
