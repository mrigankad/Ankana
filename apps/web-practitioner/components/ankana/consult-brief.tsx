"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { Panel } from "@/components/ankana/ui";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/data";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { consultApi, onConsultChanged, type BriefTransit, type BriefV1 } from "@/lib/api/consult";
import { problemMessage } from "@/lib/api/v1";
import { useLanguage, useT } from "@/lib/i18n/provider";
import { tName } from "@/lib/i18n/translate";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function useDateFmt() {
  const { lang } = useLanguage();
  const loc = lang === "hi" ? "hi-IN" : "en-GB";
  return {
    day: (iso: string) => new Intl.DateTimeFormat(loc, { day: "numeric", month: "short", year: "numeric" }).format(new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)),
    short: (iso: string) => new Intl.DateTimeFormat(loc, { day: "numeric", month: "short" }).format(new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)),
    month: (iso: string) => new Intl.DateTimeFormat(loc, { month: "short", year: "numeric" }).format(new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)),
  };
}

function Block({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  const t = useT();
  return (
    <section className={`flex min-w-0 flex-col gap-2 ${className}`}>
      <h3 className="m-0 text-[12px] font-bold uppercase leading-4 tracking-[0.06em] text-soft">{t(title)}</h3>
      {children}
    </section>
  );
}

function Pill({ tone, children }: { tone: "alert" | "ok" | "accent" | "muted"; children: ReactNode }) {
  const tones = { alert: "bg-alert-wash text-alert", ok: "bg-ok-wash text-ok", accent: "bg-accent-wash text-accent-text", muted: "bg-chip text-body" };
  return <span className={`inline-flex shrink-0 items-center rounded-[4px] px-2 py-[2px] text-[12px] font-bold leading-4 ${tones[tone]}`}>{children}</span>;
}

export function transitText(t: ReturnType<typeof useT>, e: BriefTransit): string {
  const planet = tName(t, cap(e.planet));
  const sign = tName(t, cap(e.sign));
  switch (e.kind) {
    case "ingress":
      return t("{planet} enters {sign}", { planet, sign });
    case "retrograde-station":
      return t("{planet} stations retrograde in {sign}", { planet, sign });
    case "direct-station":
      return t("{planet} stations direct in {sign}", { planet, sign });
    case "conjunction":
      return t("{planet} joins the natal {target}", { planet, target: t(e.target === "lagna" ? "lagna" : "Moon") });
    case "aspect":
      return t("{planet} aspects the natal {target}", { planet, target: t(e.target === "lagna" ? "lagna" : "Moon") });
    default:
      return t("Sade sati: {phase}", { phase: t(e.phase ?? "ends") });
  }
}

/** The pre-consult brief: everything to read before the client sits down. */
export function ClientBrief({ clientId, consultationId, embedded = false }: { clientId: string; consultationId?: string; embedded?: boolean }) {
  const t = useT();
  const f = useDateFmt();
  const [b, setB] = useState<BriefV1 | null>(null);
  const [error, setError] = useState("");
  const [rev, setRev] = useState(0);
  useEffect(() => onConsultChanged(() => setRev((n) => n + 1)), []);
  useEffect(() => {
    let live = true;
    setError("");
    consultApi.getBrief(clientId, consultationId).then((r) => live && setB(r)).catch((e) => live && setError(problemMessage(e)));
    return () => {
      live = false;
    };
  }, [clientId, consultationId, rev]);

  if (error) return embedded ? <p className="m-0 text-[14px] leading-5 text-body">{t("The brief could not be loaded.")}</p> : null; // assistants cannot open clinical data
  if (!b)
    return (
      <Panel className="flex flex-col gap-3 p-5" aria-busy>
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-24 w-full" />
      </Panel>
    );

  const noChart = !b.chart_id;
  const body = (
    <div className="flex flex-col gap-5">
      {b.stated_question ? (
        <div className="flex flex-col gap-1 rounded-[6px] bg-accent-wash px-4 py-3">
          <span className="text-[12px] font-bold uppercase leading-4 tracking-[0.06em] text-accent-text">{t("The client asks")}</span>
          <p className="m-0 text-[16px] font-semibold leading-6 text-ink">{b.stated_question}</p>
        </div>
      ) : null}

      <div className={`grid gap-x-8 gap-y-5 ${embedded ? "" : "md:grid-cols-2"}`}>
        <Block title="Running period">
          {b.dasha ? (
            <div className="flex flex-col gap-[2px]">
              <div className="text-[17px] font-bold leading-6 text-ink">
                {tName(t, cap(b.dasha.maha))}
                {b.dasha.antar ? ` / ${tName(t, cap(b.dasha.antar))}` : ""}
              </div>
              <div className="text-[13px] leading-4 text-body">
                {b.dasha.antar && b.dasha.antar_ends ? t("Sub-period ends {date}", { date: f.day(b.dasha.antar_ends) }) : null}
                {b.dasha.antar && b.dasha.antar_ends ? " · " : ""}
                {t("Main period ends {date}", { date: f.month(b.dasha.maha_ends) })}
              </div>
            </div>
          ) : (
            <p className="m-0 text-[14px] leading-5 text-body">{noChart ? t("No chart yet. Add birth details to see the period.") : t("Not available")}</p>
          )}
          {b.sade_sati ? (
            <div className="flex flex-wrap items-center gap-2 text-[14px] leading-5 text-ink">
              <span className="font-bold">{t("Sade sati")}</span>
              {b.sade_sati.active ? <Pill tone="alert">{t(b.sade_sati.phase ? cap(b.sade_sati.phase) : "Active")}</Pill> : <Pill tone="muted">{t("Not active")}</Pill>}
              {b.sade_sati.active && b.sade_sati.ends_at ? <span className="text-[13px] text-body">{t("until {date}", { date: f.month(b.sade_sati.ends_at) })}</span> : null}
            </div>
          ) : null}
        </Block>

        <Block title="Next notable transits">
          {b.transits.length ? (
            <ul className="m-0 flex list-none flex-col gap-[6px] p-0">
              {b.transits.map((e) => (
                <li key={`${e.date}-${e.planet}-${e.kind}`} className="flex items-baseline gap-3 text-[14px] leading-5">
                  <span className="w-[52px] shrink-0 text-soft">{f.short(e.date)}</span>
                  <span className="min-w-0 text-ink">
                    <span className="font-bold">{transitText(t, e)}</span>
                    <span className="text-body"> {t("house {n} from the Moon", { n: e.house_from_moon })}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-[14px] leading-5 text-body">{noChart ? t("Needs a chart.") : t("Nothing notable in the next six months.")}</p>
          )}
        </Block>

        <Block title="Remedies in progress">
          {b.remedies.length ? (
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {b.remedies.map((r) => (
                <li key={r.plan_id} className="flex flex-col gap-1">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="min-w-0 truncate text-[14px] font-bold leading-5 text-ink">{r.title}</span>
                    <span className="shrink-0 text-[13px] leading-4 text-body">
                      {r.status === "draft" ? t("Draft") : t("Day {day} of {total}", { day: Math.min(r.day_number ?? 0, r.cycle_days), total: r.cycle_days })}
                    </span>
                  </div>
                  {r.adherence_pct !== null ? (
                    <div className="flex items-center gap-2">
                      <Progress value={r.adherence_pct} className="h-[6px] grow" aria-label={t("Check-ins done")} />
                      <span className="w-[88px] shrink-0 text-right text-[12px] leading-4 text-body">{t("{n}% checked in", { n: r.adherence_pct })}</span>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-[14px] leading-5 text-body">{t("No remedies running.")}</p>
          )}
        </Block>

        <Block title="Last consultation">
          {b.last_consultation ? (
            <div className="flex flex-col gap-1">
              <div className="text-[14px] font-bold leading-5 text-ink">
                {f.day(b.last_consultation.at)}
                {b.last_consultation.topic ? <span className="font-normal text-body">{` · ${b.last_consultation.topic}`}</span> : null}
              </div>
              {b.last_consultation.excerpt ? <p className="m-0 text-[14px] leading-5 text-body">{b.last_consultation.excerpt}</p> : null}
            </div>
          ) : (
            <p className="m-0 text-[14px] leading-5 text-body">{t("This is the first visit.")}</p>
          )}
        </Block>

        <Block title="Open follow-ups">
          {b.follow_ups.length ? (
            <ul className="m-0 flex list-none flex-col gap-[6px] p-0">
              {b.follow_ups.map((u) => (
                <li key={u.consultation_id} className="flex items-center gap-2 text-[14px] leading-5 text-ink">
                  <span className="font-bold">{f.day(u.date)}</span>
                  {u.overdue ? <Pill tone="alert">{t("Overdue")}</Pill> : <Pill tone="accent">{t("Upcoming")}</Pill>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-[14px] leading-5 text-body">{t("None open.")}</p>
          )}
        </Block>

        <Block title="Predictions awaiting an outcome">
          {b.open_predictions.length ? (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {b.open_predictions.slice(0, 3).map((p) => (
                <li key={p.id} className="flex flex-col gap-[2px] text-[14px] leading-5">
                  <span className="text-ink">{p.statement}</span>
                  <span className="flex flex-wrap items-center gap-2 text-[13px] leading-4 text-body">
                    {p.window_end ? t("by {date}", { date: f.day(p.window_end) }) : t("No window set")}
                    {p.due ? <Pill tone="alert">{t("Window ended")}</Pill> : null}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-[14px] leading-5 text-body">{t("None waiting.")}</p>
          )}
        </Block>
      </div>
    </div>
  );

  if (embedded) return body;
  return (
    <Panel className="flex flex-col gap-4 p-5" aria-label={t("Pre-consult brief")}>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">{t("Pre-consult brief")}</h2>
        <span className="text-[13px] leading-4 text-soft">{t("Read before the visit")}</span>
      </div>
      {body}
    </Panel>
  );
}

/** The same brief in a side sheet, opened from a Today tile. */
export function BriefSheet({ open, onOpenChange, clientId, consultationId, name }: { open: boolean; onOpenChange: (o: boolean) => void; clientId: string; consultationId?: string; name: string }) {
  const t = useT();
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[min(100vw,520px)] max-w-[520px] gap-0 overflow-y-auto p-0 sm:max-w-[520px]">
        <SheetHeader className="border-b border-rule p-5">
          <SheetTitle className="text-[20px] font-bold leading-6 text-ink">{t("Brief for {name}", { name })}</SheetTitle>
          <SheetDescription className="text-[14px] leading-5 text-body">{t("What to know before the visit.")}</SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-4 p-5">
          {open ? <ClientBrief clientId={clientId} consultationId={consultationId} embedded /> : null}
          <Link href={`/clients/${clientId}`} className="text-[14px] font-bold leading-5 text-accent-text no-underline hover:underline">
            {t("Open the client page")}
          </Link>
        </div>
      </SheetContent>
    </Sheet>
  );
}
