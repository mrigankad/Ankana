"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { AuthShell } from "@/components/auth/auth-shell";
import { useAuth } from "@/components/auth/auth-provider";
import { CreatePracticeForm, SignUpForm } from "@/components/auth/sign-up-form";
import { useT } from "@/lib/i18n/provider";
import { refreshSession } from "@/lib/auth/session";

function SignUpScreen() {
  const t = useT();
  const params = useSearchParams();
  const router = useRouter();
  const { completeSignIn, session } = useAuth();
  const practiceStep = params.get("step") === "practice" && session.status === "authed" && !!session.accessToken;

  if (practiceStep) {
    return (
      <AuthShell title="Name your practice" subtitle="One last step. You become its owner and can invite your team afterwards.">
        <CreatePracticeForm
          token={session.accessToken as string}
          onCreated={async () => {
            await refreshSession();
            router.replace("/");
          }}
        />
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Create your practice"
      subtitle="We email you a six digit code to confirm your address. No password needed."
      footer={
        <>
          {t("Already have an account?")}{" "}
          <Link href="/sign-in" className="font-bold text-accent-text no-underline hover:underline">
            {t("Sign in")}
          </Link>
        </>
      }
    >
      <SignUpForm onSession={(s) => completeSignIn(s, "/")} />
    </AuthShell>
  );
}

export default function SignUpPage() {
  return (
    <Suspense>
      <SignUpScreen />
    </Suspense>
  );
}
