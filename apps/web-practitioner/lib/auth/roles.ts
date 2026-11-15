import type { Membership } from "./api";
import type { SessionState } from "./session";

export type Role = Membership["role"];

/** The role of the signed-in user in the practice they are looking at; null when signed out. */
export function activeRole(session: Pick<SessionState, "memberships" | "practiceId">): Role | null {
  const m = session.memberships.find((x) => x.practice_id === session.practiceId) ?? session.memberships[0];
  return m?.role ?? null;
}

const OWNER_ONLY = ["/settings/team", "/settings/practice", "/settings/billing"];
const hit = (path: string, prefix: string) => path === prefix || path.startsWith(prefix + "/");

/**
 * Which paths a role may open. Clients see only the portal; staff never see it;
 * owner-only settings are refused to astrologers and assistants.
 */
export function pathAllowed(role: Role | null, path: string): boolean {
  if (role === null) return true; // auth off or not resolved yet: the API still enforces roles
  if (role === "client") return hit(path, "/portal");
  if (hit(path, "/portal")) return false;
  if (role !== "owner" && OWNER_ONLY.some((p) => hit(path, p))) return false;
  return true;
}

/** Where a role lands when it opens a path it may not see. */
export const homeFor = (role: Role | null): string => (role === "client" ? "/portal" : "/");
