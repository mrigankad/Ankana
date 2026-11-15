"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { MatchGlyph, MiniKundali } from "@/components/ankana/mini-kundali";
import { Topbar } from "@/components/ankana/topbar";
import { BriefSheet } from "@/components/ankana/consult-brief";
import { Btn, Chip, Panel } from "@/components/ankana/ui";
import { api } from "@/lib/api/client";
import type { ConsultCard, SkyItem, TodayView } from "@/lib/api/types";
import { useLanguage, useT } from "@/lib/i18n/provider";
import { tName } from "@/lib/i18n/translate";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

const NUMBER_WORDS = [
  "Nobody",
  "One person is",
  "Two people are",
  "Three people are",
  "Four people are",
  "Five people are",
  "Six people are",
  "Seven people are",
  "Eight people are",
  "Nine people are",
  "Ten people are",
];

function greeting(tv: TodayView, t: ReturnType<typeof useT>) {
  const hour = new Date().getHours();
  const name = tv.practitioner.firstName;
  const hello = name
    ? hour < 12 ? t("Good morning, {name}.", { name }) : hour < 17 ? t("Good afternoon, {name}.", { name }) : t("Good evening, {name}.", { name })
    : hour < 12 ? t("Good morning.") : hour < 17 ? t("Good afternoon.") : t("Good evening.");
  const n = tv.consultCount;
  const who =
    n === 0
      ? t("Nobody is coming today.")
      : NUMBER_WORDS[n]
        ? t(`${NUMBER_WORDS[n]} coming today.`)
        : t("{n} people are coming today.", { n });
  return `${hello} ${who}`;
}

