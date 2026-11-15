"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { RemindersPanel } from "@/components/ankana/reminders-panel";
import { MiniKundali } from "@/components/ankana/mini-kundali";
import { Topbar } from "@/components/ankana/topbar";
import { Btn, Chip, Panel } from "@/components/ankana/ui";
import { ClientFormDialog } from "@/components/ankana/client-form-dialog";
import { ClientLivePanels } from "@/components/ankana/client-live";
import { ClientTags } from "@/components/ankana/client-tags";
import { ClientBrief } from "@/components/ankana/consult-brief";
import { ConsultationNotesSection, PredictionsSection } from "@/components/ankana/consult-notes";
import { ClientTimeline } from "@/components/ankana/client-timeline";
import { api, isFixtures } from "@/lib/api/client";
import { v1Api, type ClientV1 } from "@/lib/api/live";
import type { ClientDetail, ClientDetailChart } from "@/lib/api/types";
import { useT } from "@/lib/i18n/provider";

function SectionHead({ title, action, note }: { title: string; action?: string; note?: string }) {
  const t = useT();
  return (
    <div className="flex items-baseline justify-between">
      <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">{t(title)}</h2>
      {action ? <span className="text-[14px] font-bold leading-[18px] text-accent-text">{t(action)}</span> : null}
      {note ? <span className="text-[13px] leading-4 text-soft">{note}</span> : null}
    </div>
  );
}

function ChartTile({ c, chartHref }: { c: ClientDetailChart; chartHref: string | null }) {
  const t = useT();
  const art =
    c.kind === "d1" ? (
      <div className="flex h-[112px] items-center justify-center" style={{ backgroundColor: "var(--surface)", backgroundImage: "linear-gradient(180deg, var(--surface) 0%, #FFFFFF 100%)" }}>
        <MiniKundali houses={c.miniHouses ?? {}} wash="var(--accent-tint)" />
      </div>
    ) : c.kind === "match" ? (
      <div className="flex h-[112px] items-center justify-center gap-2 bg-sidebar-wash">
        <svg width="64" height="64" viewBox="0 0 56 56" aria-hidden className="shrink-0">
          <rect x="1" y="1" width="54" height="54" fill="var(--bg)" stroke="var(--text-primary)" strokeWidth="1.2" />
          <path d="M1 1L55 55M55 1L1 55M28 1L55 28L28 55L1 28Z" fill="none" stroke="var(--text-primary)" strokeWidth="1.2" />
        </svg>
        <svg width="64" height="64" viewBox="0 0 56 56" aria-hidden className="shrink-0">
          <rect x="1" y="1" width="54" height="54" fill="var(--bg)" stroke="var(--text-soft)" strokeWidth="1.2" />
          <path d="M1 1L55 55M55 1L1 55M28 1L55 28L28 55L1 28Z" fill="none" stroke="var(--text-soft)" strokeWidth="1.2" />
        </svg>
      </div>
    ) : (
      <div className="flex h-[112px] items-center justify-center bg-sidebar-wash">
        <svg width="72" height="72" viewBox="0 0 56 56" aria-hidden className="shrink-0">
          <circle cx="28" cy="28" r="26" fill="var(--bg)" stroke="var(--text-primary)" strokeWidth="1.2" />
          <circle cx="28" cy="28" r="15" fill="none" stroke="var(--text-primary)" strokeWidth="1.2" />
          <path d="M28 2V54M2 28H54" fill="none" stroke="var(--text-primary)" strokeWidth="1.2" />
        </svg>
      </div>
    );
  const body = (
    <Panel className="flex h-full min-w-0 grow basis-0 flex-col overflow-clip">
      {art}
      <div className="flex flex-col gap-[2px] px-[14px] py-3">
        <div className="text-[15px] font-bold leading-[18px] text-ink">{t(c.title)}</div>
        <div className="text-[13px] leading-4 text-soft">{c.sub}</div>
      </div>
    </Panel>
  );
  return c.kind === "d1" && chartHref ? (
    <Link href={chartHref} className="flex min-w-0 grow basis-0 no-underline">
      {body}
    </Link>
  ) : (
    <div className="flex min-w-0 grow basis-0">{body}</div>
  );
}

