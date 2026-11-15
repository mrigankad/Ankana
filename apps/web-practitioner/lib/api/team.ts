import { isFixtures } from "./client";
import * as fx from "./fixture-admin";
import { v1Get, v1Patch, v1Post, v1Put, v1Request } from "./v1";

export type StaffRole = "owner" | "astrologer" | "assistant";
export type MemberRole = StaffRole | "client";

export interface Member {
  member_id: string;
  user_id: string;
  email: string | null;
  name: string | null;
  role: MemberRole;
  client_id: string | null;
}

export interface Invite {
  id: string;
  email: string;
  role: MemberRole;
  client_id: string | null;
  expires_at: string;
}

export interface PracticeInfo {
  id: string;
  name: string;
  timezone: string;
}

export interface ClientOption {
  id: string;
  display_name: string;
}

export const ROLE_LABEL: Record<MemberRole, string> = {
  owner: "Owner",
  astrologer: "Astrologer",
  assistant: "Assistant",
  client: "Client portal",
};

export const ROLE_CAN: Record<MemberRole, string> = {
  owner: "Everything, including billing and team",
  astrologer: "Charts, readings, remedies, notes",
  assistant: "Clients, bookings, reminders. No notes",
  client: "Sees only their own portal",
};

export const listMembers = (): Promise<Member[]> =>
  isFixtures() ? Promise.resolve([...fx.fxMembers]) : v1Get<{ members: Member[] }>("/practice/members", 15000).then((r) => r.members);
export const listInvites = (): Promise<Invite[]> =>
  isFixtures() ? Promise.resolve([...fx.fxInvites]) : v1Get<{ invites: Invite[] }>("/practice/invites", 15000).then((r) => r.invites);
export const createInvite = (b: { email: string; role: MemberRole; client_id?: string | null }): Promise<Invite> => {
  if (isFixtures()) {
    // Sample mode: apply to the in-memory list only. Inviting the same address again replaces the old invite.
    const invite: Invite = { id: `i${Date.now()}`, email: b.email, role: b.role, client_id: b.client_id ?? null, expires_at: new Date(Date.now() + 7 * 86_400_000).toISOString() };
    fx.fxInvites.splice(0, fx.fxInvites.length, ...fx.fxInvites.filter((i) => i.email.toLowerCase() !== b.email.toLowerCase()), invite);
    return Promise.resolve(invite);
  }
  return v1Post<Invite>("/practice/invites", { email: b.email, role: b.role, ...(b.client_id ? { client_id: b.client_id } : {}) });
};
export const revokeInvite = (id: string): Promise<void> => {
  if (isFixtures()) {
    fx.fxInvites.splice(0, fx.fxInvites.length, ...fx.fxInvites.filter((i) => i.id !== id));
    return Promise.resolve();
  }
  return v1Request<void>("DELETE", `/practice/invites/${id}`);
};
export const changeRole = (memberId: string, role: StaffRole): Promise<{ member_id: string; role: StaffRole }> => {
  if (isFixtures()) {
    const m = fx.fxMembers.find((x) => x.member_id === memberId);
    if (m) m.role = role;
    return Promise.resolve({ member_id: memberId, role });
  }
  return v1Patch<{ member_id: string; role: StaffRole }>(`/practice/members/${memberId}`, { role });
};
export const removeMember = (memberId: string): Promise<void> => {
  if (isFixtures()) {
    fx.fxMembers.splice(0, fx.fxMembers.length, ...fx.fxMembers.filter((m) => m.member_id !== memberId));
    return Promise.resolve();
  }
  return v1Request<void>("DELETE", `/practice/members/${memberId}`);
};
export const getPractice = (): Promise<PracticeInfo> => (isFixtures() ? Promise.resolve({ ...fx.fxPractice }) : v1Get<PracticeInfo>("/practice", 15000));
export const renamePractice = (name: string): Promise<PracticeInfo> => {
  if (isFixtures()) {
    fx.fxPractice.name = name;
    return Promise.resolve({ ...fx.fxPractice });
  }
  return v1Patch<PracticeInfo>("/practice", { name });
};
export const setTimezone = (timezone: string) =>
  isFixtures()
    ? Promise.resolve({ timezone: (fx.fxPractice.timezone = timezone) })
    : v1Request<{ timezone: string }>("PUT", "/notification-settings", { body: { timezone } });
export const listClientOptions = (): Promise<ClientOption[]> =>
  isFixtures() ? Promise.resolve([...fx.fxClients]) : v1Get<{ clients: ClientOption[] }>("/clients", 15000, { limit: 200 }).then((r) => r.clients);

export interface PracticePlace {
  label: string | null;
  latitude: number | null;
  longitude: number | null;
  source: "practice" | "timezone_default" | "unset";
}
export const getPracticePlace = (): Promise<PracticePlace> =>
  isFixtures() ? Promise.resolve({ ...fx.fxPlace }) : v1Get<PracticePlace>("/practice/location", 15000);
export const setPracticePlace = (b: { place_label: string; latitude: number; longitude: number }): Promise<PracticePlace> => {
  if (isFixtures()) {
    Object.assign(fx.fxPlace, { label: b.place_label, latitude: b.latitude, longitude: b.longitude, source: "practice" as const });
    return Promise.resolve({ ...fx.fxPlace });
  }
  return v1Put<PracticePlace>("/practice/location", b);
};
