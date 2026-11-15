"use client";

import { depthApi } from "@/lib/api/depth";
import { ashtakavargaView, type CellTone } from "@/lib/api/depth-views";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { DepthBody, DepthFailed, DepthLoading, useDepthData } from "./depth-shell";
import { ProofValue } from "./proof-drawer";

const CELL: Record<CellTone, string> = {
  high: "bg-ok-wash font-bold text-ok",
  low: "bg-alert-wash font-bold text-alert",
  mid: "text-ink",
};

function Swatch({ tone, label, hint }: { tone: CellTone; label: string; hint: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-[13px] leading-[18px] text-body">
      <span className={cn("inline-flex h-6 min-w-6 items-center justify-center rounded-[4px] px-1 text-[12px]", CELL[tone] === "text-ink" ? "bg-sidebar-wash text-ink" : CELL[tone])}>{label}</span>
      {hint}
    </span>
  );
}

/** Strengths tab, ashtakavarga part: seven bhinna grids and the sarva grid, 12 sign columns with totals. */
export function AshtakavargaView({ chartId, live }: { chartId: string; live: boolean }) {
  const t = useT();
  const { data, failed, retry } = useDepthData(() => depthApi.ashtakavarga(chartId, live), `${chartId}:${live}`);

  if (failed) return <DepthBody><DepthFailed onRetry={retry} /></DepthBody>;
  if (!data) return <DepthBody><DepthLoading rows={4} /></DepthBody>;

  const v = ashtakavargaView(data, t);
  const th = data.thresholds;
  const names = (list: Array<{ name: string; value: number }>) => list.map((s) => `${s.name} ${s.value}`).join(", ");

  return (
    <DepthBody>
      <div id="ashtakavarga" className="flex flex-col gap-1">
        <h2 className="m-0 text-[20px] font-bold leading-6 tracking-[-0.01em] text-ink">{t("Ashtakavarga")}</h2>
        <p className="m-0 text-[14px] leading-5 text-body">
          {t("Bindus each planet gives to the twelve signs, and their sum. Select any number to see which planets gave it.")}
        </p>
      </div>

      <div className="overflow-x-auto rounded-[10px] border border-rule">
        <table className="w-full min-w-[760px] border-collapse text-center" aria-label={t("Ashtakavarga grids")}>
          <thead>
            <tr className="bg-sidebar-wash">
              <th scope="col" className="sticky left-0 z-[1] w-[92px] bg-sidebar-wash px-3 py-2 text-left text-[12px] font-bold leading-4 text-soft">
                {t("Sign")}
              </th>
              {v.columns.map((c) => (
                <th key={c.sign} scope="col" className="px-1 py-2 text-[12px] font-bold leading-4 text-ink" title={c.name}>
                  <div>{c.abbr}</div>
                  <div className={cn("font-normal", c.isLagna ? "text-accent-text" : "text-soft")}>{c.isLagna ? t("Lagna") : `H${c.house}`}</div>
                </th>
              ))}
              <th scope="col" className="w-[64px] px-3 py-2 text-right text-[12px] font-bold leading-4 text-soft">{t("Total")}</th>
            </tr>
          </thead>
          <tbody>
            {v.rows.map((row) => (
              <tr key={row.id} className={cn("border-t border-rule", row.isSarva && "border-t-2 border-t-rule-strong bg-wash-soft")}>
                <th scope="row" className={cn("sticky left-0 z-[1] px-3 py-[6px] text-left text-[14px] font-bold leading-[18px] text-ink", row.isSarva ? "bg-wash-soft" : "bg-surface")}>
                  {row.label}
                </th>
                {row.cells.map((c) => (
                  <td key={c.sign} className="p-[3px]">
                    <ProofValue
                      proof={c.proof}
                      className={cn("flex h-8 w-full min-w-8 items-center justify-center rounded-[4px] text-[14px] leading-[18px] no-underline", CELL[c.tone], row.isSarva && "text-[15px]")}
                      title={`${row.label} ${c.proof.title}`}
                    >
                      {c.value}
                    </ProofValue>
                  </td>
                ))}
                <td className="px-3 py-[6px] text-right">
                  <ProofValue proof={row.totalProof} className="text-[14px] font-bold leading-[18px] text-ink">{row.total}</ProofValue>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2" aria-label={t("Colour legend")}>
        <Swatch tone="high" label={`${th.sarva_high}+`} hint={t("Sarva {n} or more: strong sign", { n: th.sarva_high })} />
        <Swatch tone="low" label={`${th.sarva_low}-`} hint={t("Sarva {n} or fewer: weak sign", { n: th.sarva_low })} />
        <Swatch tone="high" label={`${th.bhinna_high}+`} hint={t("Planet row {n} or more", { n: th.bhinna_high })} />
        <Swatch tone="low" label={`${th.bhinna_low}-`} hint={t("Planet row {n} or fewer", { n: th.bhinna_low })} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-[10px] bg-ok-wash px-4 py-3">
          <div className="text-[12px] font-bold leading-4 text-ok">{t("Strongest signs")}</div>
          <div className="text-[14px] leading-5 text-ink">{v.strongest.length ? names(v.strongest) : t("None at or above {n}", { n: th.sarva_high })}</div>
        </div>
        <div className="rounded-[10px] bg-alert-wash px-4 py-3">
          <div className="text-[12px] font-bold leading-4 text-alert">{t("Weakest signs")}</div>
          <div className="text-[14px] leading-5 text-ink">{v.weakest.length ? names(v.weakest) : t("None at or below {n}", { n: th.sarva_low })}</div>
        </div>
      </div>
    </DepthBody>
  );
}
