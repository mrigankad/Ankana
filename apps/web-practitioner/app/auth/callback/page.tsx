"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { safeNext } from "@/components/auth/auth-provider";
import { refreshSession } from "@/lib/auth/session";

/** Return point after "Sign in with ...": the API set the refresh cookie, trade it for a session. */
function Callback() {
  const params = useSearchParams();
  const router = useRouter();
  useEffect(() => {
    const next = safeNext(params.get("next"));
    void refreshSession().then((p) => {
      if (!p) router.replace("/sign-in?error=oidc_failed");
      else router.replace(p.memberships.length === 0 ? "/sign-up?step=practice" : next);
    });
  }, [params, router]);
  return (
    <div className="flex min-h-svh items-center justify-center bg-wash-soft text-[14px] text-body" role="status">
      Finishing sign-in
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense>
      <Callback />
    </Suspense>
  );
}
