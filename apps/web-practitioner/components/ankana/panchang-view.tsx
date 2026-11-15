"use client";

import { useEffect, useState } from "react";

import { PageHeader } from "@/components/ankana/page-header";
import { SampleBadge, ServerUnavailable } from "@/components/ankana/server-unavailable";
import { Eyebrow, Panel } from "@/components/ankana/ui";
import { Topbar } from "@/components/ankana/topbar";
import { api, mode } from "@/lib/api/client";
import type { TodayView } from "@/lib/api/types";
import { useT } from "@/lib/i18n/provider";

function Fact({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <Panel className="flex flex-col gap-1 p-4">
      <Eyebrow>{label}</Eyebrow>
      <div className="text-[20px] font-bold leading-6 text-ink">{value}</div>
      <div className="text-[13px] leading-4 text-body">{note}</div>
    </Panel>
  );
}

/** Panchang and muhurta: today's five limbs, the windows to avoid, and the sky this week. */
export function PanchangView() {
  const t = useT();
  const [today, setToday] = useState<TodayView | null>(null);
  const [failed, setFailed] = useState(false);
  const [n, setN] = useState(0);
  useEffect(() => {
    setFailed(false);
    api.getToday().then(setToday).catch(() => setFailed(true));
  }, [n]);
  const sample = mode() !== "live";
  const p = today?.panchang;

  return (
    <>
      <Topbar crumbs={[{ label: "Panchang & muhurta" }]} />
      <main className="flex flex-1 flex-col gap-7 px-5 py-8 lg:px-10 lg:py-9">
        <PageHeader
          title={t("Panchang & muhurta")}
          subtitle={t("Today's five limbs, the windows to avoid, and what the sky does this week.")}
          badge={sample ? <SampleBadge /> : undefined}
        />
        {failed ? <ServerUnavailable onRetry={() => setN((x) => x + 1)} /> : null}
        {p ? (
          <>
            <section className="flex flex-col gap-3" aria-label={t("Today")}>
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">{t("Today")}</h2>
                <span className="text-[13px] leading-4 text-soft">{today?.practitioner.practice}</span>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
                <Fact label={t("VARA")} value={p.vara} note={p.varaDeva} />
                <Fact label={t("TITHI")} value={p.tithi.name} note={p.tithi.until} />
                <Fact label={t("NAKSHATRA")} value={p.nakshatra.name} note={p.nakshatra.until} />
                <Fact label={t("SUNRISE")} value={p.sunrise} note={t("Local time")} />
              </div>
            </section>

            <section className="flex flex-col gap-3" aria-label={t("Muhurta windows")}>
              <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">{t("Muhurta windows")}</h2>
              <Panel className="flex flex-col">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-rule px-5 py-4">
                  <span className="size-[8px] shrink-0 rounded-full bg-alert" aria-hidden />
                  <span className="min-w-[96px] text-[15px] font-bold leading-5 text-ink">{t("Rahu kaal")}</span>
                  <span className="text-[15px] leading-5 text-ink">{p.rahuKaal.range}</span>
                  <span className="text-[13px] leading-4 text-body">{p.rahuKaal.note}</span>
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-4">
                  <span className="size-[8px] shrink-0 rounded-full bg-sindoor" aria-hidden />
                  <span className="min-w-[96px] text-[15px] font-bold leading-5 text-ink">{t("Next ingress")}</span>
                  <span className="text-[15px] leading-5 text-ink">{p.ingress?.title ?? t("None soon")}</span>
                  <span className="text-[13px] leading-4 text-body">{p.ingress?.note ?? ""}</span>
                </div>
              </Panel>
            </section>

            <section className="flex flex-col gap-3" aria-label={t("Sky this week")}>
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">{t("Sky this week")}</h2>
                <span className="text-[13px] leading-4 text-soft">{t("Clients touched")}</span>
              </div>
              <Panel className="flex flex-col">
                {(today?.sky ?? []).map((s, i, all) => (
                  <div key={s.title} className={`flex items-center gap-4 px-5 py-3 ${i < all.length - 1 ? "border-b border-rule" : ""}`}>
                    <span className="w-[60px] shrink-0 text-[13px] leading-4 text-soft">{s.date}</span>
                    <span className="grow text-[15px] font-bold leading-5 text-ink">{s.title}</span>
                    <span className="text-[14px] leading-4 text-ink">{s.touched}</span>
                  </div>
                ))}
              </Panel>
            </section>
          </>
        ) : failed ? null : (
          <div className="h-48 animate-pulse rounded-[10px] bg-sidebar-wash motion-reduce:animate-none" aria-hidden />
        )}
      </main>
    </>
  );
}
