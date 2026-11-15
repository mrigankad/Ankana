import { getApiBaseUrl } from "./client";
import { ProblemError, authHeaders, v1Get } from "./v1";

export type Limit = number | null;

export interface PlanInfo {
  key: string;
  name: string;
  limits: Record<string, Limit>;
  features: string[];
  price_month_paise: number;
  price_year_paise: number;
  total_month_paise: number;
  total_year_paise: number;
  gst_rate_bp: number;
}

export interface SubscriptionInfo {
  id: string;
  plan: string;
  interval: "month" | "year";
  status: "created" | "active" | "past_due" | "halted" | "cancelled";
  current_period_end: string | null;
  grace_until: string | null;
  cancel_at_period_end: boolean;
  checkout_url: string | null;
}

export interface UsageRow {
  metric: string;
  used: number;
  limit: Limit;
  period: string;
}

export interface BillingState {
  plan: PlanInfo;
  subscription: SubscriptionInfo | null;
  in_grace: boolean;
  pending_checkout: SubscriptionInfo | null;
  usage: UsageRow[];
}

export interface InvoiceRow {
  id: string;
  number: string;
  issued_at: string;
  total_paise: number;
  taxable_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  intra_state: boolean;
}

export interface BillingProfile {
  legal_name: string | null;
  gstin: string | null;
  state_code: string | null;
  address: string | null;
}

async function send<T>(method: "POST" | "PUT", path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${getApiBaseUrl()}/v1/billing${path}`, {
    method,
    headers: { ...(await authHeaders()), ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
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

export const getPlans = () => v1Get<{ plans: PlanInfo[] }>("/billing/plans", 15000);
export const getBilling = () => v1Get<BillingState>("/billing/subscription", 15000);
export const getInvoices = () => v1Get<{ items: InvoiceRow[] }>("/billing/invoices", 15000);
export const getProfile = () => v1Get<BillingProfile>("/billing/profile", 15000);
export const saveProfile = (b: BillingProfile) => send<BillingProfile>("PUT", "/profile", b);
export const startCheckout = (plan: string, interval: "month" | "year") =>
  send<{ checkout_url: string }>("POST", "/checkout", { plan, interval });
export const cancelSubscription = () => send<SubscriptionInfo>("POST", "/cancel");
export const invoiceDownload = (id: string) =>
  v1Get<{ download_url: string }>(`/billing/invoices/${id}/download`, 60000);

const METRIC_LABEL: Record<string, string> = {
  clients: "Clients",
  ai_asks: "AI questions this month",
  reports: "Reports this month",
};
export const metricLabel = (m: string) => METRIC_LABEL[m] ?? m;

/** Paise to a rupee string with Indian digit grouping, e.g. 70682 gives "706.82". */
export function rupees(paise: number): string {
  return new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(paise / 100);
}
