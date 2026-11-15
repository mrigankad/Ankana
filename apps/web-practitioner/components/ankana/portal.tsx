"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/auth-provider";
import { LanguageMenuItems } from "@/components/language-switcher";
import { Banner, Progress } from "@/components/ui/data";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, Dialog, DialogContent, DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useToast } from "@/components/ui/toast";
import { Chip } from "@/components/ankana/ui";
import { SampleBadge } from "@/components/ankana/server-unavailable";
import { isFixtures } from "@/lib/api/client";
import * as portal from "@/lib/api/portal";
import type { Consent, ConsentReceipt, PortalSummary, RemedyPlan } from "@/lib/api/portal";
import { problemMessage } from "@/lib/api/v1";
import { signOut } from "@/lib/auth/session";
import { useT } from "@/lib/i18n/provider";

const CARD = "rounded-[10px] border border-rule bg-white p-5 shadow-[0_1px_2px_rgba(34,30,29,0.04),0_6px_18px_rgba(34,30,29,0.05)]";
const dateFmt = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
const longDate = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const timeFmt = (iso: string) => new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
const mb = (n: number | null) => (!n ? "" : n < 1_048_576 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1_048_576).toFixed(1)} MB`);

/** The portal ships its own chrome: a client never sees the practitioner shell. */
export function Portal() {
  const t = useT();
  const toast = useToast();
  const router = useRouter();
  const { session } = useAuth();
  const [summary, setSummary] = useState<PortalSummary | null>(null);
  const [plan, setPlan] = useState<RemedyPlan | null>(null);
  const [consents, setConsents] = useState<Consent[]>([]);
  const [receipts, setReceipts] = useState<ConsentReceipt[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState<string | null>(null);
  const [withdraw, setWithdraw] = useState<string | null>(null);
  const [receiptFor, setReceiptFor] = useState<string | null>(null);
  const [exportState, setExportState] = useState<"idle" | "working" | "ready" | "failed">("idle");
  const [exportUrl, setExportUrl] = useState<string | null>(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    try {
      const s = await portal.getSummary();
      setSummary(s);
      const [p, c, r] = await Promise.all([
        portal.getActivePlan(s.client_id),
        portal.getConsents(s.client_id),
        portal.getReceipts(s.client_id),
      ]);
      setPlan(p);
      setConsents(c.consents);
      setReceipts(r);
      setError(null);
    } catch (e) {
      setError(problemMessage(e, t("Your page could not be loaded. Try again in a moment.")));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function markDone(itemId: string) {
    if (!plan) return;
    setChecking(itemId);
    try {
      await portal.checkIn(plan.id, itemId);
      isFixtures() ? toast(t("Sample mode: changes are not saved")) : toast(t("Marked as done. Well done."), { tone: "success" });
      setPlan(await portal.getActivePlan(summary!.client_id));
    } catch (e) {
      toast(problemMessage(e, t("That could not be saved. Try again.")), { tone: "error" });
    } finally {
      setChecking(null);
    }
  }

  async function doWithdraw(purpose: string) {
    if (!summary) return;
    try {
      await portal.withdrawConsent(summary.client_id, purpose);
      isFixtures() ? toast(t("Sample mode: changes are not saved")) : toast(t("Consent withdrawn"), { tone: "success" });
    } catch (e) {
      toast(problemMessage(e, t("That could not be withdrawn.")), { tone: "error" });
    }
    await load();
  }

  async function askExport() {
    if (!summary) return;
    if (isFixtures()) {
      toast(t("Sample mode: changes are not saved"));
      return;
    }
    setExportState("working");
    try {
      let req = await portal.requestExport(summary.client_id);
      for (let i = 0; i < 40 && alive.current && req.status !== "done" && req.status !== "failed"; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        req = await portal.getPrivacyRequest(req.id);
      }
      if (req.status === "done") {
        setExportUrl(req.download_url);
        setExportState("ready");
      } else {
        setExportState(req.status === "failed" ? "failed" : "working");
      }
    } catch (e) {
      setExportState("failed");
      toast(problemMessage(e, t("The export could not be requested.")), { tone: "error" });
    }
  }

  // Latest consent row per purpose.
  const byPurpose = new Map<string, Consent>();
  for (const c of consents) if (!byPurpose.has(c.purpose)) byPurpose.set(c.purpose, c);
  const rows = [...byPurpose.values()];
  const doneDays = plan ? Math.max(0, ...plan.items.map((i) => i.done_days)) : 0;
  const ap = summary?.next_appointment ?? null;
  const first = (summary?.display_name ?? session.user?.name ?? "").split(" ")[0];
  const initials = (summary?.display_name ?? "?").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  const receiptList = receipts.filter((r) => r.consent_id && consents.find((c) => c.id === r.consent_id)?.purpose === receiptFor);

  return (
    <div className="min-h-svh bg-wash-soft text-ink">
      <header className="flex h-14 items-center justify-between border-b border-rule bg-white px-4">
        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate text-[18px] font-bold leading-[22px]">{summary?.practice_name ?? "Ankana"}</span>
          {isFixtures() ? <SampleBadge /> : null}
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label={t("Account menu")}
            className="flex size-8 items-center justify-center rounded-full bg-ink text-[12px] font-bold text-white"
          >
            {initials}
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-[200px]">
            <LanguageMenuItems />
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={async () => {
                await signOut();
                router.replace("/sign-in");
              }}
            >
              {t("Sign out")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      <main className="mx-auto flex max-w-[520px] flex-col gap-6 px-4 pb-8 pt-6">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 text-[30px] font-bold leading-9 tracking-[-0.01em]">{first ? t("Namaste, {name}", { name: first }) : t("Namaste")}</h1>
          <p className="m-0 text-[16px] leading-[22px] text-body">{t("Everything from your consultations, in one quiet place.")}</p>
        </div>

        {error ? <Banner tone="error">{error}</Banner> : null}

        <section
          aria-label={t("Your next consultation")}
          className="flex flex-col gap-[10px] rounded-[10px] p-5 text-white shadow-[0_8px_24px_rgba(34,30,29,0.2)]"
          style={{ backgroundColor: "var(--accent)" }}
        >
          <span className="text-[12px] font-bold leading-4 tracking-[0.06em] text-on-dark-muted">{t("YOUR NEXT CONSULTATION")}</span>
          {ap ? (
            <>
              <span className="text-[24px] font-bold leading-[30px]">
                {ap.at ? `${longDate(ap.at)}, ${timeFmt(ap.at)}` : longDate(ap.date!)}
              </span>
              <span className="text-[15px] leading-5 text-on-dark-body">
                {ap.kind === "follow_up" ? t("Your follow-up is due. Your astrologer will confirm the time.") : ""}
                {ap.topic ? ` ${t("Topic: {topic}.", { topic: ap.topic })}` : ""}
              </span>
            </>
          ) : (
            <span className="text-[16px] leading-[22px] text-on-dark-body">
              {t("Nothing is booked yet. Your astrologer will send an invitation when the next one is set.")}
            </span>
          )}
        </section>

        <section aria-label={t("Your remedy plan")} className={`flex flex-col gap-4 ${CARD}`}>
          <div className="flex flex-col gap-1">
            <span className="text-[12px] font-bold leading-4 tracking-[0.06em] text-soft">{t("YOUR REMEDY PLAN")}</span>
            <h2 className="m-0 text-[20px] font-bold leading-[26px]">{plan ? plan.title : t("No remedy plan right now")}</h2>
          </div>
          {plan ? (
            <>
              <div className="flex flex-col gap-2">
                <div className="flex justify-between text-[14px] leading-[18px]">
                  <span className="text-body">
                    {t("Day {n} of {total}", { n: plan.day_number ?? 1, total: plan.cycle_days })}
                  </span>
                  <span className="font-bold">{t("{n} done", { n: doneDays })}</span>
                </div>
                <Progress
                  value={(doneDays / plan.cycle_days) * 100}
                  aria-label={t("{total} day progress", { total: plan.cycle_days })}
                  className="h-2"
                />
              </div>
              {plan.items.map((item) => (
                <div key={item.id} className="flex flex-col gap-3">
                  <div className="flex flex-col gap-[2px] rounded-[8px] border border-rule bg-wash-soft p-[14px]">
                    <span className="text-[15px] font-bold leading-5">{item.title}</span>
                    {item.instructions ? <span className="text-[14px] leading-[18px] text-body">{item.instructions}</span> : null}
                  </div>
                  {item.done_today ? (
                    <div className="flex h-[52px] items-center justify-center rounded-[8px] bg-ok-wash text-[16px] font-bold text-ok" role="status">
                      {t("Done for today")}
                    </div>
                  ) : (
                    <Button
                      size="md"
                      className="h-[52px] w-full text-[16px]"
                      loading={checking === item.id}
                      onClick={() => void markDone(item.id)}
                    >
                      {t("Mark today as done")}
                    </Button>
                  )}
                </div>
              ))}
              <p className="m-0 text-center text-[13px] leading-[18px] text-soft">{t("Missed a day? That is fine. Pick up where you left off.")}</p>
            </>
          ) : (
            <p className="m-0 text-[14px] leading-5 text-body">{t("When your astrologer starts a plan for you, your daily check-in appears here.")}</p>
          )}
        </section>

        <section aria-label={t("Your reports")} className="flex flex-col gap-3">
          <h2 className="m-0 text-[20px] font-bold leading-[26px]">{t("Your reports")}</h2>
          {summary && summary.reports.length === 0 ? (
            <p className="m-0 text-[14px] leading-5 text-body">{t("No reports have been shared with you yet.")}</p>
          ) : null}
          {(summary?.reports ?? []).map((r) => (
            <div key={r.id} className="flex items-center justify-between gap-3 rounded-[10px] border border-rule bg-white px-4 py-[14px]">
              <div className="flex min-w-0 flex-col">
                <span className="truncate text-[15px] font-bold leading-5">{t("Kundali report")}</span>
                <span className="text-[13px] leading-4 text-soft">
                  {dateFmt(r.created_at)}, {r.language === "hi" ? t("Hindi") : t("English")}
                  {r.size_bytes ? `, ${mb(r.size_bytes)}` : ""}
                </span>
              </div>
              {r.download_url ? (
                <Button asChild variant="outline" size="md" className="h-9 shrink-0 px-[14px] no-underline">
                  <a href={r.download_url} download>
                    {t("Download")}
                  </a>
                </Button>
              ) : null}
            </div>
          ))}
        </section>

        <section aria-label={t("Your consents")} className="flex flex-col gap-3">
          <div className="flex flex-col gap-[2px]">
            <h2 className="m-0 text-[20px] font-bold leading-[26px]">{t("Your consents")}</h2>
            <p className="m-0 text-[14px] leading-5 text-body">{t("You decide how your details are used. Withdraw any time.")}</p>
          </div>
          {rows.length === 0 ? <p className="m-0 text-[14px] leading-5 text-body">{t("You have not given any consent yet.")}</p> : null}
          {rows.map((c) => {
            const given = c.withdrawn_at === null;
            const rec = receipts.filter((r) => r.consent_id === c.id).at(-1);
            return (
              <div key={c.id} className="flex flex-col gap-[10px] rounded-[10px] border border-rule bg-white p-4">
                <div className="flex items-center justify-between">
                  <span className="text-[15px] font-bold leading-5">{t(portal.PURPOSE_LABEL[c.purpose] ?? c.purpose)}</span>
                  <Chip tone={given ? "ok" : "muted"}>{given ? t("Given") : t("Withdrawn")}</Chip>
                </div>
                <span className="text-[13px] leading-[18px] text-soft">
                  {given
                    ? t("Given on {date}", { date: dateFmt(c.granted_at) })
                    : t("Withdrawn on {date}", { date: dateFmt(c.withdrawn_at!) })}
                  {rec ? `. ${t("Receipt")} ${rec.receipt_hash.slice(0, 4).toUpperCase()}-${rec.receipt_hash.slice(4, 8).toUpperCase()}` : ""}
                </span>
                <div className="flex gap-4">
                  <Button variant="link" size="sm" className="h-auto p-0 text-[14px] font-bold text-accent-text" onClick={() => setReceiptFor(c.purpose)}>
                    {t("View receipt")}
                  </Button>
                  {given ? (
                    <Button variant="link" size="sm" className="h-auto p-0 text-[14px] font-bold text-alert" onClick={() => setWithdraw(c.purpose)}>
                      {t("Withdraw")}
                    </Button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </section>

        <section aria-label={t("Your data")} className="flex flex-col gap-3 rounded-[10px] bg-wash p-5">
          <h2 className="m-0 text-[18px] font-bold leading-6">{t("Your data, your copy")}</h2>
          <p className="m-0 text-[14px] leading-5 text-body">{t("Ask for everything held about you. We prepare a ZIP and it appears here when it is ready.")}</p>
          {exportState === "ready" && exportUrl ? (
            <Button asChild size="md" className="h-12 w-full no-underline">
              <a href={exportUrl} download>
                {t("Download my data")}
              </a>
            </Button>
          ) : (
            <Button variant="outline" size="md" className="h-12 w-full bg-white" loading={exportState === "working"} onClick={() => void askExport()}>
              {exportState === "working" ? t("Preparing your export") : t("Request my data export")}
            </Button>
          )}
          {exportState === "failed" ? <Banner tone="error">{t("The export did not finish. Try again in a little while.")}</Banner> : null}
        </section>

        <p className="m-0 px-2 pt-2 text-center text-[13px] leading-[18px] text-soft">
          {t("Ankana · Guidance is advisory. It does not replace medical, legal or financial advice.")}
        </p>
      </main>

      <ConfirmDialog
        open={!!withdraw}
        onOpenChange={(o) => !o && setWithdraw(null)}
        tone="danger"
        title={t("Withdraw this consent?")}
        description={t("Your astrologer will stop using your details for this. You can give consent again later.")}
        confirmLabel={t("Withdraw")}
        cancelLabel={t("Keep")}
        onConfirm={async () => {
          if (withdraw) await doWithdraw(withdraw);
        }}
      />

      <Dialog open={!!receiptFor} onOpenChange={(o) => !o && setReceiptFor(null)}>
        <DialogContent>
          <DialogTitle>{t("Consent receipt")}</DialogTitle>
          <DialogDescription>{t(portal.PURPOSE_LABEL[receiptFor ?? ""] ?? "")}</DialogDescription>
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {receiptList.map((r) => (
              <li key={r.id} className="flex flex-col gap-1 rounded-[6px] border border-rule p-3 text-[13px] leading-[18px] text-body">
                <span className="font-bold text-ink">
                  {r.event === "granted" ? t("Given") : t("Withdrawn")} · {new Date(r.occurred_at).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false })}
                </span>
                <span>{t("Notice version {v}", { v: r.notice_version })}</span>
                <span className="break-all text-soft">{r.receipt_hash}</span>
                <span>{r.verified ? t("Signature checked") : t("Signature could not be checked")}</span>
              </li>
            ))}
          </ul>
          <DialogFooter>
            <Button variant="outline" size="md" onClick={() => setReceiptFor(null)}>
              {t("Close")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
