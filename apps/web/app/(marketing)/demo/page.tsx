import type { Metadata } from "next";
import { DemoForm } from "./demo-form";
import { LampStrip } from "@/components/brand/lamp-strip";
import { Eyebrow } from "@/components/ui/panel";
import type { LampSpec } from "@/lib/lamp";

export const metadata: Metadata = {
  title: "Book a demo",
  description:
    "Fifteen minutes. Bring your own contact list and watch it run for real, with the ceiling set low.",
};

const STRIP: LampSpec[] = [
  { state: "jade", label: "Auto-closed" },
  { state: "jade", label: "Auto-closed" },
  { state: "brass", pulse: true, label: "Queued for retry" },
  { state: "jade", label: "Auto-closed" },
  { state: "flare", label: "Needs a person" },
  { state: "jade", label: "Auto-closed" },
];

const WHAT_HAPPENS = [
  {
    title: "You bring a real list",
    body: "Twenty rows from a spreadsheet you actually use. We validate it live, so you see which rows would have failed and why.",
  },
  {
    title: "We write your goal together",
    body: "In plain English, with the fields you want back. This is the part that decides whether the whole thing works, and it takes about four minutes.",
  },
  {
    title: "We run a few real calls",
    body: "Two or three from your own list, ceiling set low, on the spot — a typed result for each one, not a mock-up.",
  },
];

/**
 * Book a demo.
 *
 * There is deliberately no phone-number field. Asking a calling company for your
 * phone number at the very top of the funnel is a friction point, and an
 * unnecessary one: everything that needs to happen on this call happens over a
 * screen share.
 */
export default function DemoPage() {
  return (
    <div className="mx-auto max-w-(--container-marketing) px-4 pt-12 sm:px-6">
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,480px)] lg:gap-16">
        <div className="flex flex-col gap-6">
          <Eyebrow>Book a demo</Eyebrow>
          <h1 className="measure-display font-display text-display-l text-text">
            Fifteen minutes, with your own list.
          </h1>
          <p className="measure text-body-l text-text-dim">
            Not a slide deck. We open the product, load contacts you brought, and run
            a few of them for real, right there, before you decide anything.
          </p>

          <ol className="mt-2 flex flex-col gap-5 border-t border-rule pt-6">
            {WHAT_HAPPENS.map((item, i) => (
              <li key={item.title} className="flex gap-4">
                <Eyebrow as="span" className="mt-1 shrink-0">
                  {String(i + 1).padStart(2, "0")}
                </Eyebrow>
                <div className="flex flex-col gap-1">
                  <h2 className="text-h4 font-medium text-text">{item.title}</h2>
                  <p className="text-small text-text-dim">{item.body}</p>
                </div>
              </li>
            ))}
          </ol>

          <div className="mt-2 flex flex-col gap-3 border-t border-rule pt-6">
            <Eyebrow>What you leave with</Eyebrow>
            <LampStrip lamps={STRIP} counts />
            <p className="measure text-small text-text-dim">
              A run you can log back into, and a campaign already configured for your
              use case. If it is not a fit, we will say so on the call rather than
              email you for three weeks.
            </p>
          </div>
        </div>

        <div className="lg:pt-2">
          <DemoForm />
        </div>
      </div>
    </div>
  );
}
