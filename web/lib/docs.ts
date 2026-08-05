/**
 * The docs navigation tree.
 *
 * Kept as data rather than derived from the filesystem so the order is editorial:
 * "Writing a good goal" sits second because it is the page that decides whether
 * someone succeeds with the product, not because of where it falls alphabetically.
 */

export interface DocPage {
  slug: string;
  title: string;
  /** One line, shown on the docs index. */
  summary: string;
}

export interface DocSection {
  name: string;
  pages: DocPage[];
}

export const DOC_SECTIONS: DocSection[] = [
  {
    name: "Start here",
    pages: [
      {
        slug: "getting-started",
        title: "Getting started",
        summary:
          "From an empty account to a dry run with typed results, in about five minutes.",
      },
      {
        slug: "writing-a-good-goal",
        title: "Writing a good goal",
        summary:
          "The goal field is the product. What separates a goal that works from one that fails at call time.",
      },
    ],
  },
  {
    name: "Results",
    pages: [
      {
        slug: "result-schemas",
        title: "Result schemas",
        summary: "Defining the fields every call returns, and the types they come back as.",
      },
      {
        slug: "triage-rules",
        title: "Triage rules",
        summary:
          "How a call becomes auto-closed, queued for retry, or escalated to a person.",
      },
    ],
  },
  {
    name: "Operating it",
    pages: [
      {
        slug: "safety-configuration",
        title: "Safety configuration",
        summary: "Dry run, the allowlist, the per-run ceiling, rate limits, and calling windows.",
      },
      {
        slug: "api-reference",
        title: "API reference",
        summary: "Campaigns, previews, and runs over HTTP.",
      },
      {
        slug: "webhooks",
        title: "Webhooks",
        summary: "Receiving results as they land, with a delivery log and replay.",
      },
    ],
  },
  {
    name: "Reference",
    pages: [
      {
        slug: "changelog",
        title: "Changelog",
        summary: "What shipped, and when.",
      },
    ],
  },
];

export const ALL_DOC_PAGES: DocPage[] = DOC_SECTIONS.flatMap((section) => section.pages);

export function findDocPage(slug: string): DocPage | undefined {
  return ALL_DOC_PAGES.find((page) => page.slug === slug);
}

/** Previous / next, for the footer of a docs page. */
export function docNeighbours(slug: string): { prev?: DocPage; next?: DocPage } {
  const index = ALL_DOC_PAGES.findIndex((page) => page.slug === slug);
  if (index === -1) return {};
  return {
    prev: index > 0 ? ALL_DOC_PAGES[index - 1] : undefined,
    next: index < ALL_DOC_PAGES.length - 1 ? ALL_DOC_PAGES[index + 1] : undefined,
  };
}
