"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Chip, Panel, type ChipTone } from "@/components/ankana/ui";
import { Button, DateField } from "@/components/ui";
import { Skeleton } from "@/components/ui/skeleton";
import type { VedicChartArtifact } from "@astro/astrology-core";

import type {
  DoubleTransitV1,
  GocharaPlanetV1,
  GocharaV1,
  SadeSatiLifetimeV1,
  SadeSatiPeriodV1,
  TransitDepthSource,
} from "@/lib/api/transit-depth";
import { lazyFixtureDepthSource, liveDepthSource } from "@/lib/api/transit-depth";
import { useLanguage, useT } from "@/lib/i18n/provider";
import { tName } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const MIN_DATE = "1900-01-01";
const MAX_DATE = "2200-12-31";

type T = (text: string, params?: Record<string, string | number>) => string;

function useFormat() {
  const { lang } = useLanguage();
  const locale = lang === "hi" ? "hi-IN" : "en-GB";
  return useMemo(
    () => ({
      full: (iso: string) => new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(iso)),
      month: (iso: string) => new Intl.DateTimeFormat(locale, { month: "short", year: "2-digit", timeZone: "UTC" }).format(new Date(iso)),
      year: (ms: number) => new Intl.DateTimeFormat(locale, { year: "numeric", timeZone: "UTC" }).format(new Date(ms)),
    }),
    [locale],
  );
}

