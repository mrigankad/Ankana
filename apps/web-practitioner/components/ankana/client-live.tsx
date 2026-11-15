"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";

import { Btn, Chip, Panel } from "@/components/ankana/ui";
import { CONSENT_NOTICE_TEXT, CONSENT_NOTICE_VERSION } from "@/lib/api/intake-flow";
import { v1Api, type ConsentPurpose, type ConsentV1, type RemedyPlanV1 } from "@/lib/api/live";
import { problemMessage } from "@/lib/api/v1";
import { useT } from "@/lib/i18n/provider";

const PURPOSES: Array<{ id: ConsentPurpose; label: string; note: string }> = [
  { id: "chart_compute", label: "Chart calculation", note: "Needed before any chart is generated." },
  { id: "ai_assistant", label: "AI assistant", note: "Lets the Ask panel read this client's chart." },
  { id: "report_sharing", label: "Report sharing", note: "Lets you send reports and share links." },
];

function ErrorLine({ children }: { children: ReactNode }) {
  return children ? (
    <p role="alert" className="m-0 rounded-[6px] bg-alert-wash px-3 py-2 text-[13px] font-bold leading-[18px] text-alert">
      {children}
    </p>
  ) : null;
}

function Head({ title, note }: { title: string; note?: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">{title}</h2>
      {note ? <span className="text-[13px] leading-4 text-soft">{note}</span> : null}
    </div>
  );
}

const INPUT = "h-[40px] w-full rounded-[6px] border border-rule bg-white px-3 text-[14px] leading-5 text-ink outline-none placeholder:text-soft focus:border-sindoor";

/* ----------------------------------------------------------------- consents */
function Consents({ clientId }: { clientId: string }) {
  const [state, setState] = useState<{ active: Record<string, boolean>; consents: ConsentV1[] } | null>(null);
  const [error, setError] = useState("");
  const reload = useCallback(() => v1Api.getConsents(clientId).then(setState).catch((e) => setError(problemMessage(e))), [clientId]);
  useEffect(() => void reload(), [reload]);

  async function toggle(p: ConsentPurpose, on: boolean) {
    setError("");
    try {
      if (on) await v1Api.withdrawConsent(clientId, p);
      else
        await v1Api.recordConsent(clientId, {
          purpose: p,
          notice_version: CONSENT_NOTICE_VERSION,
          notice_text: CONSENT_NOTICE_TEXT,
          notice_language: "en",
          channel: "in_person",
        });
      await reload();
    } catch (e) {
      setError(problemMessage(e));
    }
  }

  return (
    <section className="flex flex-col gap-3" aria-label="Consents">
      <Head title="Consents" />
      <ErrorLine>{error}</ErrorLine>
      <Panel className="flex flex-col">
        {PURPOSES.map((p, i) => {
          const on = Boolean(state?.active[p.id]);
          const latest = state?.consents.find((c) => c.purpose === p.id && !c.withdrawn_at);
          return (
            <div key={p.id} className={`flex items-center gap-3 px-4 py-3 ${i === PURPOSES.length - 1 ? "" : "border-b border-rule"}`}>
              <div className="flex grow flex-col">
                <div className="text-[14px] font-bold leading-[18px] text-ink">{p.label}</div>
                <div className="text-[12px] leading-4 text-soft">{on && latest ? `Given ${new Date(latest.granted_at).toLocaleDateString("en-GB")}, notice ${latest.notice_version}` : p.note}</div>
              </div>
              <Chip tone={on ? "ok" : "muted"}>{on ? "Given" : "Not given"}</Chip>
              <Btn variant="outline" className="py-[6px]" onClick={() => void toggle(p.id, on)} disabled={!state}>
                {on ? "Withdraw" : "Record"}
              </Btn>
            </div>
          );
        })}
      </Panel>
    </section>
  );
}

/* ------------------------------------------------------------ remedy plans */
function Plans({ clientId }: { clientId: string }) {
  const [plans, setPlans] = useState<RemedyPlanV1[] | null>(null);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [item, setItem] = useState("");

  const reload = useCallback(() => v1Api.listRemedyPlans(clientId).then(setPlans).catch((e) => setError(problemMessage(e))), [clientId]);
  useEffect(() => void reload(), [reload]);

  const run = async (fn: () => Promise<unknown>) => {
    setError("");
    try {
      await fn();
      await reload();
    } catch (e) {
      setError(problemMessage(e));
    }
  };

  return (
    <section className="flex flex-col gap-3" aria-label="Remedy plans">
      <Head title="Remedy plans" note={plans ? `${plans.filter((p) => p.status === "active").length} active` : ""} />
      <ErrorLine>{error}</ErrorLine>
      <Panel className="flex flex-col gap-2 p-4">
        <input aria-label="Plan title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Plan title, for example Saturn, 43 days" className={INPUT} />
        <input aria-label="First practice" value={item} onChange={(e) => setItem(e.target.value)} placeholder="First practice, for example Lamp at a peepal, Saturdays" className={INPUT} />
        <div className="flex justify-end">
          <Btn
            disabled={!title.trim()}
            onClick={() =>
              void run(async () => {
                await v1Api.createRemedyPlan(clientId, { title: title.trim(), cycle_days: 43, items: item.trim() ? [{ title: item.trim() }] : [] });
                setTitle("");
                setItem("");
              })
            }
          >
            Create plan
          </Btn>
        </div>
      </Panel>
      {plans?.map((p) => (
        <Panel key={p.id} className="flex flex-col gap-2 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="text-[15px] font-bold leading-[18px] text-ink">{p.title}</div>
            <Chip tone={p.status === "active" ? "ok" : p.status === "draft" ? "accent" : "muted"}>{p.status}</Chip>
          </div>
          {p.status !== "draft" && p.day_number ? (
            <div className="text-[13px] leading-4 text-soft">
              Day {Math.min(p.day_number, p.cycle_days)} of {p.cycle_days}
            </div>
          ) : null}
          {p.items.map((it) => (
            <div key={it.id} className="flex items-center justify-between gap-3 text-[14px] leading-5 text-body">
              <span>
                {it.title} <span className="text-soft">({it.done_days} days done)</span>
              </span>
              {p.status === "active" ? (
                <Btn variant="outline" className="py-[5px]" onClick={() => void run(() => v1Api.checkinRemedyItem(p.id, it.id, { done: true }))}>
                  Check in today
                </Btn>
              ) : null}
            </div>
          ))}
          <div className="flex gap-2">
            {p.status === "draft" ? <Btn onClick={() => void run(() => v1Api.startRemedyPlan(p.id))}>Start plan</Btn> : null}
            {p.status === "active" ? (
              <Btn variant="outline" onClick={() => void run(() => v1Api.completeRemedyPlan(p.id))}>
                Mark complete
              </Btn>
            ) : null}
            {p.status === "draft" || p.status === "active" ? (
              <button type="button" className="text-[13px] font-bold leading-4 text-alert" onClick={() => void run(() => v1Api.cancelRemedyPlan(p.id))}>
                Cancel plan
              </button>
            ) : null}
          </div>
        </Panel>
      ))}
    </section>
  );
}

/** Live-only sections of the Client screen: consents and remedy plans. Consultation notes live in consult-notes.tsx. */
export function ClientLivePanels({ clientId }: { clientId: string; chartId?: string | null }) {
  return (
    <div className="grid gap-7 lg:grid-cols-2">
      <Consents clientId={clientId} />
      <Plans clientId={clientId} />
    </div>
  );
}
