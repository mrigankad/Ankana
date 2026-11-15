"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import * as api from "@/lib/api/billing";
import type { BillingProfile, BillingState, InvoiceRow, PlanInfo } from "@/lib/api/billing";
import { getMeta } from "@/lib/api/v1";
import { ServerUnavailable } from "@/components/ankana/server-unavailable";
import { Btn, Chip, Eyebrow, Panel } from "@/components/ankana/ui";
import { EmptyState } from "@/components/ui/data";
import { isLive } from "@/lib/api/client";
import { useT } from "@/lib/i18n/provider";
import type { ChipTone } from "@/components/ankana/ui";

const FIELD =
  "w-full rounded-[6px] border border-rule bg-white px-3 py-2 text-[14px] leading-[18px] text-ink outline-none focus:border-sindoor";
const RANK = ["free", "solo", "studio"];
const EMPTY_PROFILE: BillingProfile = { legal_name: "", gstin: "", state_code: "", address: "" };

function message(e: unknown) {
  return e instanceof Error ? e.message : "Something went wrong.";
}

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "";

function statusChip(b: BillingState): { tone: ChipTone; text: string } {
  const s = b.subscription;
  if (!s) return { tone: "muted", text: "Free plan" };
  if (b.in_grace) return { tone: "alert", text: `Payment failed, plan kept until ${fmtDate(s.grace_until)}` };
  if (s.cancel_at_period_end) return { tone: "accent", text: `Ends ${fmtDate(s.current_period_end)}` };
  return { tone: "ok", text: `Active, renews ${fmtDate(s.current_period_end)}` };
}