function dateLine(tv: TodayView, t: ReturnType<typeof useT>, lang: string) {
  if (!tv.dateIso) return tv.dateLine;
  const [y, m, d] = tv.dateIso.split("-").map(Number) as [number, number, number];
  const day = new Intl.DateTimeFormat(lang === "hi" ? "hi-IN" : "en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(new Date(Date.UTC(y, m - 1, d)));
  const f = tv.first;
  if (!f) return t("{day}. Nothing is booked for today.", { day });
  const state =
    f.status === "prepared"
      ? t("The chart is ready.")
      : f.status === "needs_birth_time"
        ? t("The birth time needs checking first.")
        : t("There is no chart yet.");
  return t("{day} · {name} is first, at {time}. {state}", { day, name: f.name, time: f.time, state });
}

function skyTitle(s: SkyItem, t: ReturnType<typeof useT>) {
  if (!s.kind || !s.sign) return s.title;
  const planet = s.planet ? tName(t, s.planet.charAt(0).toUpperCase() + s.planet.slice(1)) : "";
  const sign = tName(t, s.sign);
  switch (s.kind) {
    case "ingress":
      return t("{planet} enters {sign}", { planet, sign });
    case "retrograde-station":
      return t("{planet} stations retrograde in {sign}", { planet, sign });
    case "direct-station":
      return t("{planet} stations direct in {sign}", { planet, sign });
    case "amavasya":
      return t("Amavasya in {sign}", { sign });
    default:
      return t("Purnima in {sign}", { sign });
  }
}

function PanchangCell({ label, value, note, last }: { label: string; value: string; note: string; last?: boolean }) {
  const t = useT();
  return (
    <div className={`flex min-w-[160px] grow basis-0 flex-col gap-1 px-5 py-4 ${last ? "bg-wash-soft" : "border-r border-rule"}`}>
      <div className={`text-[12px] font-bold leading-4 ${last ? "text-accent-text" : "text-soft"}`}>{t(label)}</div>
      <div className="text-[16px] font-bold leading-5 text-ink">{value}</div>
      <div className="text-[13px] leading-4 text-body">{note}</div>
    </div>
  );
}

function ConsultTile({ c }: { c: ConsultCard }) {
  const t = useT();
  const [brief, setBrief] = useState(false);
  const ready = c.status.tone === "ok";
  const headline = c.headlineKey ? t(c.headlineKey, { sign: tName(t, c.headlineParams?.sign ?? "") }) : c.headline;
  const sub = c.dasha
    ? t("{dasha} dasha", { dasha: `${tName(t, c.dasha.maha.charAt(0).toUpperCase() + c.dasha.maha.slice(1))}${c.dasha.antar ? ` / ${tName(t, c.dasha.antar.charAt(0).toUpperCase() + c.dasha.antar.slice(1))}` : ""}` })
    : c.sub;
  const body = (
    <Panel className="flex h-full min-w-0 flex-col overflow-clip">
      <div
        className="flex h-[170px] shrink-0 items-center gap-[14px] px-4"
        style={{
          backgroundColor: "var(--surface)",
          
        }}
      >
        {c.kind === "match" ? (
          <MatchGlyph />
        ) : (
          <MiniKundali houses={c.miniHouses ?? {}} wash={ready ? "var(--accent-tint)" : "var(--surface-2)"} />
        )}
        <div className="flex min-w-0 flex-col gap-1">
          <div className="text-[12px] font-bold leading-4 text-accent-text">{c.time}</div>
          <div className={`whitespace-pre-wrap break-words text-[19px] font-bold leading-6 ${ready ? "text-ink" : "text-black"}`}>{headline}</div>
          <div className="text-[13px] leading-4 text-body">{sub}</div>
        </div>
      </div>
      <div className="flex flex-col gap-2 px-4 py-[14px]">
        <div className="text-[17px] font-bold leading-[22px] text-ink">{c.clientName}</div>
        <div className="flex items-center gap-2">
          <Chip tone={c.status.tone}>{t(c.status.label)}</Chip>
          <span className="text-[13px] leading-4 text-body">{c.topic}</span>
        </div>
      </div>
    </Panel>
  );
  return (
    <div className="flex min-w-0 flex-col gap-2">
      {c.chartId ? (
        <Link href={`/charts/${c.chartId}`} className="block min-w-0 grow no-underline">
          {body}
        </Link>
      ) : (
        <div className="min-w-0 grow">{body}</div>
      )}
      {c.clientId && c.kind === "chart" ? (
        <>
          <button
            type="button"
            onClick={() => setBrief(true)}
            className="inline-flex h-[34px] items-center justify-center rounded-[6px] border border-rule bg-surface px-3 text-[13px] font-bold leading-4 text-accent-text hover:border-accent-line hover:bg-accent-wash"
          >
            {t("Prep brief")}
          </button>
          <BriefSheet open={brief} onOpenChange={setBrief} clientId={c.clientId} consultationId={c.id} name={c.clientName} />
        </>
      ) : null}
    </div>
  );
}

export default function TodayPage() {
  const t = useT();
  const { lang } = useLanguage();
  const [today, setToday] = useState<TodayView | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    api.getToday().then(setToday).catch(() => setFailed(true));
  }, []);
  const pan = today?.panchang ?? null;
  const ing = pan?.ingress ?? null;

  return (
    <>
      <Topbar crumbs={[{ label: "Today" }]} />
      <main className="flex flex-1 flex-col gap-7 px-5 py-8 lg:px-10 lg:py-9">
        {today ? (
          <>
            <div className="flex items-end justify-between gap-4">
              <div className="flex flex-col gap-1">
                <h1 className="m-0 text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink lg:text-[32px] lg:leading-10">
                  {greeting(today, t)}
                </h1>
                <p className="m-0 text-[16px] leading-5 text-body">{dateLine(today, t, lang)}</p>
              </div>
              <div
                className="hidden size-16 shrink-0 overflow-clip rounded-2xl border border-rule bg-white sm:block"
                style={{ boxShadow: "0 4px 14px rgba(34,30,29,0.08)" }}
              >
                <div
                  className="size-16 rounded-[10px]"
                  style={{
                    backgroundImage: "url(/illustrations/illus-astrolabe@2x.png)",
                    backgroundPosition: "50%",
                    backgroundSize: "118%",
                    backgroundRepeat: "no-repeat",
                  }}
                />
              </div>
            </div>

            <section aria-label={t("Today's panchang")} className="flex flex-col overflow-clip rounded-[10px] border border-rule lg:flex-row">
              <div
                className="flex shrink-0 flex-col gap-[2px] px-5 py-4 lg:w-[200px]"
                style={{
                  backgroundColor: "var(--text-primary)",
                }}
              >
                <div className="text-[12px] font-bold leading-4 tracking-[0.06em] text-accent-light">{t("TODAY'S PANCHANG")}</div>
                <div className="text-[22px] font-bold leading-7 text-white">{pan ? tName(t, pan.vara) : t("Not available")}</div>
                {pan ? (
                  <div className="deva whitespace-pre text-[12px] leading-4 text-[color:var(--rule-strong)]">
                    {pan.place ? `${pan.varaDeva} · ${t("{place} sunrise {time}", { place: pan.place, time: pan.sunrise })}` : pan.varaDeva}
                  </div>
                ) : null}
              </div>
              {pan ? (
                <div className="flex min-w-0 grow flex-wrap lg:flex-nowrap">
                  <PanchangCell
                    label="Tithi"
                    value={pan.tithi.paksha ? `${tName(t, pan.tithi.name)}, ${t(pan.tithi.paksha)}` : pan.tithi.name}
                    note={pan.tithi.untilTime ? t("until {time}", { time: pan.tithi.untilTime }) : pan.tithi.until}
                  />
                  <PanchangCell
                    label="Nakshatra"
                    value={tName(t, pan.nakshatra.name)}
                    note={pan.nakshatra.untilTime ? t("until {time}", { time: pan.nakshatra.untilTime }) : pan.nakshatra.until}
                  />
                  <PanchangCell
                    label="Rahu kaal"
                    value={pan.rahuKaal.from ? t("{from} to {to}", { from: pan.rahuKaal.from, to: pan.rahuKaal.to ?? "" }) : pan.rahuKaal.range}
                    note={t(pan.rahuKaal.note)}
                  />
                  <PanchangCell
                    label="Next ingress"
                    value={ing ? (ing.planet && ing.sign ? t("{planet} into {sign}", { planet: tName(t, cap(ing.planet)), sign: tName(t, ing.sign) }) : ing.title) : t("None soon")}
                    note={ing ? (ing.date ? t("{date}, touches {n} clients", { date: ing.date, n: ing.touched ?? 0 }) : ing.note) : ""}
                    last
                  />
                </div>
              ) : (
                <div className="flex min-w-0 grow flex-col justify-center gap-1 bg-wash-soft px-5 py-4">
                  <div className="text-[15px] font-bold leading-5 text-ink">{t("The panchang needs a place")}</div>
                  <div className="text-[13px] leading-4 text-body">{t("Set where the practice sits and today's tithi, nakshatra and Rahu kaal appear here.")}</div>
                  <Link href="/settings/practice" className="mt-1 text-[14px] font-bold text-accent-text no-underline hover:underline">{t("Set the practice place")}</Link>
                </div>
              )}
            </section>

            <div className="flex items-baseline justify-between">
              <div className="flex items-baseline gap-[10px]">
                <h2 className="m-0 text-[20px] font-bold leading-6 text-black">{t("Today's consultations")}</h2>
                <span className="text-[14px] leading-[18px] text-soft">{t("{n} booked", { n: today.consultCount })}</span>
              </div>
              <span className="text-[14px] font-bold leading-[18px] text-accent-text">{t("Open calendar")}</span>
            </div>

            {today.consults.length ? (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {today.consults.map((c) => (
                  <ConsultTile key={c.id} c={c} />
                ))}
              </div>
            ) : (
              <Panel className="flex flex-wrap items-center justify-between gap-3 px-5 py-5">
                <span className="text-[14px] leading-5 text-body">{t("Nothing is booked for today.")}</span>
                <Btn variant="outline" href="/clients">
                  {t("Open clients")}
                </Btn>
              </Panel>
            )}

            <div className="flex flex-col gap-4 lg:flex-row" id="needs-you">
              <Panel className="flex min-w-0 grow-[1.4] basis-0 flex-col gap-1 px-5 py-[18px]">
                <div className="flex justify-between pb-2">
                  <h2 className="m-0 text-[17px] font-bold leading-[22px] text-black">{t("Needs you")}</h2>
                  <span className="text-[13px] leading-4 text-soft">{t("{n} items", { n: today.needsYou.length })}</span>
                </div>
                {today.needsYou.length === 0 ? (
                  <div className="border-t border-rule py-[10px] text-[14px] leading-[18px] text-body">{t("All clear. Nothing is waiting on you.")}</div>
                ) : null}
                {today.needsYou.slice(0, 8).map((n) => {
                  const row = (
                    <>
                      <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: n.tone === "alert" ? "var(--text-primary)" : "var(--warning)" }} />
                      <div className="grow text-[14px] leading-[18px] text-black">
                        <span className="font-bold">{n.who}</span> · {n.textKey ? t(n.textKey, n.textParams) : n.text}
                      </div>
                      <span className="text-[14px] font-bold leading-[18px] text-accent-text">{t(n.action)}</span>
                    </>
                  );
                  return n.href ? (
                    <Link key={n.id} href={n.href} className="flex items-center gap-3 border-t border-rule py-[10px] no-underline hover:bg-wash-soft">
                      {row}
                    </Link>
                  ) : (
                    <div key={n.id} className="flex items-center gap-3 border-t border-rule py-[10px]">
                      {row}
                    </div>
                  );
                })}
                {today.needsYou.length > 8 ? (
                  <Link href="/needs-you" className="border-t border-rule pt-[10px] text-[14px] font-bold leading-[18px] text-accent-text no-underline">
                    {t("See all")}
                  </Link>
                ) : null}
              </Panel>
              <Panel className="flex min-w-0 grow basis-0 flex-col gap-1 px-5 py-[18px]">
                <div className="flex justify-between pb-2">
                  <h2 className="m-0 text-[17px] font-bold leading-[22px] text-black">{t("Sky this week")}</h2>
                  <span className="text-[13px] leading-4 text-soft">{t("Clients touched")}</span>
                </div>
                {today.sky.length === 0 ? (
                  <div className="border-t border-rule py-[10px] text-[14px] leading-[18px] text-body">{t("Nothing notable in the next 7 days.")}</div>
                ) : null}
                {today.sky.map((s) => (
                  <div key={`${s.date}-${s.title}`} className="flex border-t border-rule py-[10px] text-[14px] leading-[18px]">
                    <span className="w-16 shrink-0 text-soft">{s.date}</span>
                    <span className="grow font-bold text-black">{skyTitle(s, t)}</span>
                    <span className="text-black">{s.touched}</span>
                  </div>
                ))}
              </Panel>
            </div>
          </>
        ) : failed ? (
          <p className="m-0 text-[15px] text-body">{t("Today could not be loaded.")}</p>
        ) : null}
      </main>
    </>
  );
}
