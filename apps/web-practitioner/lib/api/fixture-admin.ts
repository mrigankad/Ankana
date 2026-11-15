import type { Invite, Member, PracticeInfo, PracticePlace, ClientOption } from "./team";
import type { PortalSummary, RemedyPlan, Consent, ConsentReceipt } from "./portal";
import type { DeviceSession } from "@/lib/auth/api";

/** Sample content for the admin and portal screens when the app runs without a server (fixtures mode). */
const day = 86_400_000;
const ago = (d: number) => new Date(Date.now() - d * day).toISOString();
const ahead = (d: number) => new Date(Date.now() + d * day).toISOString();

export const fxMembers: Member[] = [
  { member_id: "m1", user_id: "u1", email: "rohan@example.com", name: "Rohan Shastri", role: "owner", client_id: null },
  { member_id: "m2", user_id: "u2", email: "arun@example.com", name: "Arun Pandey", role: "astrologer", client_id: null },
  { member_id: "m3", user_id: "u3", email: "kavya@example.com", name: "Kavya Rao", role: "assistant", client_id: null },
];
export const fxInvites: Invite[] = [
  { id: "i1", email: "rohit@example.com", role: "astrologer", client_id: null, expires_at: ahead(5) },
  { id: "i2", email: "sunita@example.com", role: "client", client_id: "c1", expires_at: ahead(3) },
];
export const fxPractice: PracticeInfo = { id: "p1", name: "Shastri Jyotish, Pune", timezone: "Asia/Kolkata" };
export const fxPlace: PracticePlace = { label: null, latitude: null, longitude: null, source: "unset" };
export const fxClients: ClientOption[] = [
  { id: "c1", display_name: "Ananya Sharma" },
  { id: "c2", display_name: "Vikram Mehta" },
];
export const fxSessions: DeviceSession[] = [
  { id: "s1", method: "otp", ip: "103.21.4.18", user_agent: "Mozilla/5.0 (Windows NT 10.0) Chrome/126.0", created_at: ago(3), last_used_at: new Date().toISOString(), current: true },
  { id: "s2", method: "password", ip: "49.36.10.7", user_agent: "Mozilla/5.0 (iPhone) Safari/605.1", created_at: ago(9), last_used_at: ago(1), current: false },
];

export const fxSummary: PortalSummary = {
  client_id: "c1",
  display_name: "Ananya Sharma",
  practice_name: "Shastri Jyotish, Pune",
  next_appointment: { id: "a1", at: ahead(4), date: ahead(4).slice(0, 10), mode: "video", topic: "Career timing review", kind: "follow_up" },
  reports: [{ id: "r1", template: "Full reading", language: "en", created_at: ago(12), size_bytes: 1_800_000, download_url: null }],
  today: new Date().toISOString().slice(0, 10),
};
export const fxPlan: RemedyPlan = {
  id: "rp1",
  title: "Saturn steadiness, 40 days",
  status: "active",
  cycle_days: 40,
  start_date: ago(11).slice(0, 10),
  end_date: ahead(29).slice(0, 10),
  day_number: 12,
  items: [
    { id: "it1", title: "Light a sesame oil lamp at dusk", instructions: "Saturdays, facing west.", planet: "saturn", done_days: 9, done_today: false },
    { id: "it2", title: "Chant the Shani mantra", instructions: "11 rounds after sunrise.", planet: "saturn", done_days: 11, done_today: true },
  ],
};
export const fxConsents: Consent[] = [
  { id: "k1", purpose: "chart_compute", notice_version: "1", granted_at: ago(40), withdrawn_at: null },
  { id: "k2", purpose: "reminders", notice_version: "1", granted_at: ago(40), withdrawn_at: null },
];
export const fxReceipts: ConsentReceipt[] = [];