function Remedy({ r, last }: { r: ClientDetail["remedies"][number]; last: boolean }) {
  const t = useT();
  const pct = Math.round((r.day / r.total) * 100);
  const done = pct >= 90;
  return (
    <div className={`flex flex-col gap-2 px-4 py-[14px] ${last ? "" : "border-b border-rule"}`}>
      <div className="flex items-baseline justify-between gap-3">
        <div className="text-[15px] font-bold leading-[18px] text-ink">{r.title}</div>
        <div className={`shrink-0 whitespace-pre text-[13px] font-bold leading-4 ${done ? "text-ok" : "text-accent-text"}`}>
          {t("Day {day} of {total}", { day: r.day, total: r.total })}
        </div>
      </div>
      <div className="h-[6px] rounded-[3px] bg-rule">
        <div
          className="h-[6px] rounded-[3px]"
          style={{
            width: `${pct}%`,
            backgroundColor: done ? "var(--success)" : "var(--accent)",
            backgroundImage: done ? undefined : "var(--fill-primary)",
          }}
        />
      </div>
      <div className="text-[13px] leading-4 text-soft">{r.note}</div>
    </div>
  );
}

export default function ClientPage({ params }: { params: Promise<{ clientId: string }> }) {
  const { clientId } = use(params);
  const t = useT();
  const [d, setD] = useState<ClientDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState(false);
  const [rev, setRev] = useState(0);
  const [raw, setRaw] = useState<ClientV1 | null>(null);
  const live = !isFixtures();

  useEffect(() => {
    api.getClientDetail(clientId).then(setD).catch(() => setFailed(true));
    if (live) v1Api.getClient(clientId).then(setRaw).catch(() => undefined);
  }, [clientId, live, rev]);

  const name = d?.row.name ?? "";
  return (
    <>
      <Topbar crumbs={[{ label: "Clients", href: "/clients" }, { label: name || t("Client") }]} />
      <main className="flex flex-1 flex-col gap-6 px-5 py-7 lg:px-10">
        {failed ? <p className="m-0 text-[15px] text-body">{t("This client could not be loaded.")}</p> : null}
        {d ? (
          <>
            <div className="flex flex-wrap items-center gap-5">
              <div className="flex size-[76px] shrink-0 items-center justify-center rounded-[10px] border border-rule bg-wash-soft text-[26px] font-bold leading-8 tracking-[0.02em] text-accent-text">
                {d.row.initials}
              </div>
              <div className="flex min-w-[260px] grow basis-0 flex-col gap-2">
                <div className="flex flex-wrap items-center gap-3">
                  <h1 className="m-0 text-[28px] font-bold leading-9 tracking-[-0.02em] text-ink lg:text-[32px]">{name}</h1>
                  {!live && d.row.tags.includes("Lal Kitab") ? (
                    <span
                      className="rounded-[4px] px-2 py-[3px] text-[13px] font-bold leading-4 text-accent-text"
                      style={{ backgroundColor: "var(--surface-2)", backgroundImage: "linear-gradient(180deg, var(--surface) 0%, #FFFFFF 100%)" }}
                    >
                      {t("Lal Kitab")}
                    </span>
                  ) : null}
                  {d.consultToday ? <Chip tone="ok" className="py-[3px]">{d.consultToday}</Chip> : null}
                </div>
                {d.bornLine ? <p className="m-0 whitespace-pre-wrap text-[15px] leading-5 text-body">{d.bornLine}</p> : null}
                {live ? <ClientTags clientId={clientId} initial={d.row.tags} /> : null}
                {d.timeConfirmed ? (
                  <div className="flex items-center gap-2 self-start rounded-[4px] bg-ok-wash py-1 pl-2 pr-[10px]">
                    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden className="shrink-0">
                      <path d="M2.5 7.5L5.5 10.5L11.5 3.5" fill="none" stroke="var(--success)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <span className="text-[13px] font-bold leading-4 text-ok">{d.timeConfirmed}</span>
                  </div>
                ) : null}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {live ? (
                  <Btn variant="outline" className="py-[10px]" onClick={() => setEditing(true)}>{t("Edit details")}</Btn>
                ) : null}
                {d.chartId ? (
                  <Btn variant="outline" href={`/charts/${d.chartId}/report`} className="py-[10px]">{t("Generate report")}</Btn>
                ) : (
                  <Btn variant="outline" className="py-[10px]" disabled>{t("Generate report")}</Btn>
                )}
                {d.chartId ? (
                  <Btn href={`/charts/${d.chartId}`} className="px-4 py-[10px]">{t("Open chart")}</Btn>
                ) : (
                  <Btn href="/clients/new" className="px-4 py-[10px]">{t("New chart")}</Btn>
                )}
              </div>
            </div>

            <div className="flex flex-col items-stretch gap-7 lg:flex-row lg:items-start">
              <div className="flex min-w-0 grow basis-0 flex-col gap-6">
                <ClientBrief clientId={clientId} />
                <section className="flex flex-col gap-3">
                  <SectionHead title="Charts" action="New chart" />
                  {d.charts.length ? (
                    <div className="flex flex-col gap-3 sm:flex-row">
                      {d.charts.map((c) => (
                        <ChartTile key={c.id} c={c} chartHref={d.chartId ? `/charts/${d.chartId}` : null} />
                      ))}
                    </div>
                  ) : (
                    <Panel className="px-5 py-5 text-[14px] leading-5 text-body">{t("No charts yet. Start with a birth chart.")}</Panel>
                  )}
                </section>

                <ConsultationNotesSection clientId={clientId} chartId={d.chartId} />
                <PredictionsSection clientId={clientId} />
                <ClientTimeline clientId={clientId} />
              </div>

              <div className="flex shrink-0 flex-col gap-6 lg:w-[380px]">
                <section className="flex flex-col gap-3">
                  <SectionHead title="Remedies in progress" note={t("{n} active", { n: d.remedies.length })} />
                  <Panel className="flex flex-col">
                    {d.remedies.length ? (
                      d.remedies.map((r, i) => <Remedy key={r.title} r={r} last={i === d.remedies.length - 1} />)
                    ) : (
                      <div className="px-4 py-[14px] text-[14px] leading-5 text-body">{t("No remedies running.")}</div>
                    )}
                  </Panel>
                </section>
                <RemindersPanel clientId={clientId} />
                <section className="flex flex-col gap-3">
                  <SectionHead title="Reports sent" action="New report" />
                  <Panel className="flex flex-col">
                    {d.reports.length ? (
                      d.reports.map((r, i) => (
                        <div key={`${r.title}-${i}`} className={`flex items-center gap-3 px-4 py-3 ${i === d.reports.length - 1 ? "" : "border-b border-rule"}`}>
                          <div className="flex min-w-0 grow flex-col">
                            <div className="truncate text-[14px] font-bold leading-[18px] text-ink">{r.title}</div>
                            <div className="text-[12px] leading-4 text-soft">
                              {r.sentKey ? t(r.sentKey, { date: r.sentParams?.date ?? "", lang: t(r.sentParams?.lang ?? "") }) : r.sent}
                            </div>
                          </div>
                          {r.href ? (
                            <a href={r.href} className="text-[13px] font-bold leading-4 text-accent-text no-underline" target="_blank" rel="noreferrer">
                              {t("Download")}
                            </a>
                          ) : null}
                          <Chip tone={r.tone ?? "ok"} className="py-[3px]">{t(r.status)}</Chip>
                        </div>
                      ))
                    ) : (
                      <div className="px-4 py-3 text-[14px] leading-5 text-body">{t("Nothing sent yet.")}</div>
                    )}
                  </Panel>
                </section>
              </div>
            </div>

            {d.facts.length ? (
              <div className="flex flex-wrap gap-3 pt-2 [&>*]:min-w-[200px]">
                {d.facts.map((f, i) => (
                  <div
                    key={f.label}
                    className={`flex grow basis-0 flex-col gap-[6px] rounded-[10px] border border-rule px-[18px] py-4 ${i === 0 ? "bg-wash-soft" : ""}`}
                  >
                    <div className={`text-[12px] font-bold uppercase leading-4 tracking-[0.08em] ${i === 0 ? "text-accent-text" : "text-soft"}`}>{f.label}</div>
                    <div className="text-[19px] font-bold leading-6 text-ink">{f.value}</div>
                    {f.note ? <div className="text-[13px] leading-4 text-body">{f.note}</div> : null}
                  </div>
                ))}
              </div>
            ) : null}
            {live ? <ClientLivePanels clientId={clientId} chartId={d.chartId} /> : null}
          </>
        ) : null}
      </main>
      {live ? <ClientFormDialog open={editing} onOpenChange={setEditing} client={raw} onSaved={() => setRev((n) => n + 1)} /> : null}
    </>
  );
}
