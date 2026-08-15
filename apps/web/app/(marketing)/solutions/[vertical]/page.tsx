import type { Metadata } from "next";
import { CaretRightIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { notFound } from "next/navigation";
import { RoiCalculator } from "@/components/marketing/roi-calculator";
import { Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { Accordion } from "@/components/ui/disclosure";
import { Eyebrow, SectionHeading } from "@/components/ui/panel";
import { Rule } from "@/components/ui/rule";
import { getVertical, schemaToJson, VERTICALS } from "@/lib/verticals";

export function generateStaticParams() {
  return VERTICALS.map((vertical) => ({ vertical: vertical.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ vertical: string }>;
}): Promise<Metadata> {
  const { vertical: slug } = await params;
  const vertical = getVertical(slug);
  if (!vertical) return {};

  return {
    title: vertical.name,
    description: vertical.sub,
  };
}

/**
 * One template, four verticals.
 *
 * The goal template and the result schema are shown in full, unabridged. That is
 * the whole differentiator on this page: everyone in this category shows a polished
 * demo, and almost nobody shows the literal instruction the agent is given or the
 * exact fields that come back. A buyer who has been burned by a vague AI pitch can
 * read these two blocks and check the claim themselves.
 */
export default async function SolutionPage({
  params,
}: {
  params: Promise<{ vertical: string }>;
}) {
  const { vertical: slug } = await params;
  const vertical = getVertical(slug);
  if (!vertical) notFound();

  return (
    <>
      {/* ---- Hero ---------------------------------------------------------- */}
      <section className="mx-auto max-w-(--container-marketing) px-4 pt-12 sm:px-6">
        <div className="flex flex-col gap-4">
          <Eyebrow>{vertical.name}</Eyebrow>
          <h1 className="measure-display font-display text-display-l text-text">
            {vertical.headline}
          </h1>
          <p className="measure text-body-l text-text-dim">{vertical.sub}</p>
          <div className="mt-2 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/signup">Start free</Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/demo">Book a 15-min demo</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* ---- The pain ------------------------------------------------------ */}
      <Divider />
      <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
        <SectionHeading title="What this actually costs you today." />
        <ol className="mt-8 grid items-stretch gap-4 md:grid-cols-3">
          {vertical.pain.map((line, i) => (
            <li
              key={i}
              className="card-raised flex h-full flex-col gap-3 p-5"
            >
              <span className="font-display text-h3 leading-none text-text-mute">
                {String(i + 1).padStart(2, "0")}
              </span>
              <p className="text-body text-text-dim">{line}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* ---- The artefact -------------------------------------------------- */}
      <Divider />
      <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
        <SectionHeading
          title="The exact goal, and the exact fields it returns."
          sub="This is the whole template, not an excerpt. It is what the agent is told, verbatim — including what it must refuse to do."
        />

        {/* One basin, not two boxes: what the agent is told flows in on the
            left, the shape it returns flows back on the right, joined by a seam
            that fades at both ends. min-w-0 keeps the unwrapped JSON from pushing
            the columns past the viewport on mobile. */}
        <div className="card-sunken mt-10 grid gap-x-8 gap-y-10 p-5 sm:p-8 lg:grid-cols-[1.05fr_1fr] lg:gap-x-12">
          <div className="flex min-w-0 flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <Eyebrow as="span">Goal template</Eyebrow>
              <Tag>{`{name}`}</Tag>
              <Tag>{`{context.*}`}</Tag>
            </div>
            <pre className="whitespace-pre-wrap font-mono text-data leading-relaxed text-text-dim">
              {vertical.goalTemplate}
            </pre>
          </div>

          <div className="flow-seam-l flex min-w-0 flex-col gap-4 lg:pl-12">
            <Eyebrow as="span">Result schema</Eyebrow>
            {/* The JSON is the whole glossary. A field list used to follow it
                here, and every line of it - key, type, description - was already
                in the object directly above, word for word: `schemaToJson`
                writes each field's `description` straight into the schema. Two
                renderings of one thing is not thoroughness, it is the reader
                checking whether they differ. */}
            {/* Capped so the schema stops setting the section's height. At full
                length the JSON ran ~1000px against the goal template's ~510 and
                dragged the whole band to half again a screen; the two columns
                now balance, and nothing is removed - the rest scrolls. */}
            <CodeBlock bare maxHeight="max-h-[30rem]" code={schemaToJson(vertical.schema)} />
          </div>
        </div>
      </section>

      {/* ---- ROI ----------------------------------------------------------- */}
      <Divider />
      <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
        <SectionHeading
          title="What it frees up, on your numbers."
          sub="Change any of these. Nothing here is a claim about your business until you put your own figures in."
        />
        <div className="mt-8">
          <RoiCalculator vertical={vertical} />
        </div>
      </section>

      {/* ---- Objections ---------------------------------------------------- */}
      <Divider />
      <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
        <SectionHeading title="The two objections we hear most." />
        <div className="mt-8 max-w-3xl">
          <Accordion
            items={vertical.objections.map((objection) => ({
              title: objection.question,
              content: objection.answer,
            }))}
          />
        </div>
      </section>

      {/* ---- Other verticals ----------------------------------------------- */}
      <Divider />
      <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
        <Eyebrow>Other teams</Eyebrow>
        <ul className="mt-4 grid gap-3 sm:grid-cols-3">
          {VERTICALS.filter((v) => v.slug !== vertical.slug).map((other) => (
            <li key={other.slug}>
              <Link
                href={`/solutions/${other.slug}`}
                className="group card-raised card-interactive flex items-center justify-between gap-3 p-4"
              >
                <span className="min-w-0">
                  <span className="block text-body font-medium text-text">{other.name}</span>
                  <span className="block text-small text-text-mute">{other.metricLabel}</span>
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
    </>
  );
}

function Divider() {
  return (
    <div className="mx-auto max-w-(--container-marketing) px-4 py-(--space-section) sm:px-6">
      <Rule />
    </div>
  );
}
