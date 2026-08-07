"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthCard } from "@/components/layout/auth-card";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { isPasswordValid, PasswordStrength } from "@/components/ui/password-strength";
import { useToast } from "@/components/ui/toast";
import { signUpWithPassword } from "@/lib/auth/actions";

const FREE_EMAIL_DOMAINS = [
  "gmail.com",
  "yahoo.com",
  "outlook.com",
  "hotmail.com",
  "icloud.com",
];

interface FieldErrors {
  name?: string;
  email?: string;
  password?: string;
}

export default function SignupPage() {
  const router = useRouter();
  const toast = useToast();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const domain = email.split("@")[1]?.toLowerCase() ?? "";
  // A nudge, not a rule. Plenty of real businesses run on a free mailbox, and
  // blocking them at the door to satisfy lead scoring is a bad trade.
  const suggestWorkEmail = FREE_EMAIL_DOMAINS.includes(domain);

  function validate(): FieldErrors {
    const found: FieldErrors = {};
    if (!name.trim()) found.name = "Add your name so teammates can recognise you.";
    if (!email.trim()) found.email = "Add an email address.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      found.email = "That doesn't look like an email address.";
    }
    if (!isPasswordValid(password)) {
      found.password = "Meet all four requirements below before continuing.";
    }
    return found;
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();

    const found = validate();
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    const result = await signUpWithPassword(email, password, name);

    if (!result.ok) {
      setFormError(result.error ?? "That didn't work.");
      setSubmitting(false);
      return;
    }

    toast({ tone: "success", title: "Account created" });

    // Confirmation is disabled on this project, so signup returns a session and the
    // user goes straight into the dashboard rather than a "check your inbox" dead end.
    // OnboardingGate shows the mandatory org-setup modal over it immediately.
    router.replace("/app");
    router.refresh();
  }

  return (
    <AuthCard
      title="Start free"
      description="No card required. Start with a free daily call budget."
      footer={
        <>
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
          >
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Field label="Your name" error={errors.name} required>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
            autoFocus
            disabled={submitting}
          />
        </Field>

        <Field
          label="Work email"
          error={errors.email ?? formError}
          help={
            suggestWorkEmail
              ? "A work address names your organisation automatically — but this one is fine."
              : undefined
          }
          required
        >
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            disabled={submitting}
          />
        </Field>

        <Field label="Password" error={errors.password} required>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            disabled={submitting}
          />
        </Field>

        <PasswordStrength value={password} />

        <Button type="submit" size="lg" className="w-full" loading={submitting}>
          Start free
        </Button>

        <p className="text-small text-text-mute">
          By continuing you agree to the{" "}
          <Link href="/trust" className="underline decoration-rule-strong underline-offset-2">
            terms
          </Link>{" "}
          and{" "}
          <Link href="/trust" className="underline decoration-rule-strong underline-offset-2">
            privacy policy
          </Link>
          .
        </p>
      </form>
    </AuthCard>
  );
}
