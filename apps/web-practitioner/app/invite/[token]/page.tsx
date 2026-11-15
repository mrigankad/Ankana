"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";

import { AuthShell, FormError, LinkButton, SubmitButton } from "@/components/auth/auth-shell";
import { useAuth } from "@/components/auth/auth-provider";
import { SignUpForm } from "@/components/auth/sign-up-form";
import { authApi, AuthApiError, type InvitePreview } from "@/lib/auth/api";
import { useT } from "@/lib/i18n/provider";
import { refreshSession, selectPractice, signOut } from "@/lib/auth/session";

const ROLE_TEXT: Record<string, string> = {
  owner: "an owner",
  astrologer: "an astrologer",
  assistant: "an assistant",
  client: "a client with portal access",
};

export default function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const t = useT();
  const router = useRouter();
  const { session, completeSignIn } = useAuth();
  const [invite, setInvite] = useState<InvitePreview | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    authApi
      .previewInvite(token)
      .then(setInvite)
      .catch((e) => setProblem(e instanceof AuthApiError ? e.message : t("Could not load this invitation.")));
  }, [token]);

  async function accept() {
    if (!session.accessToken) return;
    setBusy(true);
    setProblem(null);
    try {
      const joined = await authApi.acceptInvite(session.accessToken, token);
      await refreshSession();
      selectPractice(joined.practice_id);
      router.replace("/");
    } catch (e) {
      setProblem(e instanceof AuthApiError ? e.message : t("Could not accept the invitation."));
      setBusy(false);
    }
  }

  if (!invite) {
    return (
      <AuthShell title="Invitation">
        {problem ? <FormError>{problem}</FormError> : <p className="text-[14px] text-body">{t("Loading")}</p>}
      </AuthShell>
    );
  }

  const title = t("Join {name}", { name: invite.practice_name });
  const subtitle = t("You were invited as {role}.", { role: t(ROLE_TEXT[invite.role] ?? invite.role) });
  const authed = session.status === "authed" && session.user;
  const matches = authed && session.user?.email?.toLowerCase() === invite.email.toLowerCase();

  if (authed && matches) {
    return (
      <AuthShell title={title} subtitle={subtitle}>
        <FormError>{problem}</FormError>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void accept();
          }}
        >
          <SubmitButton busy={busy}>{t("Accept invitation")}</SubmitButton>
        </form>
      </AuthShell>
    );
  }

  if (authed) {
    return (
      <AuthShell title={title} subtitle={subtitle}>
        <p className="text-[14px] leading-5 text-body">
          {t("This invitation is for {hint}, but you are signed in as {email}.", { hint: invite.email_hint, email: session.user?.email ?? "" })}
        </p>
        <LinkButton onClick={() => void signOut()}>{t("Sign out and use the invited address")}</LinkButton>
      </AuthShell>
    );
  }

  return (
    <AuthShell title={title} subtitle={`${subtitle} ${t("Confirm {hint} with a code and you are in.", { hint: invite.email_hint })}`}>
      <SignUpForm withPractice={false} presetEmail={invite.email} onSession={(s) => completeSignIn(s, `/invite/${token}`)} />
    </AuthShell>
  );
}
