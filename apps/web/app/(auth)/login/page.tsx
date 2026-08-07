"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthCard } from "@/components/layout/auth-card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { signInWithPassword } from "@/lib/auth/actions";

export default function LoginPage() {
  return (
    <Suspense fallback={<AuthCard title="Sign in">{null}</AuthCard>}>
      <SignInForm />
    </Suspense>
  );
}

function SignInForm() {
  const router = useRouter();
  const toast = useToast();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();

    if (!email.trim() || !password) {
      // One message covering both fields: naming which half failed tells an
      // attacker whether the address is registered.
      setError("Enter your email and password.");
      return;
    }

    setSubmitting(true);
    setError(null);

    const result = await signInWithPassword(email, password);

    if (!result.ok) {
      setError(result.error ?? "That didn't work.");
      setSubmitting(false);
      return;
    }

    toast({ tone: "success", title: "Signed in" });

    const next = searchParams.get("next");
    // Internal paths only, so a crafted ?next= cannot bounce someone off-site.
    router.replace(next?.startsWith("/app") ? next : "/app");
    router.refresh();
  }

  return (
    <AuthCard
      title="Sign in"
      footer={
        <>
          New here?{" "}
          <Link
            href="/signup"
            className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
          >
            Start free
          </Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Field label="Email" error={error} required>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            autoFocus
            disabled={submitting}
          />
        </Field>

        <Field label="Password" required>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            disabled={submitting}
          />
        </Field>

        <div className="flex items-center justify-between gap-3">
          <Checkbox
            checked={remember}
            onCheckedChange={setRemember}
            label="Remember me"
            id="remember"
          />
          <Link
            href="/forgot-password"
            className="text-small text-text-dim underline decoration-rule-strong underline-offset-2 hover:text-text hover:decoration-current"
          >
            Forgot password
          </Link>
        </div>

        <Button type="submit" size="lg" className="w-full" loading={submitting}>
          Sign in
        </Button>
      </form>
    </AuthCard>
  );
}
