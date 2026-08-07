import type { Metadata } from "next";
import { StatusBoard } from "./status-board";
import { Eyebrow } from "@/components/ui/panel";

export const metadata: Metadata = {
  title: "Status",
  description: "Live status of the CallFlow calling service and dashboard.",
};

export default function StatusPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 pt-12 sm:px-6">
      <header className="flex flex-col gap-3">
        <Eyebrow>Status</Eyebrow>
        <h1 className="font-display text-display-l text-text">Is it working?</h1>
        <p className="text-body-l text-text-dim">
          Checked live from your browser when this page loads. The calling service sleeps
          when it isn&apos;t in use, so a slow first check is normal rather than an outage.
        </p>
      </header>

      <div className="mt-10">
        <StatusBoard />
      </div>
    </div>
  );
}