function UsageBar({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const full = limit !== null && limit > 0 && used >= limit;
  return (
    <div className="flex flex-col gap-[6px]">
      <div className="flex justify-between text-[13px] leading-4">
        <span className="text-body">{label}</span>
        <span className="font-bold text-ink">{limit === null ? `${used} used, unlimited` : `${used} of ${limit}`}</span>
      </div>
      <div
        className="h-[6px] rounded-[3px] bg-rule"
        role="progressbar"
        aria-label={label}
        aria-valuenow={used}
        aria-valuemax={limit ?? undefined}
      >
        <div
          className="h-[6px] rounded-[3px]"
          style={{ width: limit === null ? "0%" : `${pct}%`, backgroundColor: full ? "var(--text-primary)" : "var(--accent)" }}
        />
      </div>
    </div>
  );
}

function PlanCard({
  plan,
  current,
  interval,
  busy,
  onChoose,
}: {
  plan: PlanInfo;
  current: BillingState;
  interval: "month" | "year";
  busy: boolean;
  onChoose: () => void;
}) {
  const isFree = plan.key === "free";
  const curKey = current.plan.key;
  const sameInterval = current.subscription?.interval === interval;
  const isCurrent = plan.key === curKey && (isFree || sameInterval);
  const lower = RANK.indexOf(plan.key) < RANK.indexOf(curKey);
  const net = interval === "year" ? plan.price_year_paise : plan.price_month_paise;
  const total = interval === "year" ? plan.total_year_paise : plan.total_month_paise;
  let action = `Upgrade to ${plan.name}`;
  if (isCurrent) action = "Your plan";
  else if (lower) action = "Cancel your plan to move down";
  else if (curKey !== "free" && plan.key === curKey) action = `Switch to ${interval === "year" ? "yearly" : "monthly"}`;
  return (
    <Panel className={`flex flex-col gap-3 p-4 ${isCurrent ? "border-sindoor" : ""}`}>
      <div className="flex items-center justify-between">
        <span className="text-[17px] font-bold leading-6 text-ink">{plan.name}</span>
        {isCurrent && <Chip tone="accent">Current</Chip>}
      </div>
      <div>
        <div className="text-[26px] font-bold leading-8 text-ink">{isFree ? "Free" : `Rs ${api.rupees(net)}`}</div>
        {!isFree && (
          <div className="text-[13px] leading-4 text-soft">
            per {interval === "year" ? "year" : "month"} plus GST, Rs {api.rupees(total)} in total
          </div>
        )}
      </div>
      <ul className="flex flex-col gap-1 text-[14px] leading-[18px] text-body">
        {Object.entries(plan.limits).map(([m, l]) => (
          <li key={m}>
            {l === null ? "Unlimited" : l === 0 ? "No" : l} {api.metricLabel(m).toLowerCase()}
          </li>
        ))}
        {plan.features.map((f) => (
          <li key={f}>{f}</li>
        ))}
      </ul>
      <div className="grow" />
      {isFree ? null : (
        <Btn variant="primary" disabled={busy || isCurrent || lower} onClick={onChoose}>
          {action}
        </Btn>
      )}
    </Panel>
  );
}

function BillingHeader({ subtitle }: { subtitle: string }) {
  return (
    <header className="flex flex-col gap-1">
      <h1 className="m-0 text-[28px] font-bold leading-9 tracking-[-0.02em] text-ink lg:text-[32px] lg:leading-10">Plan and billing</h1>
      <p className="m-0 max-w-[640px] text-[16px] leading-6 text-body">{subtitle}</p>
    </header>
  );
}

export function BillingSettings() {
  const t = useT();
  const [down, setDown] = useState(false);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [state, setState] = useState<BillingState | null>(null);
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [invoices, setInvoices] = useState<InvoiceRow[]>([]);
  const [profile, setProfile] = useState<BillingProfile>(EMPTY_PROFILE);
  const [interval, setInterval] = useState<"month" | "year">("month");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, p, i, pr] = await Promise.all([api.getBilling(), api.getPlans(), api.getInvoices(), api.getProfile()]);
      setState(s);
      setPlans(p.plans);
      setInvoices(i.items);
      setProfile({
        legal_name: pr.legal_name ?? "",
        gstin: pr.gstin ?? "",
        state_code: pr.state_code ?? "",
        address: pr.address ?? "",
      });
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, []);

  useEffect(() => {
    getMeta()
      .then((m) => {
        setEnabled(Boolean(m.billing));
        if (m.billing) void load();
      })
      .catch(() => {
        setDown(isLive());
        setEnabled(false);
      });
  }, [load]);

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await fn();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(null);
    }
  }

  if (enabled === null) return <div className="px-6 py-9 text-[14px] text-soft lg:px-10">{t("Loading")}</div>;
  if (!enabled) {
    return (
      <div className="flex flex-col gap-8 px-6 py-9 lg:px-10">
        <BillingHeader subtitle={t("Plans, usage and GST invoices for hosted practices.")} />
        {down ? (
          <ServerUnavailable />
        ) : (
          <Panel className="w-full max-w-[560px]">
            <EmptyState
              illustration={
                // eslint-disable-next-line @next/next/no-img-element
                <img src="/illustrations/illus-lota@2x.png" alt="" width={120} height={120} className="size-[120px] object-contain" />
              }
              title={t("Billing is off for this deployment")}
              description={t("There are no plans or limits here, so everything is unlimited. Plans appear when billing is switched on for a hosted practice.")}
            />
          </Panel>
        )}
      </div>
    );
  }

  const chip = state ? statusChip(state) : null;

  return (
    <div className="flex w-full max-w-[1120px] flex-col gap-6 px-6 py-9 lg:px-10">
      <BillingHeader subtitle={t("Prices exclude GST. Invoices carry your GSTIN when you add it below.")} />

      {error && (
        <div role="alert" className="rounded-[6px] bg-alert-wash px-3 py-2 text-[14px] leading-5 text-alert">
          {error}
        </div>
      )}
      {notice && <div className="rounded-[6px] bg-ok-wash px-3 py-2 text-[14px] leading-5 text-ok">{notice}</div>}

      {state && chip && (
        <Panel className="flex flex-col gap-4 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="text-[20px] font-bold leading-6 text-ink">{state.plan.name}</span>
              <Chip tone={chip.tone}>{chip.text}</Chip>
            </div>
            {state.subscription && !state.subscription.cancel_at_period_end && !confirmCancel && (
              <Btn variant="outline" onClick={() => setConfirmCancel(true)}>
                Cancel plan
              </Btn>
            )}
          </div>
          {confirmCancel && (
            <div className="flex flex-wrap items-center gap-3 rounded-[6px] bg-wash-soft px-3 py-3 text-[14px] leading-5 text-body">
              <span className="grow">
                Cancel at the end of the paid period? You keep your plan until then and your data is never deleted.
              </span>
              <Btn variant="outline" onClick={() => setConfirmCancel(false)}>
                Keep plan
              </Btn>
              <Btn
                variant="primary"
                disabled={busy === "cancel"}
                onClick={() =>
                  run("cancel", async () => {
                    await api.cancelSubscription();
                    setConfirmCancel(false);
                    setNotice("Your plan will end at the close of the current period.");
                    await load();
                  })
                }
              >
                Confirm cancel
              </Btn>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            {state.usage.map((u) => (
              <UsageBar key={u.metric} label={api.metricLabel(u.metric)} used={u.used} limit={u.limit} />
            ))}
          </div>
        </Panel>
      )}

      {state && (
        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <Eyebrow>PLANS</Eyebrow>
            <div className="flex gap-2" role="group" aria-label="Billing interval">
              {(["month", "year"] as const).map((i) => (
                <button
                  key={i}
                  type="button"
                  aria-pressed={interval === i}
                  onClick={() => setInterval(i)}
                  className={
                    interval === i
                      ? "rounded-full bg-ink px-[14px] py-2 text-[13px] font-bold leading-4 text-white"
                      : "rounded-full border border-rule bg-white px-[14px] py-2 text-[13px] font-bold leading-4 text-body hover:text-ink"
                  }
                >
                  {i === "month" ? "Monthly" : "Yearly"}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {plans.map((p) => (
              <PlanCard
                key={p.key}
                plan={p}
                current={state}
                interval={interval}
                busy={busy === `plan-${p.key}`}
                onChoose={() =>
                  run(`plan-${p.key}`, async () => {
                    const r = await api.startCheckout(p.key, interval);
                    window.location.assign(r.checkout_url);
                  })
                }
              />
            ))}
          </div>
          {state.pending_checkout?.checkout_url && (
            <p className="text-[13px] leading-5 text-soft">
              A checkout is waiting.{" "}
              <a className="font-bold text-accent-text" href={state.pending_checkout.checkout_url}>
                Resume payment
              </a>
            </p>
          )}
        </section>
      )}

      <section className="flex flex-col gap-3">
        <Eyebrow>GST DETAILS ON INVOICES</Eyebrow>
        <Panel className="p-5">
          <form
            className="grid gap-4 sm:grid-cols-2"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              void run("profile", async () => {
                const saved = await api.saveProfile({
                  legal_name: profile.legal_name || null,
                  gstin: profile.gstin || null,
                  state_code: profile.state_code || null,
                  address: profile.address || null,
                });
                setProfile({
                  legal_name: saved.legal_name ?? "",
                  gstin: saved.gstin ?? "",
                  state_code: saved.state_code ?? "",
                  address: saved.address ?? "",
                });
                setNotice("Invoice details saved.");
              });
            }}
          >
            <label className="flex flex-col gap-1 text-[13px] font-bold leading-4 text-body">
              Legal name
              <input
                className={FIELD}
                value={profile.legal_name ?? ""}
                onChange={(e) => setProfile({ ...profile, legal_name: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1 text-[13px] font-bold leading-4 text-body">
              GSTIN
              <input
                className={FIELD}
                maxLength={15}
                value={profile.gstin ?? ""}
                onChange={(e) => setProfile({ ...profile, gstin: e.target.value.toUpperCase() })}
              />
            </label>
            <label className="flex flex-col gap-1 text-[13px] font-bold leading-4 text-body">
              GST state code
              <input
                className={FIELD}
                maxLength={2}
                inputMode="numeric"
                placeholder="Taken from the GSTIN if empty"
                value={profile.state_code ?? ""}
                onChange={(e) => setProfile({ ...profile, state_code: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1 text-[13px] font-bold leading-4 text-body sm:col-span-2">
              Address
              <textarea
                className={FIELD}
                rows={2}
                value={profile.address ?? ""}
                onChange={(e) => setProfile({ ...profile, address: e.target.value })}
              />
            </label>
            <div className="sm:col-span-2">
              <Btn variant="primary" type="submit" disabled={busy === "profile"}>
                Save details
              </Btn>
            </div>
          </form>
        </Panel>
      </section>

      <section className="flex flex-col gap-3">
        <Eyebrow>INVOICES</Eyebrow>
        <Panel className="overflow-hidden">
          {invoices.length === 0 ? (
            <div className="p-5 text-[14px] leading-5 text-soft">Invoices appear here after your first payment.</div>
          ) : (
            invoices.map((i) => (
              <div key={i.id} className="flex flex-wrap items-center gap-3 border-b border-rule px-5 py-3 last:border-b-0">
                <span className="w-[150px] text-[14px] font-bold text-ink">{i.number}</span>
                <span className="grow text-[14px] text-body">{fmtDate(i.issued_at)}</span>
                <span className="text-[14px] font-bold text-ink">Rs {api.rupees(i.total_paise)}</span>
                <Btn
                  variant="outline"
                  disabled={busy === `inv-${i.id}`}
                  onClick={() =>
                    run(`inv-${i.id}`, async () => {
                      const r = await api.invoiceDownload(i.id);
                      window.open(r.download_url, "_blank", "noopener");
                    })
                  }
                >
                  Download PDF
                </Btn>
              </div>
            ))
          )}
        </Panel>
      </section>
    </div>
  );
}
