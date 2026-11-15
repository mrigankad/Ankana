"use client";

import { useMemo, useState } from "react";

import { Segmented } from "@/components/ankana/ask-panel";
import { cn } from "@/lib/utils";
import {
  buildDashaTimeline,
  buildWhyPeriod,
  cap,
  type DashaTimelineView,
} from "@/lib/api/chart-views";
import type { ChartBundle } from "@/lib/api/types";
import { useT } from "@/lib/i18n/provider";

import { DashaDrillDown } from "./dasha-drill";

const GOLD = "var(--fill-primary)";

/** Proportional dasha bar: width is years, labels mark where each period ends (Paper U06). */
export function DashaBar({ view }: { view: DashaTimelineView }) {
  const n = view.segments.length;
  const gaps = (n - 1) * 2;
  const markerLeft = `calc(${view.todayFraction} * (100% - ${gaps}px) + ${view.todayIndex * 2}px)`;
  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-[560px] flex-col">
        <div className="relative h-5">
          <span
            className="absolute top-0 -translate-x-1/2 whitespace-pre rounded-full px-[9px] py-[3px] text-[12px] font-bold leading-[14px] text-white"
            style={{ left: markerLeft, backgroundImage: GOLD }}
          >
            {view.todayLabel}
          </span>
        </div>
        <div className="relative h-2 shrink-0">
          <span className="absolute top-0 h-2 w-[2px] -translate-x-1/2 bg-sindoor" style={{ left: markerLeft }} />
        </div>
        <div className="flex h-11 shrink-0 gap-[2px]">
          {view.segments.map((s, i) => {
            const skip = s.years < 5;
            return (
              <div
                key={s.planet + i}
                className={cn(
                  "flex min-w-0 items-center justify-center",
                  i === 0 && "rounded-l-lg",
                  i === n - 1 && "rounded-r-lg",
                  s.state === "now" ? "text-white" : s.state === "past" ? "bg-rule text-soft" : "bg-sidebar-wash text-body",
                )}
                style={{ flex: `${s.years} 1 0`, backgroundImage: s.state === "now" ? GOLD : undefined }}
              >
                {skip ? null : <span className={cn("truncate font-bold leading-4", s.years < 9 ? "text-[12px]" : "text-[13px]")}>{s.label}</span>}
              </div>
            );
          })}
        </div>
        <div className="flex gap-[2px] pt-2">
          {view.segments.map((s, i) => (
            <div key={s.planet + i} className="flex min-w-0 justify-end" style={{ flex: `${s.years} 1 0` }}>
              <span className={cn("whitespace-pre text-[12px] leading-4", s.state === "now" ? "font-bold text-accent-text" : "text-soft")}>{s.endYear}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CiteRows({ items }: { items: Array<{ n: number; source: string; detail: string }> }) {
  return (
    <div className="flex flex-col gap-[6px]">
      {items.map((c) => (
        <div key={c.n} className="flex gap-2 rounded-[6px] bg-white px-[10px] py-[7px]">
          <span className="text-[12px] font-bold leading-4 text-accent-text">{c.n}</span>
          <span className="text-[12px] leading-4 text-body">
            {c.source} · {c.detail}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Paper U06 Dashas tab body. */
export function DashasView({ bundle, chartId, live, onOpenPredictions }: { bundle: ChartBundle; chartId: string; live: boolean; onOpenPredictions?: () => void }) {
  const a = bundle.artifact;
  const t = useT();
  const [system, setSystem] = useState("Vimshottari");
  const now = useMemo(() => new Date(), []);
  const birth = useMemo(() => {
    const i = a.calculationMetadata.input;
    return new Date(a.calculationMetadata.utcDateTime ?? `${i.birthDate}T${i.birthTime}:00Z`);
  }, [a]);

  const vim = useMemo(() => buildDashaTimeline(a.vimshottari.mahadashas, birth, a.vimshottari.balanceYears, now), [a, birth, now]);
  const yog = useMemo(
    () => (a.yoginiDasha ? buildDashaTimeline(a.yoginiDasha.mahadashas, birth, a.yoginiDasha.balanceYears, now) : null),
    [a, birth, now],
  );
  const why = useMemo(() => buildWhyPeriod(a, now), [a, now]);

  const yogini = system === "Yogini" && yog;
  const view = yogini ? yog : vim;
  const balanceNote = yogini
    ? t("Yogini balance at birth was {years} years ({yogini}).", { years: a.yoginiDasha!.balanceYears.toFixed(2), yogini: a.yoginiDasha!.birthYogini })
    : t("{planet} balance at birth was {years} years.", { planet: t(cap(a.vimshottari.birthLord)), years: a.vimshottari.balanceYears.toFixed(2) });

  return (
    <div className="flex min-h-0 grow flex-col gap-[18px] px-4 py-[22px] sm:px-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-[20px] font-bold leading-6 tracking-[-0.01em] text-ink">{yogini ? t("Yogini dasha") : t("Vimshottari dasha")}</h2>
        <Segmented
          items={["Vimshottari", "Yogini", "Lal Kitab 35-yr"]}
          active={system}
          onChange={setSystem}
          className="[&>button]:px-3 [&>button]:py-[5px] [&>button]:text-[13px] [&>button]:leading-4"
        />
      </div>

      {system === "Lal Kitab 35-yr" ? (
        <LalKitabCycle bundle={bundle} />
      ) : (
        <div className="flex flex-col rounded-[10px] border border-rule px-4 pb-[14px] pt-4">
          <DashaBar view={view} />
          <div className="flex items-start justify-between gap-4 pt-[10px]">
            <div className="text-[12px] leading-4 text-soft">{t("Width is years, labels mark where each period ends.")} {balanceNote}</div>
            {onOpenPredictions ? (
              <button type="button" onClick={onOpenPredictions} className="shrink-0 text-[12px] font-bold leading-4 text-accent-text">
                {t("Predictions")}
              </button>
            ) : null}
          </div>
        </div>
      )}

      {system !== "Lal Kitab 35-yr" ? (
        <DashaDrillDown chartId={chartId} live={live} system={yogini ? "yogini" : "vimshottari"} timeZone={a.calculationMetadata.input.timezoneName} />
      ) : null}

      <div className="flex min-w-0 flex-col gap-3 self-stretch rounded-[10px] bg-wash-soft px-[18px] py-4">
        <div className="text-[12px] font-bold leading-4 tracking-[0.06em] text-accent-text">{t("WHY THIS PERIOD")}</div>
        <p className="m-0 text-[14px] leading-[21px] text-ink">
          {why.segments.map((seg, i) => (
            <span key={i}>
              {seg.text}
              {seg.cite ? <span className="font-bold text-accent-text">[{seg.cite}]</span> : null}
            </span>
          ))}
        </p>
        <CiteRows items={why.citations} />
      </div>
    </div>
  );
}

function LalKitabCycle({ bundle }: { bundle: ChartBundle }) {
  const t = useT();
  const c = (bundle.lalKitab.varshphal as { age: number; cycle35?: { rotation?: number; yearInCycle?: number; cyclePlanet?: string; part?: string } }) ?? null;
  const cyc = c?.cycle35;
  return (
    <div className="flex flex-col gap-[6px] rounded-[10px] border border-rule px-4 py-4">
      <div className="text-[15px] font-bold leading-5 text-ink">
        {t("Lal Kitab 35-year cycle, year {year} of 35", { year: cyc?.yearInCycle ?? c?.age ?? "" })}
      </div>
      <div className="text-[13px] leading-[18px] text-body">
        {t("Cycle {n}, {planet} part. Advisory only, needs review.", { n: cyc?.rotation ?? 1, planet: t(cap(cyc?.cyclePlanet ?? "")) })}
      </div>
    </div>
  );
}
