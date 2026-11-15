"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { AuthShell } from "@/components/auth/auth-shell";
import { safeNext, useAuth } from "@/components/auth/auth-provider";
import { SignInForm } from "@/components/auth/sign-in-form";
import { useT } from "@/lib/i18n/provider";
import { authApi, type AuthConfig } from "@/lib/auth/api";

const FALLBACK: AuthConfig = {
  email_code: true,
  phone_code: false,
  password: false,
  signup: true,
  oidc: [],
  password_min_length: 10,
  otp_ttl_seconds: 600,
};

function SignInScreen() {
  const t = useT();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const { completeSignIn, session, enabled } = useAuth();
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [unreachable, setUnreachable] = useState(false);

  useEffect(() => {
    authApi
      .config()
      .then(setConfig)
      .catch(() => {
        setConfig(FALLBACK);
        setUnreachable(true);
      });
  }, []);

  useEffect(() => {
    if (enabled && session.status === "authed" && session.memberships.length > 0) {
      window.location.replace(next);
    }
  }, [enabled, session.status, session.memberships.length, next]);

  return (
    <AuthShell
      title="Sign in to Ankana"
      subtitle="Use the email your practice knows you by."
      footer={
        config?.signup ? (
          <>
            {t("New here?")}{" "}
            <Link href="/sign-up" className="font-bold text-accent-text no-underline hover:underline">
              {t("Create a practice")}
            </Link>
          </>
        ) : undefined
      }
    >
      {config ? (
        <>
          {unreachable ? (
            <p role="alert" className="rounded-[6px] bg-alert-wash px-3 py-[10px] text-[14px] leading-5 text-alert">
              {t("Cannot reach the Ankana server. Check that the API is running.")}
            </p>
          ) : null}
          <SignInForm
            config={config}
            next={next}
            redirectError={params.get("error")}
            onSession={(s) => completeSignIn(s, next)}
          />
        </>
      ) : (
        <p className="text-[14px] text-body">{t("Loading")}</p>
      )}
    </AuthShell>
  );
}

export default function SignInPage() {
  return (
    <Suspense>
      <SignInScreen />
    </Suspense>
  );
}
