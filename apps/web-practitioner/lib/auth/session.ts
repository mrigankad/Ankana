import { authApi, type AuthUser, type Membership, type SessionPayload } from "./api";

/**
 * In-memory session. The access token never touches storage; the refresh token
 * is an httpOnly cookie the browser sends to the API. The selected practice is
 * the only thing remembered (localStorage), and only as a preference.
 */
export interface SessionState {
  status: "loading" | "authed" | "anon";
  accessToken: string | null;
  expiresAt: number;
  user: AuthUser | null;
  memberships: Membership[];
  practiceId: string | null;
}

const PRACTICE_KEY = "ankana.practice";
let state: SessionState = {
  status: "loading",
  accessToken: null,
  expiresAt: 0,
  user: null,
  memberships: [],
  practiceId: null,
};
const listeners = new Set<() => void>();

function emit(next: SessionState) {
  state = next;
  listeners.forEach((l) => l());
}

export const getSession = () => state;
export function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/** Auth UI is on only when the deployment asks for it, so fixture and token dev modes keep working. */
export function authEnabled(): boolean {
  return process.env.NEXT_PUBLIC_AUTH_MODE === "builtin";
}

function storedPractice(): string | null {
  try {
    return window.localStorage.getItem(PRACTICE_KEY);
  } catch {
    return null;
  }
}

export function applySession(p: SessionPayload) {
  const ids = p.memberships.map((m) => m.practice_id);
  const preferred = [storedPractice(), p.active_practice_id].find((id) => id && ids.includes(id));
  const practiceId = preferred ?? ids[0] ?? null;
  emit({
    status: "authed",
    accessToken: p.access_token ?? null,
    expiresAt: Date.now() + (p.expires_in ?? 0) * 1000,
    user: p.user,
    memberships: p.memberships,
    practiceId,
  });
}

export function clearSession() {
  emit({ status: "anon", accessToken: null, expiresAt: 0, user: null, memberships: [], practiceId: null });
}

export function selectPractice(practiceId: string) {
  try {
    window.localStorage.setItem(PRACTICE_KEY, practiceId);
  } catch {
    // preference only
  }
  emit({ ...state, practiceId });
}

let inflight: Promise<SessionPayload | null> | null = null;

/** One refresh at a time: the server treats a replayed refresh token as theft. */
export function refreshSession(): Promise<SessionPayload | null> {
  if (!inflight) {
    inflight = authApi
      .refresh()
      .then((p) => {
        applySession(p);
        return p;
      })
      .catch(() => {
        clearSession();
        return null;
      })
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}

/** Token for an API call, refreshed first when it is about to expire. */
export async function getFreshToken(): Promise<string | null> {
  if (state.status === "authed" && state.accessToken && state.expiresAt - Date.now() > 30_000) {
    return state.accessToken;
  }
  const p = await refreshSession();
  return p?.access_token ?? null;
}

export async function signOut() {
  try {
    await authApi.signout();
  } finally {
    clearSession();
  }
}
