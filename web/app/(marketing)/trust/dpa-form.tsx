"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ErrorSummary, Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { useToast } from "@/components/ui/toast";

/**
 * DPA request form.
 *
 * There is no submission endpoint on the service yet, so this validates and reports
 * honestly rather than pretending to send. A form that shows a success message
 * without delivering anything is worse than one that says where to email — a
 * compliance reviewer who never gets a reply concludes the whole page is decorative.
 */
export function DpaRequestForm() {
  const toast = useToast();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);

  function validate(): Record<string, string> {
    const next: Record<string, string> = {};
    if (!name.trim()) next.name = "Add your name so we know who to address it to.";
    if (!email.trim()) next.email = "Add a work email so we can send the agreement.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      next.email = "That doesn't look like an email address.";
    }
    if (!company.trim()) next.company = "Add the company the agreement is for.";
    return next;
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSubmitted(true);
    toast({
      tone: "info",
      title: "Nothing was sent yet",
      body: "This form isn't connected to a mailbox. Email the address shown and we'll reply.",
    });
  }

  if (submitted) {
    return (
      <Panel className="flex flex-col gap-3 p-5">
        <h3 className="text-h4 font-medium text-text">Send this to us directly</h3>
        <p className="text-small text-text-dim">
          This form is not yet wired to a mailbox, so nothing has been delivered. Email{" "}
          <a
            href={`mailto:legal@callflow.ai?subject=DPA request — ${encodeURIComponent(company)}`}
            className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
          >
            legal@callflow.ai
          </a>{" "}
          and we will send the DPA, the named sub-processor list, and our security
          overview within two business days.
        </p>
        <Button variant="secondary" size="sm" className="w-fit" onClick={() => setSubmitted(false)}>
          Back to the form
        </Button>
      </Panel>
    );
  }

  const summary = Object.entries(errors).map(([id, message]) => ({
    id: `dpa-${id}`,
    label: { name: "Name", email: "Work email", company: "Company" }[id] ?? id,
    message,
  }));

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <ErrorSummary errors={summary} />

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" error={errors.name} required>
          <Input
            id="dpa-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
          />
        </Field>
        <Field label="Work email" error={errors.email} required>
          <Input
            id="dpa-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </Field>
      </div>

      <Field label="Company" error={errors.company} required>
        <Input
          id="dpa-company"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          autoComplete="organization"
        />
      </Field>

      <Field
        label="Anything specific you need"
        help="Data residency, a security questionnaire, a named sub-processor list."
      >
        <Textarea
          id="dpa-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
        />
      </Field>

      <Button type="submit" className="w-fit">
        Request the DPA
      </Button>
    </form>
  );
}
