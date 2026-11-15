"use client";

import { useMemo, useState } from "react";

import { cn } from "@/lib/utils";
import { buildLalKitab, type LkHouseView } from "@/lib/api/chart-views";
import type { ChartBundle } from "@/lib/api/types";
import { useT } from "@/lib/i18n/provider";

const CARD_SHADOW = "0 1px 2px rgba(34,30,29,0.04), 0 6px 18px rgba(34,30,29,0.04)";

/** [left, top, width, height] of each house box inside the 440px Lal Kitab chart (Paper U08). */
const BOX: Record<number, [number, number, number, number]> = {
  1: [171, 71, 96, 76], 2: [61, 13, 96, 66], 3: [12, 84, 64, 52], 4: [62, 194, 96, 52], 5: [12, 304, 64, 52], 6: [61, 359, 96, 66],
  7: [171, 291, 96, 76], 8: [281, 361, 96, 60], 9: [358, 304, 64, 52], 10: [282, 194, 96, 52], 11: [357, 77, 64, 64], 12: [281, 13, 96, 66],
};

function Diamond({ size, className }: { size: number; className?: string }) {
  return <span className={cn("shrink-0 rotate-45 bg-sindoor", className)} style={{ width: size, height: size }} />;
}

function HouseBox({ h }: { h: LkHouseView }) {
  const t = useT();
  const [left, top, width, height] = BOX[h.house]!;
  const multi = h.planets.length > 1;
  return (
    <div className="absolute flex flex-col items-center justify-center gap-[2px]" style={{ left, top, width, height }}>
      <div className={cn("text-[11px] font-bold leading-[14px]", h.pakka ? "text-accent-text" : "text-soft")}>{h.house}</div>
      {h.planets.map((p) => {
        const dormant = p.state === "dormant";
        const big = h.house === 1 || h.house === 6;
        const small = multi || (width === 64 && dormant);
        const fs = big ? 17 : small ? 15 : 16;
        const sub = dormant ? (width === 64 ? p.sub.replace("wakes at", "wakes") : p.sub) : !multi && height >= 66 ? "awake" : "";
        return (
          <div key={p.key} className="flex flex-col items-center">
            <div className={cn("flex items-center", big ? "gap-[5px]" : "gap-1")}>
              {p.pakka ? <Diamond size={big ? 7 : 6} /> : null}
              {dormant ? <span className="size-[6px] shrink-0 rounded-full bg-[var(--warning)]" /> : null}
              <span className={cn("font-bold", dormant ? "text-soft" : "text-ink")} style={{ fontSize: fs, lineHeight: `${fs >= 16 ? 20 : 19}px` }}>
                {t(p.name)}
              </span>
            </div>
            {sub ? <span className={cn("text-[11px] leading-[14px]", dormant ? "text-soft" : "text-body")}>{sub}</span> : null}
          </div>
        );
      })}
    </div>
  );
}

function LkChart({ houses }: { houses: LkHouseView[] }) {
  return (
    <div className="max-w-full overflow-x-auto">
      <div className="relative h-[440px] w-[440px] shrink-0 rounded-[10px] border border-rule bg-wash-soft">
        <svg width="438" height="438" viewBox="0 0 440 440" className="absolute left-0 top-0" aria-hidden>
          <rect x="10" y="10" width="420" height="420" fill="none" stroke="var(--text-primary)" strokeWidth="1.5" />
          <path d="M10 10 L430 430 M430 10 L10 430" fill="none" stroke="var(--text-primary)" strokeWidth="1.2" />
          <path d="M220 10 L430 220 L220 430 L10 220 Z" fill="none" stroke="var(--text-primary)" strokeWidth="1.2" />
        </svg>
        {houses.map((h) => (
          <HouseBox key={h.house} h={h} />
        ))}
      </div>
    </div>
  );
}

function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("flex flex-col rounded-[10px] border border-rule bg-white", className)} style={{ boxShadow: CARD_SHADOW }}>
      {children}
    </div>
  );
}

