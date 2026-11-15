"use client";

import { useEffect, useMemo, useState } from "react";

import { Topbar } from "@/components/ankana/topbar";
import { ClientTableRow, FilterPill } from "@/components/ankana/client-table";
import { Btn, Panel } from "@/components/ankana/ui";
import { LiveClients } from "@/components/ankana/live-clients";
import { api, isFixtures } from "@/lib/api/client";
import { clientFacets, filterClients, type ClientFilter } from "@/lib/api/clients";
import type { ClientRow, WorkspaceMeta } from "@/lib/api/types";
import { useT } from "@/lib/i18n/provider";

function FixtureClients() {
  const t = useT();
  const [rows, setRows] = useState<ClientRow[] | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceMeta | null>(null);
  const [filter, setFilter] = useState<ClientFilter>("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.listClients().then(setRows).catch(() => setRows([]));
    api.getWorkspace().then(setWorkspace).catch(() => undefined);
  }, []);

  const facets = useMemo(() => (rows ? clientFacets(rows, workspace) : null), [rows, workspace]);
  const visible = useMemo(() => (rows ? filterClients(rows, filter, query) : []), [rows, filter, query]);

  return (
    <>
      <Topbar crumbs={[{ label: "Clients" }]} />
      <main className="flex flex-1 flex-col gap-5 px-5 py-8 lg:px-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <div className="flex items-baseline gap-[10px]">
              <h1 className="m-0 text-[28px] font-bold leading-[34px] tracking-[-0.02em] text-ink lg:text-[32px] lg:leading-[38px]">{t("Clients")}</h1>
              <span className="text-[15px] leading-[18px] text-soft">{facets ? t("{n} people", { n: facets.total }) : ""}</span>
            </div>
            <p className="m-0 text-[15px] leading-5 text-body">
              {t("Every chart is computed once and kept with the person.")}
              {facets ? ` ${t("{n} follow-ups are due this week.", { n: facets.followUp })}` : ""}
            </p>
          </div>
          <button
            type="button"
            className="flex shrink-0 items-center gap-2 rounded-[6px] border border-rule bg-white px-[14px] py-[9px] text-[14px] font-bold leading-[18px] text-ink"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden className="shrink-0">
              <path d="M8 2v8M5 7l3 3 3-3M3 13h10" fill="none" stroke="var(--text-primary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {t("Import from Jagannatha Hora")}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-[10px]">
          <label className="flex w-full shrink-0 items-center gap-2 rounded-[6px] border border-rule bg-white px-3 py-[9px] sm:w-[300px]">
            <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden className="shrink-0">
              <circle cx="6" cy="6" r="4.2" fill="none" stroke="var(--text-soft)" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M9.2 9.2L12 12" fill="none" stroke="var(--text-soft)" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <input
              aria-label={t("Search clients")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("Search name, place, lagna")}
              className="min-w-0 grow border-0 bg-transparent text-[14px] leading-[18px] text-ink outline-none placeholder:text-soft"
            />
          </label>
          <FilterPill active={filter === "all"} onClick={() => setFilter("all")}>
            {t("All")} {facets?.total ?? ""}
          </FilterPill>
          <FilterPill active={filter === "lalKitab"} onClick={() => setFilter("lalKitab")}>
            {t("Lal Kitab")} {facets?.lalKitab ?? ""}
          </FilterPill>
          <FilterPill active={filter === "matching"} onClick={() => setFilter("matching")}>
            {t("Matching")} {facets?.matching ?? ""}
          </FilterPill>
          <FilterPill active={filter === "rectify"} onClick={() => setFilter("rectify")}>
            {t("Needs rectify")} {facets?.rectify ?? ""}
          </FilterPill>
          <FilterPill active={filter === "followUp"} onClick={() => setFilter("followUp")}>
            {t("Follow-up due")} {facets?.followUp ?? ""}
          </FilterPill>
          <div className="grow" />
          <div className="flex items-center gap-[6px]">
            <span className="text-[13px] leading-4 text-soft">{t("Sort by")}</span>
            <span className="text-[13px] font-bold leading-4 text-ink">{t("Next follow-up")}</span>
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden className="shrink-0">
              <path d="M3 4.5L6 7.5L9 4.5" fill="none" stroke="var(--text-primary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>

        <Panel className="overflow-clip">
          <div className="overflow-x-auto">
            <div className="md:min-w-[1010px]">
              <div className="hidden h-[38px] items-center border-b border-rule bg-sidebar-wash px-5 md:flex text-[12px] font-bold leading-4 text-soft">
                <div className="w-[300px] shrink-0">{t("CLIENT")}</div>
                <div className="w-[140px] shrink-0">{t("LAGNA")}</div>
                <div className="w-[190px] shrink-0">{t("CURRENT DASHA")}</div>
                <div className="w-[120px] shrink-0">{t("LAST CONSULT")}</div>
                <div className="w-[140px] shrink-0">{t("NEXT FOLLOW-UP")}</div>
                <div className="grow">{t("TAGS")}</div>
              </div>
              {visible.map((c, i) => (
                <ClientTableRow key={c.id} c={c} index={i} highlight={i === 0 && filter === "all" && !query} />
              ))}
              {rows && visible.length === 0 ? (
                <div className="flex flex-col items-start gap-3 px-5 py-8 text-[14px] text-body">
                  <span>{query || filter !== "all" ? t("No clients match that filter.") : t("No clients yet. Start with a first chart.")}</span>
                  {!query && filter === "all" ? <Btn href="/clients/new">{t("+ New chart")}</Btn> : null}
                </div>
              ) : null}
            </div>
          </div>
        </Panel>
      </main>
    </>
  );
}

export default function ClientsPage() {
  const [fallback, setFallback] = useState(false);
  if (isFixtures() || fallback) return <FixtureClients />;
  return <LiveClients onUnreachable={() => setFallback(true)} />;
}
