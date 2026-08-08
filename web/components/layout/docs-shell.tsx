"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { DOC_SECTIONS, docNeighbours, findDocPage } from "@/lib/docs";

/** Docs-only label: plain sans, not the site's mono `.eyebrow`   every string
 * on this page shares one font family. */
function DocsLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-docs text-label font-medium uppercase tracking-widest text-text-mute">
      {children}
    </p>
  );
}

/**
 * Three-pane docs shell: section nav, content, on-page contents.
 *
 * The contents list is built from the headings the MDX actually rendered, read out
 * of the DOM after mount. That keeps it honest   a hand-maintained list drifts the
 * first time someone edits a heading, and a docs page whose contents list lies is
 * worse than one with no contents list.
 */
export function DocsShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "";
  const slug = pathname.replace(/^\/docs\/?/, "");
  const page = findDocPage(slug);
  const { prev, next } = docNeighbours(slug);

  return (
    <div className="mx-auto grid max-w-(--container-marketing) gap-8 px-4 pt-10 pb-20 sm:px-6 lg:grid-cols-[200px_minmax(0,1fr)] xl:grid-cols-[200px_minmax(0,1fr)_180px]">
      {/* ---- Section nav ------------------------------------------------- */}
      <nav aria-label="Documentation" className="lg:sticky lg:top-24 lg:self-start">
        <div className="flex flex-col gap-5 border-b border-rule pb-5 lg:border-0 lg:pb-0">
          {DOC_SECTIONS.map((section) => (
            <div key={section.name} className="flex flex-col gap-2">
              <DocsLabel>{section.name}</DocsLabel>
              <ul className="flex flex-col gap-0.5">
                {section.pages.map((docPage) => {
                  const active = docPage.slug === slug;
                  return (
                    <li key={docPage.slug}>
                      <Link
                        href={`/docs/${docPage.slug}`}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "-mx-2 block rounded-sm px-2 py-1.5 font-docs text-small transition-colors duration-(--dur-micro)",
                          active
                            ? "bg-surface-sunken font-medium text-text"
                            : "text-text-dim hover:bg-surface-hover hover:text-text",
                        )}
                      >
                        {docPage.title}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </nav>

      {/* ---- Content ------------------------------------------------------ */}
      <article className="min-w-0">
        {children}

        {(prev || next) && (
          <nav
            aria-label="More documentation"
            className="mt-12 flex flex-wrap gap-3 border-t border-rule pt-6"
          >
            {prev ? (
              <Link
                href={`/docs/${prev.slug}`}
                className={cn(
                  "flex flex-col gap-1 rounded-md border border-rule p-3 transition-colors hover:bg-surface-hover",
                  next ? "flex-1" : "w-full max-w-72",
                )}
              >
                <DocsLabel>Previous</DocsLabel>
                <span className="font-docs text-small font-medium text-text">{prev.title}</span>
              </Link>
            ) : null}
            {next ? (
              <Link
                href={`/docs/${next.slug}`}
                className={cn(
                  "flex flex-col gap-1 rounded-md border border-rule p-3 text-right transition-colors hover:bg-surface-hover",
                  prev ? "flex-1" : "ml-auto w-full max-w-72",
                )}
              >
                <DocsLabel>Next</DocsLabel>
                <span className="font-docs text-small font-medium text-text">{next.title}</span>
              </Link>
            ) : null}
          </nav>
        )}
      </article>

      {/* ---- On this page ------------------------------------------------- */}
      <OnThisPage key={slug} title={page?.title} />
    </div>
  );
}

interface Heading {
  id: string;
  text: string;
  level: 2 | 3;
}

function OnThisPage({ title }: { title?: string }) {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeId, setActiveId] = useState<string>("");

  /**
   * Reads the headings the MDX actually rendered.
   *
   * A DOM scan after mount is the only way to build this honestly   the alternative is a
   * hand-maintained list that drifts the first time someone edits a heading. The DOM is a
   * genuine external system here, which is what an effect is for.
   */
  useEffect(() => {
    const nodes = Array.from(
      document.querySelectorAll<HTMLElement>("article h2[id], article h3[id]"),
    );

    // eslint-disable-next-line react-hooks/set-state-in-effect -- reading the rendered DOM is the external-system sync an effect exists for.
    setHeadings(
      nodes.map((node) => ({
        id: node.id,
        text: node.textContent ?? "",
        level: node.tagName === "H2" ? 2 : 3,
      })),
    );

    if (nodes.length === 0) return;

    // Marks the heading nearest the top of the viewport. `rootMargin` pulls the
    // trigger line below the sticky header so the highlighted entry matches what
    // the reader is actually looking at.
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveId(visible[0].target.id);
      },
      { rootMargin: "-96px 0px -70% 0px", threshold: 0 },
    );

    for (const node of nodes) observer.observe(node);
    return () => observer.disconnect();
  }, [title]);

  if (headings.length < 2) return <div aria-hidden className="hidden xl:block" />;

  return (
    <nav
      aria-label="On this page"
      className="hidden xl:sticky xl:top-24 xl:block xl:w-45 xl:self-start"
    >
      <DocsLabel>On this page</DocsLabel>
      <ul className="mt-2 flex flex-col gap-1 border-l border-rule">
        {headings.map((heading) => (
          <li key={heading.id} className="min-w-0">
            <a
              href={`#${heading.id}`}
              title={heading.text}
              className={cn(
                "-ml-px block truncate border-l py-1 font-docs text-small transition-colors duration-(--dur-micro)",
                heading.level === 3 ? "pl-5" : "pl-3",
                heading.id === activeId
                  ? "border-text font-medium text-text"
                  : "border-transparent text-text-mute hover:text-text",
              )}
            >
              {heading.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
