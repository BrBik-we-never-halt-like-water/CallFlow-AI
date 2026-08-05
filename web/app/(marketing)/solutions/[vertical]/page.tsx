import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { RoiCalculator } from "@/components/marketing/roi-calculator";
import { Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { Accordion } from "@/components/ui/disclosure";
import { Eyebrow, Panel, SectionHeading } from "@/components/ui/panel";
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
        <SectionHeading eyebrow="The problem" title="What this actually costs you today." />
        <ol className="mt-8 grid gap-6 border-t border-rule pt-8 md:grid-cols-3">
          {vertical.pain.map((line, i) => (
            <li key={i} className="flex flex-col gap-2">
              <Eyebrow as="span">{String(i + 1).padStart(2, "0")}</Eyebrow>
              <p className="text-body text-text-dim">{line}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* ---- The artefact -------------------------------------------------- */}
      <Divider />
      <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
        <SectionHeading
          eyebrow="The campaign"
          title="The exact goal, and the exact fields it returns."
          sub="This is the whole template, not an excerpt. It is what the agent is told, verbatim — including what it must refuse to do."
        />

        <div className="mt-8 grid gap-4 lg:grid-cols-2">
          {/* min-w-0: without it these grid columns take their children's
              min-content width — the unwrapped JSON schema below — and push the
              whole page wider than the viewport on mobile. */}
          <div className="flex min-w-0 flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Eyebrow as="span">Goal template</Eyebrow>
              <Tag>{`{name}`}</Tag>
              <Tag>{`{context.*}`}</Tag>
            </div>
            <Panel sunken className="p-4">
              <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-data text-text">
                {vertical.goalTemplate}
              </pre>
            </Panel>
          </div>

          <div className="flex min-w-0 flex-col gap-3">
            <CodeBlock
              label="Result schema"
              code={schemaToJson(vertical.schema)}
              maxHeight="max-h-[32rem]"
            />
            <ul className="flex flex-col gap-1.5">
              {vertical.schema.map((field) => (
                <li key={field.key} className="flex flex-wrap items-baseline gap-2">
                  <code className="font-mono text-data text-text">{field.key}</code>
                  <span className="font-mono text-label uppercase tracking-[0.14em] text-text-mute">
                    {field.type}
                  </span>
                  <span className="text-small text-text-dim">{field.description}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ---- ROI ----------------------------------------------------------- */}
      <Divider />
      <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
        <SectionHeading
          eyebrow="The maths"
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
        <SectionHeading eyebrow="Fair questions" title="The two objections we hear most." />
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
        <ul className="mt-4 flex flex-wrap gap-2">
          {VERTICALS.filter((v) => v.slug !== vertical.slug).map((other) => (
            <li key={other.slug}>
              <Link
                href={`/solutions/${other.slug}`}
                className="inline-flex items-center rounded-sm border border-rule px-3 py-2 text-small text-text-dim transition-colors hover:bg-surface-hover hover:text-text"
              >
                {other.name}
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
