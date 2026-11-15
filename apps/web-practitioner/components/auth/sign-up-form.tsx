"use client";

import { useState, type FormEvent } from "react";

import { authApi, AuthApiError, type SessionPayload } from "@/lib/auth/api";
import { useT } from "@/lib/i18n/provider";
import { CodeField, Field, FormError, LinkButton, SubmitButton } from "./auth-shell";

function message(e: unknown, t: (s: string) => string): string {
  return e instanceof AuthApiError ? e.message : t("Something went wrong. Try again.");
}

/**
 * Two steps: details, then the emailed code. Without practiceName the person
 * joins an existing practice (invite), so only a name is asked for.
 */
export function SignUpForm({
  withPractice = true,
  presetEmail,
  onSession,
}: {
  withPractice?: boolean;
  presetEmail?: string;
  onSession: (s: SessionPayload) => void;
}) {
  const t = useT();
  const [step, setStep] = useState<"details" | "code">("details");
  const [name, setName] = useState("");
  const [practice, setPractice] = useState("");
  const [email, setEmail] = useState(presetEmail ?? "");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(message(e, t));
    } finally {
      setBusy(false);
    }
  }

  const submitDetails = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => {
      await authApi.signup({
        email: email.trim(),
        name: name.trim(),
        ...(withPractice ? { practice_name: practice.trim() } : {}),
      });
      setStep("code");
    });
  };

  const verify = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => onSession(await authApi.verifyCode(email.trim(), code)));
  };

  if (step === "code") {
    return (
      <form onSubmit={verify} className="flex flex-col gap-4">
        <p className="text-[14px] leading-5 text-body">{t("We sent a six digit code to {email}. It lasts 10 minutes.", { email: email.trim() })}</p>
        <CodeField value={code} onChange={setCode} />
        <FormError>{error}</FormError>
        <SubmitButton busy={busy} disabled={code.length !== 6}>
          {withPractice ? t("Create my practice") : t("Continue")}
        </SubmitButton>
        <LinkButton onClick={() => setStep("details")}>{t("Change my details")}</LinkButton>
      </form>
    );
  }

  return (
    <form onSubmit={submitDetails} className="flex flex-col gap-4">
      <Field id="name" label="Your name" autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} />
      {withPractice ? (
        <Field id="practice" label="Practice name" required value={practice} onChange={(e) => setPractice(e.target.value)} hint="Shown on reports and to your team. You can change it later." />
      ) : null}
      <Field id="email" label="Email" type="email" autoComplete="email" required value={email} readOnly={!!presetEmail} onChange={(e) => setEmail(e.target.value)} />
      <FormError>{error}</FormError>
      <SubmitButton busy={busy}>{t("Email me a code")}</SubmitButton>
    </form>
  );
}

/** Signed in but no practice yet (for example after sign-in with a provider). */
export function CreatePracticeForm({ token, onCreated }: { token: string; onCreated: () => void }) {
  const t = useT();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await authApi.createPractice(token, name.trim());
      onCreated();
    } catch (err) {
      setError(message(err, t));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Field id="practice" label="Practice name" required value={name} onChange={(e) => setName(e.target.value)} />
      <FormError>{error}</FormError>
      <SubmitButton busy={busy}>{t("Create my practice")}</SubmitButton>
    </form>
  );
}
