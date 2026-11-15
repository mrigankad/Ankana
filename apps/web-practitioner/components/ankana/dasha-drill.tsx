"use client";

import { useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { depthApi, type DashasDepth, type DashaSystem } from "@/lib/api/depth";
import { applyAsOf, currentLine, dashaRows, runningKeys, type DashaRow } from "@/lib/api/depth-views";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { DepthBody, DepthFailed, DepthLoading, useDepthData } from "./depth-shell";
import { ProofValue } from "./proof-drawer";

/** Each level steps in by this many px; the label column shrinks by the same so dates line up. */
const STEP = 20;

function Row({ row, onToggle }: { row: DashaRow; onToggle: (key: string) => void }) {
  const t = useT();
  const now = row.state === "current";
  return (
    <div
      role="treeitem"
      aria-level={row.level + 1}
      aria-expanded={row.hasChildren ? row.open : undefined}
      aria-current={now ? "date" : undefined}
      data-state={row.state}
      className={cn(
        "flex min-h-11 items-center gap-2 border-b border-rule px-3 py-[6px] last:border-b-0",
        now ? "bg-wash" : row.state === "past" ? "opacity-70" : "",
      )}
    >
      <span className="shrink-0" style={{ width: row.level * STEP }} aria-hidden />
      <span className="flex size-7 shrink-0 items-center justify-center">
        {row.hasChildren ? (
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label={`${row.open ? t("Collapse") : t("Expand")} ${row.label}`}
            onClick={() => onToggle(row.key)}
          >
            <ChevronRight className={cn("transition-transform motion-reduce:transition-none", row.open && "rotate-90")} aria-hidden />
          </Button>
        ) : null}
      </span>
      <div className="flex min-w-0 grow flex-wrap items-baseline gap-x-4 gap-y-[2px]">
        <span
          className={cn("shrink-0 truncate text-[14px] leading-[18px]", row.level === 0 ? "font-bold text-ink" : "font-semibold text-ink")}
          style={{ width: 132 - row.level * STEP }}
        >
          <ProofValue proof={row.proof} className="text-inherit no-underline hover:underline">{row.label}</ProofValue>
        </span>
        <span className="text-[13px] leading-[18px] text-body">{row.range}</span>
        <span className="text-[12px] leading-4 text-soft">{row.span}</span>
      </div>
      {now ? <span className="shrink-0 rounded-[4px] bg-hl-wash px-[7px] py-[2px] text-[12px] font-bold leading-4 text-accent-text">{t("Now")}</span> : null}
    </div>
  );
}

function Tree({ data, timeZone }: { data: DashasDepth; timeZone?: string }) {
  const t = useT();
  const nodes = useMemo(() => applyAsOf(data.mahadashas, new Date()), [data]);
  const running = useMemo(() => runningKeys(nodes), [nodes]);
  const marked = useMemo(() => ({ ...data, mahadashas: nodes }), [data, nodes]);
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set(running));

  const rows = dashaRows(marked, expanded, t, timeZone);
  const toggle = (key: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const levels = data.rule.levels === 3 ? t("Maha, antar and pratyantar dasha with exact dates.") : t("Maha and antar dasha with exact dates. The Yogini system has no deeper level.");
  const current = currentLine(marked, t);

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="m-0 text-[14px] leading-5 text-body">{levels}</p>
          {current ? (
            <p className="m-0 text-[14px] leading-5 text-ink">
              {t("Running now")}: <span className="font-bold">{current}</span>
            </p>
          ) : null}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setExpanded(new Set(running))}>{t("Show running period")}</Button>
          <Button variant="outline" size="sm" onClick={() => setExpanded(new Set())}>{t("Collapse all")}</Button>
        </div>
      </div>
      <div role="tree" aria-label={t("Dasha periods")} className="overflow-hidden rounded-[10px] border border-rule bg-surface">
        {rows.map((row) => (
          <Row key={row.key} row={row} onToggle={toggle} />
        ))}
      </div>
    </>
  );
}

/** Dasha drill-down: maha, antar, pratyantar with exact dates, running period marked, rows open to their proof. */
export function DashaDrillDown({ chartId, live, system, timeZone }: { chartId: string; live: boolean; system: DashaSystem; timeZone?: string }) {
  const { data, failed, retry } = useDepthData(() => depthApi.dashas(chartId, system, live), `${chartId}:${live}:${system}`);
  if (failed) return <DepthBody bare><DepthFailed onRetry={retry} /></DepthBody>;
  if (!data) return <DepthBody bare><DepthLoading rows={6} /></DepthBody>;
  return (
    <DepthBody bare>
      <Tree key={`${data.system}`} data={data} timeZone={timeZone} />
    </DepthBody>
  );
}
