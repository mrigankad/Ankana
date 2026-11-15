"use client";

import { createContext, useCallback, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import type { SessionPayload } from "@/lib/auth/api";
import { activeRole, homeFor, pathAllowed } from "@/lib/auth/roles";
import {
  applySession,
  authEnabled,
  getSession,
  refreshSession,
  subscribe,
  type SessionState,
} from "@/lib/auth/session";

const PUBLIC_PREFIXES = ["/sign-in", "/sign-up", "/invite", "/auth", "/design"];
export const isPublicPath = (path: string) => PUBLIC_PREFIXES.some((p) => path === p || path.startsWith(p + "/"));

const SERVER_STATE: SessionState = {
  status: "loading",
  accessToken: null,
  expiresAt: 0,
  user: null,
  memberships: [],
  practiceId: null,
};

interface AuthContextValue {
  enabled: boolean;
  session: SessionState;
  /** Store the session returned by a sign-in and go to `next` (or the practice setup). */
  completeSignIn: (p: SessionPayload, next?: string) => void;
}

const AuthContext = createContext<AuthContextValue>({
  enabled: false,
  session: SERVER_STATE,
  completeSignIn: () => undefined,
});
export const useAuth = () => useContext(AuthContext);

/** Only same-site relative paths survive; anything else becomes "/". */
export function safeNext(next: string | null | undefined): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const enabled = authEnabled();
  const session = useSyncExternalStore(subscribe, getSession, () => SERVER_STATE);
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const isPublic = isPublicPath(pathname);
  const role = activeRole(session);
  const allowed = !enabled || isPublic || session.status !== "authed" || pathAllowed(role, pathname);

  // Restore the session from the refresh cookie on first load.
  useEffect(() => {
    if (enabled && getSession().status === "loading") void refreshSession();
  }, [enabled]);

  // Keep the access token fresh while the tab is open.
  useEffect(() => {
    if (!enabled || session.status !== "authed") return;
    const wait = Math.max(session.expiresAt - Date.now() - 60_000, 5_000);
    const t = setTimeout(() => void refreshSession(), wait);
    return () => clearTimeout(t);
  }, [enabled, session.status, session.expiresAt]);

  // Route guard.
  useEffect(() => {
    if (!enabled || session.status === "loading" || isPublic) return;
    if (session.status === "anon") {
      router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
    } else if (session.memberships.length === 0) {
      router.replace("/sign-up?step=practice");
    } else if (!allowed) {
      router.replace(homeFor(role));
    }
  }, [enabled, session.status, session.memberships.length, isPublic, pathname, router, allowed, role]);

  const completeSignIn = useCallback(
    (p: SessionPayload, next?: string) => {
      applySession(p);
      const target = safeNext(next);
      router.replace(p.memberships.length === 0 && !isPublicPath(target) ? "/sign-up?step=practice" : target);
    },
    [router],
  );

  const blocked = enabled && !isPublic && (session.status !== "authed" || session.memberships.length === 0 || !allowed);

  return (
    <AuthContext.Provider value={{ enabled, session, completeSignIn }}>
      {blocked ? (
        <div className="flex min-h-svh items-center justify-center bg-wash-soft text-[14px] text-body" role="status">
          Opening your workspace
        </div>
      ) : (
        children
      )}
    </AuthContext.Provider>
  );
}
