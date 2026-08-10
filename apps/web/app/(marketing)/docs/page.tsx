import { CaretRightIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { Eyebrow } from "@/components/ui/panel";
import { DOC_SECTIONS } from "@/lib/docs";

export default function DocsIndexPage() {
  return (
    <>
      <h1 className="font-display text-display-l text-text">Documentation</h1>
      <p className="mt-4 measure text-body-l text-text-dim">
        How to write a goal that works, what comes back from a call, and how the safety
        guards behave. If you only read one page, read{" "}
        <Link
          href="/docs/writing-a-good-goal"
          className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
        >
          Writing a good goal
        </Link>
        .
      </p>

      <div className="mt-10 flex flex-col gap-8">
        {DOC_SECTIONS.map((section) => (
          <section key={section.name} className="flex flex-col gap-3">
            <Eyebrow>{section.name}</Eyebrow>
            <ul className="border-t border-rule">
              {section.pages.map((page) => (
                <li key={page.slug} className="border-b border-rule">
                  <Link
                    href={`/docs/${page.slug}`}
                    className="group flex items-center gap-4 py-3 transition-colors hover:bg-surface-hover"
                  >
                    <span className="flex min-w-0 flex-1 flex-col gap-1">
                      <span className="text-h4 font-medium text-text">{page.title}</span>
                      <span className="measure text-small text-text-dim">{page.summary}</span>
                    </span>
                    <CaretRightIcon
                      aria-hidden
                      className="size-4 shrink-0 text-text-mute transition-transform duration-(--dur-base) ease-(--ease-out) group-hover:translate-x-1"
                    />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
