import type { MDXComponents } from "mdx/types";
import Link from "next/link";
import { CodeBlock } from "@/components/ui/code-block";

/**
 * Element mapping for every MDX page.
 *
 * Docs prose is styled here rather than with a typography plugin, so it inherits
 * the same type scale, measure, and rule colours as the rest of the product. A
 * docs page that uses a different set of headings from the app it documents reads
 * as a separate website.
 *
 * Headings get ids so the on-page contents list can link to them.
 */
function slugify(children: React.ReactNode): string {
  return String(children)
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return {
    h1: ({ children }) => (
      <h1 className="font-docs text-display-l font-semibold tracking-tight text-text">
        {children}
      </h1>
    ),
    h2: ({ children }) => (
      <h2
        id={slugify(children)}
        className="mt-12 scroll-mt-24 border-t border-rule pt-8 font-docs text-h2 font-semibold tracking-tight text-text first:mt-0 first:border-0 first:pt-0"
      >
        {children}
      </h2>
    ),
    h3: ({ children }) => (
      <h3
        id={slugify(children)}
        className="mt-10 scroll-mt-24 font-docs text-h3 font-medium tracking-tight text-text"
      >
        {children}
      </h3>
    ),
    h4: ({ children }) => (
      <h4 className="mt-7 font-docs text-h4 font-medium text-text">{children}</h4>
    ),
    p: ({ children }) => (
      <p className="mt-4 measure text-body leading-[1.7] text-text-dim">{children}</p>
    ),
    ul: ({ children }) => (
      <ul className="mt-4 flex measure flex-col gap-2.5 text-body leading-[1.7] text-text-dim">
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="mt-4 flex measure list-decimal flex-col gap-2.5 pl-6 text-body leading-[1.7] text-text-dim marker:text-text-mute">
        {children}
      </ol>
    ),
    li: ({ children }) => <li className="pl-0.5 [ul>&]:flex [ul>&]:gap-3">{children}</li>,
    strong: ({ children }) => (
      <strong className="font-medium text-text">{children}</strong>
    ),
    a: ({ href, children }) => {
      const target = String(href ?? "");
      const external = /^https?:\/\//.test(target);
      const className =
        "font-medium text-text underline decoration-rule-strong underline-offset-2 transition-colors hover:decoration-current";

      return external ? (
        <a href={target} target="_blank" rel="noreferrer" className={className}>
          {children}
        </a>
      ) : (
        <Link href={target} className={className}>
          {children}
        </Link>
      );
    },
    code: ({ children }) => (
      <code className="rounded-xs border border-rule bg-surface-sunken px-1.5 py-0.5 font-mono text-data text-text">
        {children}
      </code>
    ),
    // A fenced block arrives as <pre><code>. Route it through CodeBlock so docs
    // samples get the same copy affordance and JSON treatment as the product.
    // A ```bash fence gets the terminal chrome (it's a command you'd run); a
    // ```text fence that looks like CSV gets the terminal chrome plus a
    // download button, since that's a sample file rather than a command.
    pre: ({ children }) => {
      const child = children as
        | { props?: { children?: unknown; className?: string } }
        | undefined;
      const raw = String(child?.props?.children ?? "").replace(/\n$/, "");
      const cls = child?.props?.className ?? "";

      const isJson = /language-json/.test(cls);
      const isBash = /language-bash/.test(cls);
      const isCsv = /language-text/.test(cls) && /^[\w.]+,[\w.]+/.test(raw);

      if (isBash) {
        return (
          <div className="mt-5">
            <CodeBlock code={raw} language="text" variant="terminal" title="shell" />
          </div>
        );
      }

      if (isCsv) {
        return (
          <div className="mt-5">
            <CodeBlock
              code={raw}
              language="text"
              variant="terminal"
              title="contacts.csv"
              downloadFilename="contacts.csv"
            />
          </div>
        );
      }

      return (
        <div className="mt-5">
          <CodeBlock code={raw} language={isJson ? "json" : "text"} />
        </div>
      );
    },
    // Used as a compact checklist/callout card   short pre-flight steps that
    // shouldn't sprawl full-width like a regular ordered list.
    blockquote: ({ children }) => (
      <blockquote className="mt-5 measure rounded-md border border-rule bg-surface-sunken p-4 text-small leading-[1.6] text-text-dim [&_ol]:mt-2 [&_ol]:gap-2 [&_p:first-child]:mt-0 [&_p]:text-small">
        {children}
      </blockquote>
    ),
    hr: () => <hr className="my-10 border-0 border-t border-rule" />,
    table: ({ children }) => (
      <div className="mt-5 overflow-x-auto rounded-md border border-rule">
        <table className="w-full border-collapse text-left">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead className="bg-surface-sunken">{children}</thead>,
    th: ({ children }) => (
      <th
        scope="col"
        className="border-b border-rule px-4 py-2.5 font-docs text-small font-medium text-text-mute"
      >
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="border-b border-rule px-4 py-2.5 text-small leading-[1.6] text-text-dim">
        {children}
      </td>
    ),
    ...components,
  };
}