/** Loads one resource and exposes a retry; resets when `key` changes. */
function useLoad<V>(load: () => Promise<V>, key: string) {
  const [state, setState] = useState<{ data: V | null; error: boolean; key: string }>({ data: null, error: false, key });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    load()
      .then((data) => !cancelled && setState({ data, error: false, key }))
      .catch(() => !cancelled && setState({ data: null, error: true, key }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);
  const current = state.key === key;
  return {
    data: current ? state.data : null,
    error: current && state.error,
    retry: () => {
      setState({ data: null, error: false, key });
      setAttempt((n) => n + 1);
    },
  };
}

function Loading({ className }: { className?: string }) {
  return <Skeleton className={cn("h-48 w-full rounded-[10px]", className)} />;
}

function Failed({ onRetry }: { onRetry: () => void }) {
  const t = useT();
  return (
    <Panel className="flex flex-wrap items-center gap-3 px-5 py-4">
      <p role="alert" className="m-0 text-[14px] leading-5 text-body">{t("This section could not be loaded.")}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>{t("Retry")}</Button>
    </Panel>
  );
}

function Proof({ text }: { text: string }) {
  const t = useT();
  return (
    <p className="m-0 border-t border-rule px-5 py-3 text-[13px] leading-5 text-soft">
      <span className="font-bold text-body">{t("Source")}: </span>
      {t(text)}
    </p>
  );
}

function SectionHead({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">{title}</h2>
      {sub ? <p className="m-0 max-w-[760px] text-[14px] leading-5 text-body">{sub}</p> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ gochara */

const VERDICT_TONE: Record<GocharaPlanetV1["verdict"], ChipTone> = {
  favourable: "ok",
  mixed: "accent",
  unfavourable: "alert",
  not_rated: "muted",
};

function verdictLabel(t: T, v: GocharaPlanetV1["verdict"]) {
  return { favourable: t("Favourable"), mixed: t("Mixed"), unfavourable: t("Unfavourable"), not_rated: t("Not rated") }[v];
}

function reasonText(t: T, r: GocharaPlanetV1): string {
  const planet = tName(t, cap(r.planet));
  const base = { planet, house: r.house_from_moon, n: r.bindus ?? 0 };
  switch (r.reason_code) {
    case "favourable_strong":
      return t("{planet} stands in house {house} from the Moon, a favourable house, and holds {n} bindus here.", base);
    case "favourable_weak_bindus":
      return t("{planet} stands in house {house} from the Moon, a favourable house, but holds only {n} bindus, so the result is muted.", base);
    case "vedha_blocked":
      return t("{planet} stands in house {house} from the Moon, a favourable house, but {by} stands in vedha house {vedha}, which obstructs it.", {
        ...base,
        by: r.vedha_by.map((p) => tName(t, cap(p))).join(", "),
        vedha: r.vedha_house ?? 0,
      });
    case "unfavourable_softened":
      return t("{planet} stands in house {house} from the Moon, not a favourable house, softened by {n} bindus.", base);
    case "unfavourable":
      return t("{planet} stands in house {house} from the Moon, not a favourable house, and holds {n} bindus.", base);
    default:
      return t("{planet} is shown by position only. The classical gochara tables rate the seven grahas.", base);
  }
}

function saturnStatusText(t: T, s: GocharaV1["saturn_status"]): string {
  if (s.kind === "sade_sati") return t("Saturn today: sade sati, {phase} phase", { phase: t(s.phase ?? "peak") });
  if (s.kind === "dhaiya_kantaka") return t("Saturn today: kantaka shani, 4th from the Moon");
  if (s.kind === "dhaiya_ashtama") return t("Saturn today: ashtama shani, 8th from the Moon");
  return t("Saturn is clear of sade sati and dhaiya");
}

function Bindus({ value, sav }: { value: number | null; sav: number }) {
  const t = useT();
  if (value === null) {
    return <span className="text-[13px] leading-4 text-soft">{t("Sign total {n}", { n: sav })}</span>;
  }
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2" role="img" aria-label={t("Bindus {n} of 8", { n: value })}>
        <span className="flex gap-[3px]">
          {Array.from({ length: 8 }, (_, i) => (
            <span key={i} className={cn("h-[14px] w-[7px] rounded-[2px]", i < value ? "bg-sindoor" : "bg-rule")} />
          ))}
        </span>
        <span className="text-[15px] font-bold leading-5 text-ink">{value}</span>
      </div>
      <span className="text-[12px] leading-4 text-soft">{t("Sign total {n}", { n: sav })}</span>
    </div>
  );
}

function GocharaRow({ row }: { row: GocharaPlanetV1 }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const rated = row.verdict !== "not_rated";
  return (
    <li className="border-b border-rule last:border-b-0">
      <div className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 px-5 py-3 md:grid-cols-[84px_118px_minmax(0,1.3fr)_minmax(0,1fr)_112px]">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[15px] font-bold leading-5 text-ink">{tName(t, cap(row.planet))}</span>
        </div>
        <div className="col-start-2 row-start-1 justify-self-end md:col-start-auto md:row-start-auto md:justify-self-start">
          <Chip tone={VERDICT_TONE[row.verdict]}>{verdictLabel(t, row.verdict)}</Chip>
        </div>
        <div className="flex flex-col">
          <span className="text-[14px] leading-5 text-ink">
            {tName(t, cap(row.sign))} <span className="text-soft">{row.degrees_in_sign.toFixed(1)}&deg;</span>
          </span>
          <span className="text-[13px] leading-4 text-soft">
            {t("House {m} from Moon, {l} from lagna", { m: row.house_from_moon, l: row.house_from_lagna })}
            {row.retrograde && row.planet !== "rahu" && row.planet !== "ketu" ? `, ${t("retrograde")}` : ""}
          </span>
        </div>
        <Bindus value={row.bindus} sav={row.sav} />
        {rated ? (
          <span className="col-span-2 justify-self-start md:col-span-1 md:justify-self-end">
            <Button variant="ghost" size="sm" className="-ml-2.5 md:ml-0" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
              {open ? t("Hide working") : t("Show working")}
            </Button>
          </span>
        ) : (
          <span className="hidden md:block" />
        )}
      </div>
      {open ? (
        <div className="flex flex-col gap-1 bg-sidebar-wash px-5 py-3 text-[14px] leading-5 text-body">
          <p className="m-0 text-ink">{reasonText(t, row)}</p>
          <p className="m-0">{t("Favourable houses from the Moon: {list}", { list: row.favourable_houses.join(", ") })}</p>
          <p className="m-0">
            {row.favourable && row.vedha_house
              ? t("Vedha house for this placement: {n}", { n: row.vedha_house })
              : t("Vedha is checked only for favourable houses.")}
          </p>
        </div>
      ) : null}
    </li>
  );
}

function GocharaSection({ source, date, onDate }: { source: TransitDepthSource; date: string; onDate: (d: string) => void }) {
  const t = useT();
  const f = useFormat();
  const { data, error, retry } = useLoad(() => source.getGochara(date || null), `g:${date}`);
  const [draft, setDraft] = useState(date);
  const today = date === "";
  return (
    <section aria-label={t("Gochara")} className="flex flex-col gap-4">
      <SectionHead
        title={today ? t("Gochara today") : t("Gochara on {date}", { date: data ? f.full(data.date) : date })}
        sub={t("Each planet is read from the natal Moon with its vedha check, and with the bhinna ashtakavarga bindus it holds in the sign it occupies.")}
      />
      <Panel className="flex flex-wrap items-end gap-x-5 gap-y-3 px-5 py-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="whatif-date" className="text-[13px] font-bold leading-4 text-body">{t("What-if date")}</label>
          <DateField
            id="whatif-date"
            value={draft}
            min={MIN_DATE}
            max={MAX_DATE}
            aria-label={t("What-if date")}
            onChange={(iso) => {
              setDraft(iso);
              if (iso) onDate(iso);
            }}
          />
        </div>
        <Button
          variant="outline"
          size="md"
          disabled={today}
          onClick={() => {
            setDraft("");
            onDate("");
          }}
        >
          {t("Back to today")}
        </Button>
        <p className="m-0 max-w-[440px] text-[13px] leading-5 text-soft">
          {t("Type any date from 1900 to 2200 to see the sky against this chart on that day. Gochara, the Sade sati line and the bindus update together.")}
        </p>
      </Panel>
      {error ? (
        <Failed onRetry={retry} />
      ) : !data ? (
        <Loading className="h-72" />
      ) : (
        <Panel className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-3 border-b border-rule bg-sidebar-wash px-5 py-3">
            <Chip tone={data.saturn_status.kind ? "accent" : "muted"}>{saturnStatusText(t, data.saturn_status)}</Chip>
            <span className="text-[13px] leading-4 text-soft">
              {t("{fav} favourable, {mixed} mixed, {unfav} unfavourable", {
                fav: data.tally.favourable ?? 0,
                mixed: data.tally.mixed ?? 0,
                unfav: data.tally.unfavourable ?? 0,
              })}
            </span>
            <span className="text-[13px] leading-4 text-soft">
              {t("Moon in {moon}, lagna {lagna}", { moon: tName(t, cap(data.moon_sign)), lagna: tName(t, cap(data.lagna_sign)) })}
            </span>
          </div>
          <div className="hidden grid-cols-[84px_118px_minmax(0,1.3fr)_minmax(0,1fr)_112px] gap-x-4 border-b border-rule px-5 py-2 text-[12px] font-bold leading-4 text-soft md:grid">
            <span>{t("Planet")}</span>
            <span>{t("Verdict")}</span>
            <span>{t("Sign now")}</span>
            <span>{t("Bindus here")}</span>
            <span />
          </div>
          <ul className="m-0 list-none p-0">
            {data.planets.map((r) => (
              <GocharaRow key={r.planet} row={r} />
            ))}
          </ul>
          <Proof text={data.proof} />
        </Panel>
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- sade sati */

const KIND_LABEL = (t: T, k: SadeSatiPeriodV1["kind"]) =>
  ({ sade_sati: t("Sade sati"), dhaiya_kantaka: t("Kantaka shani"), dhaiya_ashtama: t("Ashtama shani") })[k];

const BAND_CLASS: Record<string, string> = {
  rising: "bg-accent-light",
  peak: "bg-sindoor",
  setting: "bg-accent-light/70",
  dhaiya_kantaka: "bg-ink/25",
  dhaiya_ashtama: "bg-ink/45",
};

function SadeSatiSection({ source, whatIf }: { source: TransitDepthSource; whatIf: string }) {
  const t = useT();
  const f = useFormat();
  const { data, error, retry } = useLoad(() => source.getSadeSati(), "s");
  return (
    <section aria-label={t("Sade sati and dhaiya")} className="flex flex-col gap-4">
      <SectionHead
        title={t("Sade sati and dhaiya for life")}
        sub={t("Every period from the natal Moon, with the rising, peak and setting phases, today's status and the next one.")}
      />
      {error ? <Failed onRetry={retry} /> : !data ? <Loading className="h-64" /> : <SadeSatiBody data={data} whatIf={whatIf} f={f} />}
    </section>
  );
}

function SadeSatiBody({ data, whatIf, f }: { data: SadeSatiLifetimeV1; whatIf: string; f: ReturnType<typeof useFormat> }) {
  const t = useT();
  const birth = Date.parse(data.birth);
  const t0 = birth;
  const t1 = birth + 100 * 365.2425 * 86_400_000;
  const pos = (iso: string | number) => {
    const ms = typeof iso === "number" ? iso : Date.parse(iso);
    return Math.min(100, Math.max(0, ((ms - t0) / (t1 - t0)) * 100));
  };
  const next = data.next_index !== null ? data.periods[data.next_index] : null;
  const nextSade = data.next_sade_sati_index !== null ? data.periods[data.next_sade_sati_index] : null;
  const cur = data.current;
  const running = cur.kind !== null;
  const ticks = Array.from({ length: 6 }, (_, i) => t0 + (i * 20 * (t1 - t0)) / 100);
  const marks = [{ ms: Date.parse(data.as_of), label: t("Today"), solid: true }, ...(whatIf ? [{ ms: Date.parse(`${whatIf}T06:30:00Z`), label: t("What-if"), solid: false }] : [])];
  const visible = data.periods.filter((p) => Date.parse(p.starts_at) < t1);
  const statusChip =
    cur.kind === "sade_sati"
      ? t("Running, {phase} phase", { phase: t(cur.phase ?? "peak") })
      : cur.kind
        ? t("Running, {kind}", { kind: KIND_LABEL(t, cur.kind) })
        : t("Not running");
  const range = (p: SadeSatiPeriodV1) => t("{a} to {b}", { a: f.full(p.starts_at), b: f.full(p.ends_at) });
  return (
    <Panel className="overflow-hidden">
      <div className="flex flex-col gap-3 px-5 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <Chip tone={running ? "accent" : "muted"}>{statusChip}</Chip>
          <span className="text-[14px] leading-5 text-body">
            {t("Moon in {moon}. Saturn is in {sign}, house {n} from the Moon.", {
              moon: tName(t, cap(data.moon_sign)),
              sign: tName(t, cap(cur.saturn_sign)),
              n: cur.house_from_moon,
            })}
          </span>
        </div>
        <div className="grid gap-2 text-[14px] leading-5 text-body md:grid-cols-2">
          {next ? (
            <p className="m-0">
              <span className="font-bold text-ink">{t("Next period")}: </span>
              {t("{kind}, {range}, at age {age}", { kind: KIND_LABEL(t, next.kind), range: range(next), age: Math.round(next.age_start) })}
            </p>
          ) : null}
          {nextSade && nextSade !== next ? (
            <p className="m-0">
              <span className="font-bold text-ink">{t("Next sade sati")}: </span>
              {t("{range}, at age {age}", { range: range(nextSade), age: Math.round(nextSade.age_start) })}
            </p>
          ) : null}
        </div>
      </div>

      <div className="px-5 pb-4">
        <div role="img" aria-label={t("Band timeline of every sade sati and dhaiya period across a lifetime")} className="relative h-[96px]">
          <div className="absolute inset-x-0 top-[22px] h-[28px] rounded-[4px] bg-sidebar-wash" />
          {visible.map((p) => {
            const left = pos(p.starts_at);
            const width = Math.max(0.6, pos(p.ends_at) - left);
            return p.phases.map((ph) => {
              const l = pos(ph.starts_at);
              const w = Math.max(0.5, pos(ph.ends_at) - l);
              const dhaiya = ph.phase === "dhaiya";
              return (
                <span
                  key={`${p.index}-${ph.phase}`}
                  title={`${KIND_LABEL(t, p.kind)}${dhaiya ? "" : `, ${t(ph.phase)}`}: ${range({ ...p, starts_at: ph.starts_at, ends_at: ph.ends_at })}`}
                  className={cn(
                    "absolute rounded-[3px]",
                    BAND_CLASS[dhaiya ? p.kind : ph.phase],
                    p.status === "past" ? "opacity-60" : "",
                    dhaiya ? "top-[29px] h-[14px]" : "top-[22px] h-[28px]",
                  )}
                  style={{ left: `${l}%`, width: `${dhaiya ? Math.max(0.6, width) : w}%` }}
                />
              );
            });
          })}
          {marks.map((m) => (
            <span key={m.label} className="absolute top-0 flex -translate-x-1/2 flex-col items-center" style={{ left: `${pos(m.ms)}%` }}>
              <span className={cn("rounded-[4px] px-1.5 text-[11px] font-bold leading-4", m.solid ? "bg-ink text-white" : "bg-hl-wash text-hl-text")}>{m.label}</span>
              <span className={cn("h-[56px] w-px", m.solid ? "bg-ink" : "bg-hl")} />
            </span>
          ))}
          {ticks.map((ms, i) => (
            <span key={ms} className="absolute top-[64px] whitespace-nowrap text-[12px] leading-4 text-soft" style={{ left: `${pos(ms)}%`, transform: i === 0 ? "none" : i === ticks.length - 1 ? "translateX(-100%)" : "translateX(-50%)" }}>
              {f.year(ms)}
              <span className="block text-[11px]">{t("Age {n}", { n: i * 20 })}</span>
            </span>
          ))}
        </div>
        <ul className="m-0 mt-2 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-[12px] leading-4 text-body">
          {(["rising", "peak", "setting", "dhaiya_kantaka", "dhaiya_ashtama"] as const).map((k) => (
            <li key={k} className="flex items-center gap-1.5">
              <span className={cn("size-[10px] rounded-[2px]", BAND_CLASS[k])} />
              {k === "dhaiya_kantaka" ? t("Kantaka shani (4th)") : k === "dhaiya_ashtama" ? t("Ashtama shani (8th)") : t("Sade sati, {phase}", { phase: t(k) })}
            </li>
          ))}
        </ul>
      </div>

      <ul className="m-0 list-none border-t border-rule p-0">
        {visible.map((p) => (
          <li key={p.index} className="flex flex-col gap-1 border-b border-rule px-5 py-3 last:border-b-0 md:flex-row md:items-baseline md:gap-4">
            <div className="flex items-center gap-2 md:w-[260px] md:shrink-0">
              <span className={cn("text-[14px] font-bold leading-5", p.status === "past" ? "text-body" : "text-ink")}>{KIND_LABEL(t, p.kind)}</span>
              <Chip tone={p.status === "current" ? "accent" : p.status === "upcoming" ? "ink" : "muted"}>
                {{ past: t("Past"), current: t("Running"), upcoming: t("Upcoming") }[p.status]}
              </Chip>
            </div>
            <div className="flex flex-1 flex-col gap-0.5 text-[13px] leading-5 text-body">
              <span>
                {range(p)}
                <span className="text-soft">
                  {" "}
                  {p.started_before_birth ? t("Began before birth, ends at age {b}", { b: Math.round(p.age_end) }) : t("Age {a} to {b}", { a: Math.round(p.age_start), b: Math.round(p.age_end) })}
                </span>
              </span>
              {p.kind === "sade_sati" ? (
                <span className="flex flex-wrap gap-x-4 text-soft">
                  {p.phases.map((ph) => (
                    <span key={ph.phase}>
                      <span className="font-bold text-body">{t(ph.phase)}</span> {f.full(ph.starts_at)}
                      {" "}
                      <span>({tName(t, cap(ph.saturn_sign))})</span>
                    </span>
                  ))}
                </span>
              ) : (
                <span className="text-soft">{t("Saturn in {sign}", { sign: tName(t, cap(p.phases[0].saturn_sign)) })}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
      <Proof text={data.proof} />
    </Panel>
  );
}

/* ------------------------------------------------------------- double transit */

function DoubleTransitSection({ source }: { source: TransitDepthSource }) {
  const t = useT();
  const f = useFormat();
  const { data, error, retry } = useLoad(() => source.getDoubleTransit(), "d");
  return (
    <section aria-label={t("Double transit")} className="flex flex-col gap-4">
      <SectionHead
        title={t("Double transit, next 24 months")}
        sub={t("A house is active for events while both Jupiter and Saturn occupy it or aspect it. Houses count from the lagna.")}
      />
      {error ? <Failed onRetry={retry} /> : !data ? <Loading className="h-72" /> : <DoubleBody data={data} f={f} t={t} />}
    </section>
  );
}

function DoubleBody({ data, f, t }: { data: DoubleTransitV1; f: ReturnType<typeof useFormat>; t: T }) {
  const t0 = Date.parse(data.start);
  const t1 = Date.parse(data.end);
  const pos = (iso: string) => ((Date.parse(iso) - t0) / (t1 - t0)) * 100;
  const quarters = Array.from({ length: 9 }, (_, i) => new Date(t0 + (i * (t1 - t0)) / 8).toISOString());
  return (
    <Panel className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-rule bg-sidebar-wash px-5 py-3 text-[13px] leading-4 text-body">
        <Chip tone="ink">{t("Jupiter in {sign}", { sign: tName(t, cap(data.jupiter_now)) })}</Chip>
        <Chip tone="ink">{t("Saturn in {sign}", { sign: tName(t, cap(data.saturn_now)) })}</Chip>
        <span className="text-soft">{t("From {a} to {b}", { a: f.full(data.start), b: f.full(data.end) })}</span>
      </div>
      <div className="hidden items-end px-5 pt-3 md:flex">
        <span className="w-[210px] shrink-0" />
        <div className="relative h-4 flex-1 text-[12px] leading-4 text-soft">
          {quarters.map((q, i) =>
            i % 2 === 0 ? (
              <span key={q} className="absolute top-0 whitespace-nowrap" style={{ left: `${(i / 8) * 100}%`, transform: i === 0 ? "none" : i === 8 ? "translateX(-100%)" : "translateX(-50%)" }}>
                {f.month(q)}
              </span>
            ) : null,
          )}
        </div>
        <span className="w-[84px] shrink-0" />
      </div>
      <ul className="m-0 list-none p-0">
        {data.houses.map((h) => (
          <li key={h.house} className="flex flex-col gap-1.5 border-b border-rule px-5 py-2.5 last:border-b-0 md:flex-row md:items-center md:gap-0">
            <div className="flex items-center gap-2 md:w-[210px] md:shrink-0">
              <span className="whitespace-nowrap text-[14px] font-bold leading-5 text-ink">{t("House {n}", { n: h.house })}</span>
              <span className="text-[13px] leading-4 text-soft">{tName(t, cap(h.sign))}</span>
              {h.active_now ? <Chip tone="accent" className="whitespace-nowrap">{t("Active now")}</Chip> : null}
            </div>
            <div
              role="img"
              aria-label={
                h.windows.length
                  ? t("House {n} is active {ranges}", { n: h.house, ranges: h.windows.map((w) => t("{a} to {b}", { a: f.full(w.starts_at), b: f.full(w.ends_at) })).join(", ") })
                  : t("House {n} has no double transit window", { n: h.house })
              }
              className="relative h-[22px] w-full rounded-[4px] bg-sidebar-wash md:w-auto md:flex-1"
            >
              {quarters.map((q, i) => (i > 0 && i < 8 ? <span key={q} className="absolute inset-y-0 w-px bg-rule" style={{ left: `${(i / 8) * 100}%` }} /> : null))}
              {h.windows.map((w) => (
                <span
                  key={w.starts_at}
                  title={t("{a} to {b}", { a: f.full(w.starts_at), b: f.full(w.ends_at) })}
                  className="absolute inset-y-[3px] rounded-[3px] bg-sindoor"
                  style={{ left: `${pos(w.starts_at)}%`, width: `${Math.max(0.8, pos(w.ends_at) - pos(w.starts_at))}%` }}
                />
              ))}
            </div>
            <span className="text-[12px] leading-4 text-soft md:w-[84px] md:shrink-0 md:text-right">
              {h.days ? t("{n} days", { n: h.days }) : t("None")}
            </span>
          </li>
        ))}
      </ul>
      <Proof text={data.proof} />
    </Panel>
  );
}

/* --------------------------------------------------------------------- root */

/** Transit depth for the Transits tab: gochara with bindus and vedha, lifetime Sade sati, double transit, and a what-if date. */
export function TransitDepth({ source }: { source: TransitDepthSource }) {
  const [date, setDate] = useState("");
  const onDate = useCallback((d: string) => setDate(d), []);
  return (
    <div className="flex flex-col gap-8" data-testid="transit-depth">
      <GocharaSection source={source} date={date} onDate={onDate} />
      <SadeSatiSection source={source} whatIf={date} />
      <DoubleTransitSection source={source} />
    </div>
  );
}

/** The tab wiring: live API when the chart is live, the offline engine in fixture mode. */
export function TransitDepthTab({ chartId, live, artifact }: { chartId: string; live: boolean; artifact: VedicChartArtifact }) {
  const source = useMemo(() => (live ? liveDepthSource(chartId) : lazyFixtureDepthSource(artifact)), [chartId, live, artifact]);
  return <TransitDepth source={source} />;
}
