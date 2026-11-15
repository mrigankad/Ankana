import { getApiBaseUrl, withFixture } from "./client";
import { ProblemError, authHeaders, v1Get } from "./v1";

export interface NeedsFollowup {
  consultation_id: string;
  client_id: string;
  client_name: string;
  follow_up_date: string;
  days_overdue: number;
  topic: string | null;
}
export interface NeedsMissed {
  plan_id: string;
  client_id: string;
  client_name: string;
  title: string;
  last_missed_date: string;
  missed_days: number;
  policy: string;
  restart_count: number;
  extended_days: number;
  day_number: number;
  total_days: number;
  item_count: number;
}
export interface NeedsEnded {
  plan_id: string;
  client_id: string;
  client_name: string;
  title: string;
  end_date: string;
}
export interface NeedsFailed {
  id: string;
  client_id: string;
  client_name: string | null;
  kind: string;
  channel: string;
  last_error: string | null;
  created_at: string;
}
export interface NeedsYou {
  /** True when this is built-in sample content, not the practice's own data. */
  sample?: boolean;
  today: string;
  followups: NeedsFollowup[];
  missed_remedies: NeedsMissed[];
  ended_plans: NeedsEnded[];
  failed_notifications: NeedsFailed[];
}

export interface NotificationRow {
  id: string;
  kind: string;
  channel: string;
  language: string;
  local_date: string;
  status: "pending" | "sent" | "failed" | "skipped" | "cancelled";
  skip_reason: string | null;
  subject: string | null;
  scheduled_for: string;
  sent_at: string | null;
  last_error: string | null;
}

export interface NotificationPrefs {
  email_opt_in: boolean;
  whatsapp_opt_in: boolean;
  sms_opt_in: boolean;
  quiet_start: string;
  quiet_end: string;
  language: "en" | "hi";
  reminders_consent: boolean;
  eligible_channels: string[];
}

async function v1Send<T>(method: "POST" | "PUT", path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${getApiBaseUrl()}/v1${path}`, {
    method,
    headers: { ...(await authHeaders()), "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let problem = null;
    try {
      problem = await res.json();
    } catch {
      // not problem+json
    }
    throw new ProblemError(res.status, problem);
  }
  return (await res.json()) as T;
}

export const needsYouFixture: NeedsYou = {
  sample: true,
  today: "2026-11-14",
  followups: [
    { consultation_id: "cs-meera-1", client_id: "client-meera-iyer", client_name: "Meera Iyer", follow_up_date: "12 Nov", days_overdue: 2, topic: "Rectify, lagna changes inside 12 minutes of the recorded time" },
    { consultation_id: "cs-vikram-1", client_id: "client-vikram-rao", client_name: "Vikram Rao", follow_up_date: "14 Nov", days_overdue: 0, topic: "Review the draft Lal Kitab upay, 2 remedies" },
    { consultation_id: "cs-sana-1", client_id: "client-sana-qureshi", client_name: "Sana Qureshi", follow_up_date: "18 Nov", days_overdue: 0, topic: "40-day remedy ends Tuesday, send a check-in" },
  ],
  missed_remedies: [],
  ended_plans: [],
  failed_notifications: [],
};

export const notifyApi = {
  needsYou: () => withFixture(() => v1Get<NeedsYou>("/needs-you"), () => needsYouFixture),
  prefs: (clientId: string) => v1Get<NotificationPrefs>(`/clients/${clientId}/notification-prefs`),
  savePrefs: (clientId: string, patch: Partial<NotificationPrefs>) =>
    v1Send<NotificationPrefs>("PUT", `/clients/${clientId}/notification-prefs`, patch),
  list: (clientId: string) =>
    v1Get<{ notifications: NotificationRow[] }>(`/notifications?client_id=${clientId}&limit=8`),
  resend: (id: string) => v1Send<unknown>("POST", `/notifications/${id}/resend`),
};

export const KIND_LABEL: Record<string, string> = {
  remedy_due: "Daily reminder",
  remedy_missed: "Missed day",
  ending_soon: "Nearly done",
  plan_complete: "Plan complete",
  followup_due: "Follow-up",
};
