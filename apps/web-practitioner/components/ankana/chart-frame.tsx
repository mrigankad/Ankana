"use client";

import type { ReactNode } from "react";

import { Topbar, type Crumb } from "@/components/ankana/topbar";
import { cn } from "@/lib/utils";
import type { ChartHeaderView } from "@/lib/api/chart-views";
import { useT } from "@/lib/i18n/provider";

export const CHART_TABS = [
  ["overview", "Overview"],
  ["reading", "Reading"],
  ["planets", "Planets"],
  ["dashas", "Dashas"],
  ["yogas", "Yogas"],
  ["strengths", "Strengths"],
  ["vargas", "Vargas"],
  ["lal-kitab", "Lal Kitab"],
  ["remedies", "Remedies"],
  ["transits", "Transits"],
] as const;

export type ChartTabId = (typeof CHART_TABS)[number][0] | "predictions";

function TabLink({
  id,
  label,
  active,
  variant,
  onSelect,
}: {
  id: string;
  label: string;
  active: boolean;
  variant: "line" | "pad";
  onSelect: (id: string) => void;
}) {
  const t = useT();
  const lal = variant === "pad" && id === "lal-kitab" && active;
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={() => onSelect(id)}
      className={cn(
        "flex shrink-0 items-center whitespace-nowrap text-[14px] leading-[18px]",
        variant === "line"
          ? active
            ? "border-b-2 border-sindoor pb-[11px] font-bold text-ink"
            : "pb-3 text-body hover:text-ink"
          : active
            ? "gap-[7px] border-b-2 border-sindoor px-[14px] py-2 font-bold text-ink"
            : "px-[14px] pb-[10px] pt-2 text-body hover:text-ink",
      )}
    >
      {lal ? <span className="size-[7px] shrink-0 rounded-[2px] bg-[var(--text-primary)]" /> : null}
      {t(label)}
    </button>
  );
}

function Avatar({ initials, size }: { initials: string; size: 40 | 44 }) {
  return (
    <div
      className={cn("flex shrink-0 items-center justify-center rounded-full bg-wash font-bold text-accent-text", size === 40 ? "size-10 text-[15px] leading-[18px]" : "size-11 text-[16px] leading-5")}
    >
      {initials}
    </div>
  );
}

/**
 * Chart workspace frame: topbar, chart header, tab bar, tab body and the optional Ask column.
 * `variant="lalkitab"` is the Paper U08 header (title line, status pills, padded tabs).
 */
export function ChartFrame({
  crumbs,
  topRight,
  header,
  tab,
  onTab,
  variant = "chart",
  ask,
  mobileAsk,
  children,
}: {
  crumbs: Crumb[];
  topRight?: ReactNode;
  header: ChartHeaderView;
  tab: string;
  onTab: (id: string) => void;
  variant?: "chart" | "lalkitab";
  /** Right-hand Ask column on wide screens; stacked below the body when narrow. */
  ask?: ReactNode;
  mobileAsk?: boolean;
  children: ReactNode;
}) {
  const lal = variant === "lalkitab";
  const t = useT();
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Topbar crumbs={crumbs} right={topRight} />
      <div className="flex min-h-0 flex-1 flex-col xl:flex-row">
        <div className="flex min-w-0 flex-1 flex-col @container">
          {lal ? (
            <div className="flex shrink-0 flex-col gap-[14px] border-b border-rule px-4 pt-[18px] sm:px-8">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-[14px]">
                  <Avatar initials={header.initials} size={44} />
                  <div className="flex min-w-0 flex-col gap-[2px]">
                    <h1 className="m-0 text-[22px] font-bold leading-7 tracking-[-0.01em] text-ink">{header.name}</h1>
                    <div className="text-[14px] leading-[18px] text-body">
                      {header.lagna} · {header.dasha} · {t("Born")} {header.birthLine} · {t("Age")} {header.ageYears}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-wash px-[10px] py-[3px] text-[12px] font-bold leading-4 text-accent-text">{t("Birth time verified")}</span>
                  <span className="rounded-full bg-sidebar-wash px-[10px] py-[3px] text-[12px] leading-4 text-body">{t("Advisory only")}</span>
                </div>
              </div>
              <div className="nk-scroll -mx-4 flex gap-[2px] overflow-x-auto px-4 sm:-mx-8 sm:px-8" role="tablist" aria-label={t("Chart sections")}>
                {CHART_TABS.map(([id, label]) => (
                  <TabLink key={id} id={id} label={label} active={tab === id} variant="pad" onSelect={onTab} />
                ))}
              </div>
            </div>
          ) : (
            <>
              <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 px-4 pt-[18px] sm:px-8">
                <div className="flex items-center gap-[14px]">
                  <Avatar initials={header.initials} size={40} />
                  <div className="flex min-w-0 flex-col gap-[2px]">
                    <h1 className="m-0 text-[22px] font-bold leading-[26px] tracking-[-0.01em] text-ink">{header.name}</h1>
                    <div className="text-[13px] leading-4 text-soft">{header.birthLine}</div>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-sidebar-wash px-[11px] py-[5px] text-[13px] font-bold leading-4 text-ink">{header.lagna}</span>
                  <span className="rounded-full bg-sidebar-wash px-[11px] py-[5px] text-[13px] font-bold leading-4 text-ink">{header.moon}</span>
                  <span className="rounded-full bg-wash px-[11px] py-[5px] text-[13px] font-bold leading-4 text-accent-text">{header.dasha}</span>
                </div>
              </div>
              <div
                className="nk-scroll mt-[14px] flex h-[38px] shrink-0 items-end gap-[22px] overflow-x-auto border-b border-rule px-4 sm:px-8"
                role="tablist"
                aria-label={t("Chart sections")}
              >
                {CHART_TABS.map(([id, label]) => (
                  <TabLink key={id} id={id} label={label} active={tab === id} variant="line" onSelect={onTab} />
                ))}
              </div>
            </>
          )}
          <div className="flex min-h-0 grow flex-col">{children}</div>
          {ask && mobileAsk ? <div className="h-[560px] shrink-0 border-t border-rule xl:hidden">{ask}</div> : null}
        </div>
        {ask ? (
          <aside className="hidden w-[340px] shrink-0 border-l border-rule xl:block" aria-label={t("Ask about this chart")}>
            <div className="sticky top-0 flex h-[calc(100svh-48px-45px)] min-h-[560px] flex-col">{ask}</div>
          </aside>
        ) : null}
      </div>
    </div>
  );
}
