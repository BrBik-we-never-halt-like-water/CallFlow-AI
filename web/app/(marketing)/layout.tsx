import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { Prewarm } from "@/components/app/prewarm";

export default function MarketingLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>

      {/* Starts waking the service while the visitor reads, so the dashboard is
          warm by the time they click through. Renders nothing and never surfaces
          an error. */}
      <Prewarm />

      <SiteHeader />
      <main id="main">{children}</main>
      <SiteFooter />
    </>
  );
}
