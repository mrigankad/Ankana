"use client";

import { useMemo, useState } from "react";

import { NorthChart, SouthChart } from "@/components/ankana/north-chart";
import { Segmented } from "@/components/ankana/ask-panel";
import { cn } from "@/lib/utils";
import {
  buildHouses,
  buildPanchang,
  buildPlanetRows,
  buildWorthRaising,
  fmtDeg,
} from "@/lib/api/chart-views";
import { tName } from "@/lib/i18n/translate";
import type { ChartBundle } from "@/lib/api/types";
import { useT } from "@/lib/i18n/provider";

const PILL = {
  accent: "bg-wash text-accent-text",
  ok: "bg-ok-wash text-ok",
  alert: "bg-alert-wash text-alert",
  muted: "bg-sidebar-wash text-body",
} as const;

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 grow basis-0 flex-col gap-[2px]">
      <div className="text-[12px] leading-4 text-soft">{label}</div>
      <div className="text-[15px] font-bold leading-5 text-ink">{value}</div>
    </div>
  );
}

/** Paper U05 overview body: rashi chart + birth panchang on the left, planets table on the right. */
export function ChartOverview({ bundle, onOpenTab }: { bundle: ChartBundle; onOpenTab: (id: string) => void }) {
  const a = bundle.artifact;
  const t = useT();
  const [style, setStyle] = useState<"North" | "South">("North");
  const houses = useMemo(() => buildHouses(a), [a]);
  const rows = useMemo(() => buildPlanetRows(a), [a]);
  const panchang = useMemo(() => buildPanchang(a), [a]);
  const worth = useMemo(() => buildWorthRaising(a), [a]);
  const lagnaSignNumber = a.ascendant.signIndex + 1;

  return (
    <div className="flex min-h-0 grow flex-col gap-7 px-4 py-[22px] @[800px]:flex-row sm:px-8">
      <div className="flex w-full shrink-0 flex-col gap-[14px] @[800px]:w-[372px]">
        <div className="flex items-center justify-between">
          <div className="text-[16px] font-bold leading-5 text-ink">
            {t("Rashi chart")} <span className="font-normal text-soft">D1</span>
          </div>
          <Segmented items={["North", "South"]} active={style} onChange={(v) => setStyle(v as "North" | "South")} />
        </div>
        <div className="flex justify-center @[800px]:justify-start">
          {style === "North" ? (
            <NorthChart houses={houses} ascLabel={`Asc ${fmtDeg(a.ascendant.degreesInSign, a.ascendant.signIndex, false)}`} />
          ) : (
            <SouthChart houses={houses} lagnaSign={a.ascendant.signIndex} />
          )}
        </div>
        <div className="flex items-center gap-[14px]">
          <div className="text-[12px] leading-4 text-soft">
            {style === "North" ? t("Small numbers are signs, {n} is {sign}", { n: lagnaSignNumber, sign: t(a.ascendant.signName) }) : t("Signs are fixed, lagna sign shaded")}
          </div>
          <div className="text-[12px] font-bold leading-4 text-sindoor">{t("Lagna house in sindoor")}</div>
        </div>
        <div className="flex flex-col gap-[10px] rounded-[10px] border border-rule px-4 py-[14px]">
          <div className="text-[12px] font-bold leading-4 tracking-[0.06em] text-accent-text">{t("BIRTH PANCHANG")}</div>
          <div className="flex gap-[10px]">
            <Fact label={t("Tithi")} value={panchang.tithi} />
            <Fact label={t("Vara")} value={panchang.vara} />
          </div>
          <div className="flex gap-[10px]">
            <Fact label={t("Nakshatra")} value={panchang.nakshatra} />
            <Fact label={t("Yoga")} value={panchang.yoga} />
          </div>
        </div>
      </div>

      <div className="flex min-w-0 grow basis-0 flex-col">
        <div className="flex items-center justify-between pb-3">
          <div className="text-[16px] font-bold leading-5 text-ink">
            {t("Planets")} <span className="font-normal text-soft">{a.calculationMetadata.ayanamsa.name === "lahiri" ? t("Lahiri, sidereal") : t("Sidereal")}</span>
          </div>
          <button type="button" onClick={() => onOpenTab("planets")} className="text-[13px] font-bold leading-4 text-accent-text">
            {t("Open Planets tab")}
          </button>
        </div>
        <div className="flex items-center border-b border-rule py-2 text-[12px] font-bold leading-4 text-soft">
          <div className="w-[84px] shrink-0">{t("Planet")}</div>
          <div className="w-[84px] shrink-0">{t("Degree")}</div>
          <div className="grow basis-0">{t("Nakshatra")}</div>
          <div className="w-[74px] shrink-0 text-right">{t("Dignity")}</div>
        </div>
        {rows.map((r) => (
          <div key={r.key} className="flex h-11 shrink-0 items-center border-b border-rule">
            <div className="w-[84px] shrink-0 text-[14px] font-bold leading-[18px] text-ink">{t(r.label)}</div>
            <div className="w-[84px] shrink-0 text-[14px] leading-[18px] text-body">{r.degree}</div>
            <div className="min-w-0 grow basis-0 text-[14px] leading-[18px] text-body">{tName(t, r.nakshatra)}</div>
            <div className="flex w-[74px] shrink-0 justify-end">
              <span className={cn("shrink-0 whitespace-pre rounded-full px-[9px] py-[3px] text-[12px] font-bold leading-[14px]", PILL[r.chip.tone])}>{t(r.chip.label)}</span>
            </div>
          </div>
        ))}
        <div className="mt-4 flex flex-col gap-[6px] rounded-[10px] bg-wash-soft px-4 py-[14px]">
          <div className="text-[12px] font-bold leading-4 tracking-[0.06em] text-accent-text">{t("WORTH RAISING FIRST")}</div>
          <div className="text-[14px] leading-5 text-ink">{worth}</div>
        </div>
      </div>
    </div>
  );
}
