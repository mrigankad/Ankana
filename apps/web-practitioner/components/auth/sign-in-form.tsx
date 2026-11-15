"use client";

import { useState, type FormEvent } from "react";

import { authApi, AuthApiError, type AuthConfig, type SessionPayload } from "@/lib/auth/api";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import { CodeField, Field, FormError, LinkButton, SubmitButton } from "./auth-shell";

const REDIRECT_ERRORS: Record<string, string> = {
  oidc_unavailable: "That sign-in provider is not reachable right now.",
  oidc_denied: "Sign-in was cancelled at the provider.",
  oidc_failed: "The provider could not confirm your identity.",
  oidc_email_unverified: "Your provider did not confirm a verified email address.",
  oidc_state_invalid: "That sign-in link expired. Start again.",
  signup_disabled: "Sign-up is closed on this server.",
};

function message(e: unknown, t: (s: string) => string): string {
  return e instanceof AuthApiError ? e.message : t("Something went wrong. Try again.");
}

export function SignInForm({
  config,
  next,
  redirectError,
  onSession,
}: {
  config: AuthConfig;
  next: string;
  redirectError?: string | null;
  onSession: (s: SessionPayload) => void;
}) {
  const t = useT();
  const [method, setMethod] = useState<"code" | "password">("code");
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(redirectError ? ((REDIRECT_ERRORS[redirectError] ? t(REDIRECT_ERRORS[redirectError]) : null)) : null);
  const [notice, setNotice] = useState<string | null>(null);

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

  const sendCode = (e?: FormEvent) => {
    e?.preventDefault();
    return run(async () => {
      await authApi.requestCode(email.trim());
      setStep("code");
      setCode("");
      setNotice(t("If {email} has an account, a code is on its way. It lasts {n} minutes.", { email: email.trim(), n: Math.round(config.otp_ttl_seconds / 60) }));
    });
  };

  const verify = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => onSession(await authApi.verifyCode(email.trim(), code)));
  };

  const signInWithPassword = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => onSession(await authApi.passwordSignin(email.trim(), password)));
  };

  return (
    <div className="flex flex-col gap-4">
      {config.password ? (
        <div role="tablist" aria-label={t("Sign-in method")} className="grid grid-cols-2 gap-1 rounded-[6px] bg-sidebar-wash p-1">
          {(
            [
              ["code", "Email code"],
              ["password", "Password"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={method === id}
              onClick={() => {
                setMethod(id);
                setError(null);
              }}
              className={cn(
                "h-9 rounded-[5px] text-[14px] font-bold",
                method === id ? "bg-white text-ink shadow-[0_1px_2px_rgba(34,30,29,0.08)]" : "text-body",
              )}
            >
              {t(label)}
            </button>
          ))}
        </div>
      ) : null}

      {method === "code" && step === "email" ? (
        <form onSubmit={sendCode} className="flex flex-col gap-4">
          <Field id="email" label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("you@practice.in")} />
          <FormError>{error}</FormError>
          <SubmitButton busy={busy}>{t("Email me a code")}</SubmitButton>
        </form>
      ) : null}

      {method === "code" && step === "code" ? (
        <form onSubmit={verify} className="flex flex-col gap-4">
          {notice ? <p className="text-[14px] leading-5 text-body">{notice}</p> : null}
          <CodeField value={code} onChange={setCode} />
          <FormError>{error}</FormError>
          <SubmitButton busy={busy} disabled={code.length !== 6}>
            {t("Sign in")}
          </SubmitButton>
          <div className="flex justify-between">
            <LinkButton onClick={() => sendCode()}>{t("Send a new code")}</LinkButton>
            <LinkButton
              onClick={() => {
                setStep("email");
                setError(null);
              }}
            >
              {t("Use another email")}
            </LinkButton>
          </div>
        </form>
      ) : null}

      {method === "password" ? (
        <form onSubmit={signInWithPassword} className="flex flex-col gap-4">
          <Field id="pw-email" label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Field id="password" label="Password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          <FormError>{error}</FormError>
          <SubmitButton busy={busy}>{t("Sign in")}</SubmitButton>
        </form>
      ) : null}

      {config.oidc.length > 0 ? (
        <>
          <div className="flex items-center gap-3 text-[12px] leading-4 text-soft">
            <span className="h-px grow bg-rule" />
            {t("or")}
            <span className="h-px grow bg-rule" />
          </div>
          <div className="flex flex-col gap-2">
            {config.oidc.map((p) => (
              <a
                key={p.id}
                href={authApi.oidcStartUrl(p.id, next)}
                className="flex h-11 items-center justify-center gap-2 rounded-[6px] border border-rule bg-white text-[15px] font-bold text-ink no-underline hover:bg-sidebar-wash"
              >
                <span className="flex size-5 items-center justify-center rounded-full bg-wash text-[11px] text-accent-text">
                  {p.label.slice(0, 1).toUpperCase()}
                </span>
                {t("Sign in with {name}", { name: p.label })}
              </a>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