/** Paper U08 Lal Kitab tab body. */
export function LalKitabView({ bundle, onOpenTab }: { bundle: ChartBundle; onOpenTab: (id: string) => void }) {
  const t = useT();
  const v = useMemo(() => buildLalKitab(bundle.lalKitab), [bundle.lalKitab]);
  const [origin, setOrigin] = useState("Origin: Lagna (book)");

  return (
    <div className="flex min-h-0 grow flex-col gap-6 px-4 py-5 @[1000px]:flex-row sm:px-8">
      <div className="flex w-full shrink-0 flex-col gap-3 @[1000px]:w-[464px]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-baseline gap-2">
            <div className="text-[18px] font-bold leading-6 text-ink">{t("Lal Kitab chart")}</div>
            <div className="deva text-[15px] leading-6 text-[color:var(--text-primary)]">लाल किताब</div>
          </div>
          <div className="flex rounded-full border border-rule p-[2px]">
            <button
              type="button"
              onClick={() => setOrigin("Origin: Lagna (book)")}
              className={cn("rounded-full px-3 py-1 text-[12px] leading-4", origin.startsWith("Origin") ? "bg-ink font-bold text-white" : "text-body")}
            >
              {t("Origin: Lagna (book)")}
            </button>
            <button
              type="button"
              disabled
              title={t("Aries as house 1 needs the live Lal Kitab engine")}
              className="rounded-full px-3 py-1 text-[12px] leading-4 text-body disabled:cursor-not-allowed"
            >
              {t("Aries")}
            </button>
          </div>
        </div>
        <LkChart houses={v.houses} />
        <div className="flex flex-wrap items-center gap-[14px]">
          <div className="flex items-center gap-[6px]">
            <Diamond size={8} />
            <span className="text-[12px] leading-4 text-body">{t("Pakka ghar")}</span>
          </div>
          <div className="flex items-center gap-[6px]">
            <span className="size-2 shrink-0 rounded-full bg-[var(--warning)]" />
            <span className="text-[12px] leading-4 text-body">{t("Dormant, needs review")}</span>
          </div>
          <span className="text-[12px] leading-4 text-soft">{t("Houses count from lagna. Book p.28")}</span>
        </div>
        <div className="flex flex-col gap-[6px] rounded-[10px] border border-rule px-4 py-3">
          <div className="text-[14px] font-bold leading-[18px] text-ink">{v.summary.title}</div>
          <div className="text-[13px] leading-[18px] text-body">{v.summary.body}</div>
        </div>
      </div>

      <div className="flex min-w-0 grow basis-0 flex-col gap-4">
        <Card>
          <div className="flex items-center justify-between px-5 pb-3 pt-4">
            <div className="flex items-baseline gap-2">
              <div className="text-[17px] font-bold leading-[22px] text-ink">{t("Debts found")}</div>
              <div className="text-[13px] leading-4 text-soft">
                {t("Rin")} · {t(v.rin.length === 1 ? "{n} indicator" : "{n} indicators", { n: v.rin.length })}
              </div>
            </div>
            <button type="button" onClick={() => onOpenTab("remedies")} className="text-[13px] font-bold leading-4 text-accent-text">
              {t("Add upay to plan")}
            </button>
          </div>
          {v.rin.length === 0 ? <div className="border-t border-rule px-5 py-[14px] text-[13px] leading-[18px] text-body">{t("No debts indicated in this chart.")}</div> : null}
          {v.rin.map((r) => (
            <div key={r.key} className="flex items-center gap-[14px] border-t border-rule px-5 py-[14px]">
              <span className={cn("size-2 shrink-0 rounded-full", r.first ? "bg-[var(--text-primary)]" : "bg-sindoor")} />
              <div className="flex min-w-0 grow basis-0 flex-col gap-[2px]">
                <div className="text-[14px] font-bold leading-[18px] text-ink">{r.title}</div>
                <div className="text-[13px] leading-[18px] text-body">{r.note}</div>
              </div>
              <span
                className={cn(
                  "shrink-0 rounded-full px-[9px] py-[2px] text-[12px] font-bold leading-4",
                  r.review ? "bg-wash text-accent-text" : "bg-ok-wash text-ok",
                )}
              >
                {r.review ? t("Needs review") : t("Checked")}
              </span>
              <span className="hidden w-16 shrink-0 text-right text-[12px] leading-4 text-accent-text sm:block">{r.cite}</span>
            </div>
          ))}
        </Card>

        <Card className="relative">
          <div className="flex items-baseline gap-2 px-5 pb-[10px] pt-4">
            <div className="text-[17px] font-bold leading-[22px] text-ink">{t("Artificial planets")}</div>
            <div className="text-[13px] leading-4 text-soft">{t("Masnui")} · {v.masnuiCount === 0 ? t("none formed") : t("{n} formed", { n: v.masnuiCount })}</div>
          </div>
          <div className="pb-4 pl-5 pr-[120px]">
            <div className="text-[13px] leading-[18px] text-body">
              {v.masnuiCount === 0
                ? t("The book's pairings were checked against this chart and none apply, so no artificial planet is added to the readings.")
                : t("The book's pairings apply to this chart, so artificial planets are added to the readings.")}
            </div>
          </div>
          <div
            className="absolute right-5 top-[14px] h-[76px] w-[76px] rounded-[10px] bg-cover bg-center"
            style={{ backgroundImage: "url(/illustrations/illus-lal-kitab@2x.png)" }}
            aria-hidden
          />
        </Card>

        <Card>
          <div className="flex items-center justify-between gap-2 px-5 pb-3 pt-4">
            <div className="flex min-w-0 items-baseline gap-2">
              <div className="whitespace-nowrap text-[17px] font-bold leading-[22px] text-ink">{t("Varshphal, year of life {age}", { age: v.varshphal.age })}</div>
              <div className="whitespace-nowrap text-[13px] leading-4 text-soft">{t("Natal house to annual house")}</div>
            </div>
            {v.varshphal.cycle ? <span className="shrink-0 whitespace-nowrap rounded-full bg-wash px-[9px] py-[2px] text-[12px] font-bold leading-4 text-accent-text">{v.varshphal.cycle}</span> : null}
          </div>
          <div className="flex gap-[6px] overflow-x-auto px-5 pb-[14px]">
            {v.varshphal.cells.map((c) => (
              <div key={c.planet} className={cn("flex min-w-[56px] grow basis-0 flex-col items-center gap-[2px] rounded-[6px] py-2", c.hot ? "bg-wash" : "bg-wash-soft")}>
                <div className="text-[12px] leading-4 text-body">{t(c.planet)}</div>
                <div className="text-[15px] font-bold leading-5 text-ink">{c.move}</div>
                <div className={cn("text-[11px] leading-[14px]", c.hot ? "text-accent-text" : "text-soft")}>{c.month}</div>
              </div>
            ))}
          </div>
          <div className="px-5 pb-4 text-[13px] leading-[18px] text-body">{v.varshphal.note}</div>
        </Card>
      </div>
    </div>
  );
}
