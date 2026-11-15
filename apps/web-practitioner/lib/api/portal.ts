import { isFixtures } from "./client";
import * as fx from "./fixture-admin";
import { v1Get, v1Post } from "./v1";

export interface PortalAppointment {
  id: string;
  at: string | null;
  date: string | null;
  mode: string | null;
  topic: string | null;
  kind: "consultation" | "follow_up";
}

export interface PortalReport {
  id: string;
  template: string;
  language: string;
  created_at: string;
  size_bytes: number | null;
  download_url: string | null;
}

export interface PortalSummary {
  client_id: string;
  display_name: string;
  practice_name: string;
  next_appointment: PortalAppointment | null;
  reports: PortalReport[];
  today: string;
}

export interface PlanItem {
  id: string;
  title: string;
  instructions: string | null;
  planet: string | null;
  done_days: number;
  done_today: boolean;
}

export interface RemedyPlan {
  id: string;
  title: string;
  status: "draft" | "active" | "completed" | "cancelled";
  cycle_days: number;
  start_date: string | null;
  end_date: string | null;
  day_number: number | null;
  items: PlanItem[];
}

export interface Consent {
  id: string;
  purpose: string;
  notice_version: string;
  granted_at: string;
  withdrawn_at: string | null;
}

export interface ConsentReceipt {
  id: string;
  consent_id: string;
  event: "granted" | "withdrawn";
  purpose: string;
  notice_version: string;
  occurred_at: string;
  receipt_hash: string;
  verified: boolean;
  notice_text: string | null;
}

export interface PrivacyRequest {
  id: string;
  kind: string;
  status: string;
  download_url: string | null;
}

export const getSummary = (): Promise<PortalSummary> => (isFixtures() ? Promise.resolve({ ...fx.fxSummary, practice_name: fx.fxPractice.name }) : v1Get<PortalSummary>("/portal/summary", 15000));

export async function getActivePlan(clientId: string): Promise<RemedyPlan | null> {
  if (isFixtures()) return { ...fx.fxPlan, items: fx.fxPlan.items.map((i) => ({ ...i })) };
  const r = await v1Get<{ remedy_plans: RemedyPlan[] }>(`/clients/${clientId}/remedy-plans`, 15000);
  return r.remedy_plans.find((p) => p.status === "active") ?? null;
}

export const checkIn = (planId: string, itemId: string): Promise<unknown> => {
  if (isFixtures()) {
    const it = fx.fxPlan.items.find((i) => i.id === itemId);
    if (it && !it.done_today) {
      it.done_today = true;
      it.done_days += 1;
    }
    return Promise.resolve({});
  }
  return v1Post(`/remedy-plans/${planId}/items/${itemId}/checkins`, { done: true });
};

export const getConsents = (clientId: string) =>
  isFixtures() ? Promise.resolve({ consents: [...fx.fxConsents], active: Object.fromEntries(fx.fxConsents.filter((c) => !c.withdrawn_at).map((c) => [c.purpose, true])) as Record<string, boolean> }) : v1Get<{ consents: Consent[]; active: Record<string, boolean> }>(`/clients/${clientId}/consents`, 15000);

export const withdrawConsent = (clientId: string, purpose: string): Promise<unknown> => {
  if (isFixtures()) {
    for (const c of fx.fxConsents) if (c.purpose === purpose && !c.withdrawn_at) c.withdrawn_at = new Date().toISOString();
    return Promise.resolve({});
  }
  return v1Post(`/clients/${clientId}/consents/${purpose}/withdraw`, {});
};

export const getReceipts = (clientId: string): Promise<ConsentReceipt[]> =>
  isFixtures() ? Promise.resolve([...fx.fxReceipts]) : v1Get<{ receipts: ConsentReceipt[] }>(`/clients/${clientId}/consent-receipts`, 15000).then((r) => r.receipts);

export const requestExport = (clientId: string): Promise<PrivacyRequest> =>
  isFixtures() ? Promise.resolve({ id: "sample-export", kind: "export", status: "done", download_url: null }) : v1Post<PrivacyRequest>(`/clients/${clientId}/export`, {});
export const getPrivacyRequest = (id: string): Promise<PrivacyRequest> =>
  isFixtures() ? Promise.resolve({ id, kind: "export", status: "done", download_url: null }) : v1Get<PrivacyRequest>(`/privacy/requests/${id}`, 15000);

export const PURPOSE_LABEL: Record<string, string> = {
  chart_compute: "Chart calculation",
  ai_assistant: "AI assistant",
  report_sharing: "Sharing my reports",
  marketing: "News and offers",
  reminders: "Reminders",
};
