"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { AuthCard } from "@/components/layout/auth-card";
import { AuthNotice } from "@/components/layout/auth-notice";
import { Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { isPasswordValid, PasswordStrength } from "@/components/ui/password-strength";

/**
 * Accept an invitation.
 *
 * The organisation name and the role being granted are shown before anything is
 * accepted. Someone clicking a link from an email needs to know which company they are
 * joining and what access they are being given   "Admin" and "Viewer" are very
 * different things to accept blind, and in a product that dials real people the
 * difference matters.
 */
export default function AcceptInvitePage() {
  const params = useParams<{ token: string }>();
  const token = typeof params?.token === "string" ? params.token : "";

  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ name?: string; password?: string }>({});
  const [submitted, setSubmitted] = useState(false);

  // Without an account service there is nothing to resolve the token against, so the
  // invitation details are shown as unresolved rather than invented.
  const organisation: string | null = null;
  const role: string | null = null;

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const next: typeof errors = {};
    if (!name.trim()) next.name = "Add your name so teammates can see who you are.";
    if (!isPasswordValid(password)) {
      next.password = "Meet all four requirements below before continuing.";
    }
    setErrors(next);
    if (Object.keys(next).length === 0) setSubmitted(true);
  }

  return (
    <AuthCard
      title="Accept your invitation"
      description="Set a password and you'll join the team."
      footer={
        <>
          Not expecting this?{" "}
          <Link
            href="/"
            className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
          >
            Ignore it
          </Link>{" "}
            nothing happens until you set a password.
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Panel sunken className="flex flex-col gap-2 p-3">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-small text-text-mute">Organisation</span>
            <span className="text-small font-medium text-text">
              {organisation ?? "Couldn't be confirmed"}
            </span>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-small text-text-mute">Role</span>
            {role ? <Tag>{role}</Tag> : <span className="text-small text-text-dim"> </span>}
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-small text-text-mute">Invite code</span>
            <span className="font-mono text-data text-text-dim">
              {token ? `${token.slice(0, 8)}…` : " "}
            </span>
          </div>
        </Panel>

        {submitted ? (
          <AuthNotice heading="Invitations aren't connected yet" />
        ) : (
          <form onSubmit={submit} noValidate className="flex flex-col gap-4">
            <Field label="Your name" error={errors.name} required>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                autoFocus
              />
            </Field>

            <Field label="Password" error={errors.password} required>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </Field>

            <PasswordStrength value={password} />

            <Button type="submit" size="lg" className="w-full">
              Join the team
            </Button>
          </form>
        )}
      </div>
    </AuthCard>
  );
}
