import type { Metadata } from "next";
import { DocsShell } from "@/components/layout/docs-shell";

export const metadata: Metadata = {
  title: {
    default: "Docs",
    template: "%s · CallFlow AI docs",
  },
};

export default function DocsLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="docs-face">
      <DocsShell>{children}</DocsShell>
    </div>
  );
}
