"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ClientFormDialog } from "@/components/ankana/client-form-dialog";
import { ClientTableRow, FilterPill } from "@/components/ankana/client-table";
import { Topbar } from "@/components/ankana/topbar";
import { Btn, Panel } from "@/components/ankana/ui";
import { Select } from "@/components/ui/select";
import { mode } from "@/lib/api/client";
import { v1Api, type ClientFacetsV1, type ClientRowV1, type ClientSort } from "@/lib/api/live";
import { clientRowFromV1 } from "@/lib/api/live-views";
import { problemMessage } from "@/lib/api/v1";
import { useT } from "@/lib/i18n/provider";

type Filter = { kind: "all" } | { kind: "tag"; tag: string } | { kind: "rectify" } | { kind: "followUp" };

const SHOWN_TAGS = 3;

/** Clients on live /v1: server search, tag and status filters, sort, cursor pagination, create. */
export function LiveClients({ onUnreachable }: { onUnreachable: () => void }) {
  const t = useT();
  const [rows, setRows] = useState<ClientRowV1[] | null>(null);
  const [facets, setFacets] = useState<ClientFacetsV1 | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>({ kind: "all" });
  const [sort, setSort] = useState<ClientSort>("recent");
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const [dialog, setDialog] = useState(false);
  const seq = useRef(0);

  const params = useCallback(
    (q: string, f: Filter, s: ClientSort) => ({
      q,
      limit: 25,
      sort: s,
      tag: f.kind === "tag" ? f.tag : undefined,
      needsRectify: f.kind === "rectify",
      followUpDue: f.kind === "followUp",
    }),
    [],
  );

  const load = useCallback(
    async (q: string, f: Filter, s: ClientSort) => {
      const mine = ++seq.current;
      try {
        const page = await v1Api.listClients(params(q, f, s));
        if (mine !== seq.current) return;
        setRows(page.clients);
        setFacets(page.facets);
        setCursor(page.next_cursor);
        setError("");
      } catch (cause) {
        if (mine !== seq.current) return;
        if (cause instanceof TypeError && mode() === "auto") return onUnreachable();
        setRows([]);
        setError(problemMessage(cause));
      }
    },
    [onUnreachable, params],
  );

  useEffect(() => {
    const timer = setTimeout(() => void load(query, filter, sort), query ? 300 : 0);
    return () => clearTimeout(timer);
  }, [query, filter, sort, load]);

  async function more() {
    if (!cursor) return;
    setLoadingMore(true);
    try {
      const page = await v1Api.listClients({ ...params(query, filter, sort), cursor });
      setRows((r) => [...(r ?? []), ...page.clients]);
      setCursor(page.next_cursor);
    } catch (cause) {
      setError(problemMessage(cause));
    } finally {
      setLoadingMore(false);
    }
  }

  const tags = facets?.tags ?? [];
  const pinned = tags.slice(0, SHOWN_TAGS);
  const rest = tags.slice(SHOWN_TAGS);
  const activeTag = filter.kind === "tag" ? filter.tag : "";
  const filtered = filter.kind !== "all" || query !== "";
  const table = (rows ?? []).map((c) => clientRowFromV1(c));

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
              {facets ? ` ${t("{n} follow-ups are due this week.", { n: facets.follow_up_due })}` : ""}
            </p>
          </div>
          <div className="flex gap-2">
            <Btn variant="outline" onClick={() => setDialog(true)}>
              {t("New client")}
            </Btn>
            <Btn href="/clients/new">{t("+ New chart")}</Btn>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-[10px]">
          <label className="flex w-full shrink-0 items-center gap-2 rounded-[6px] border border-rule bg-white px-3 py-[9px] sm:w-[300px]">
            <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden className="shrink-0 text-soft">
              <circle cx="6" cy="6" r="4.2" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M9.2 9.2L12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <input
              aria-label={t("Search clients")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("Search by name")}
              className="min-w-0 grow border-0 bg-transparent text-[14px] leading-[18px] text-ink outline-none placeholder:text-soft"
            />
          </label>
          <FilterPill active={filter.kind === "all"} onClick={() => setFilter({ kind: "all" })}>
            {t("All")} {facets?.total ?? ""}
          </FilterPill>
          {pinned.map((x) => (
            <FilterPill key={x.tag} active={activeTag === x.tag} onClick={() => setFilter({ kind: "tag", tag: x.tag })}>
              {t(x.tag)} {x.count}
            </FilterPill>
          ))}
          {rest.length ? (
            <Select
              aria-label={t("More tags")}
              className="h-[34px] w-[150px] text-[13px]"
              value={rest.some((x) => x.tag === activeTag) ? activeTag : ""}
              onValueChange={(v) => setFilter(v ? { kind: "tag", tag: v } : { kind: "all" })}
              placeholder={t("More tags")}
              options={[{ value: "", label: t("More tags") }, ...rest.map((x) => ({ value: x.tag, label: `${x.tag} ${x.count}` }))]}
            />
          ) : null}
          <FilterPill active={filter.kind === "rectify"} onClick={() => setFilter({ kind: "rectify" })}>
            {t("Needs rectify")} {facets?.needs_rectify ?? ""}
          </FilterPill>
          <FilterPill active={filter.kind === "followUp"} onClick={() => setFilter({ kind: "followUp" })}>
            {t("Follow-up due")} {facets?.follow_up_due ?? ""}
          </FilterPill>
          <div className="grow" />
          <div className="flex items-center gap-[8px]">
            <span className="text-[13px] leading-4 text-soft">{t("Sort by")}</span>
            <Select
              aria-label={t("Sort by")}
              className="h-[34px] w-[170px] text-[13px] font-bold"
              value={sort}
              onValueChange={(v) => setSort(v as ClientSort)}
              options={[
                { value: "recent", label: t("Newest first") },
                { value: "name", label: t("Name") },
                { value: "follow_up", label: t("Next follow-up") },
                { value: "last_consult", label: t("Last consult") },
              ]}
            />
          </div>
        </div>

        {error ? (
          <p role="alert" className="m-0 rounded-[6px] bg-alert-wash px-[14px] py-[10px] text-[14px] font-bold leading-[18px] text-alert">
            {error}
          </p>
        ) : null}

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
              {table.map((c, i) => (
                <ClientTableRow key={c.id} c={c} index={i} highlight={false} />
              ))}
              {rows === null ? <div className="px-5 py-8 text-[14px] text-body">{t("Loading clients")}</div> : null}
              {rows && rows.length === 0 && !error ? (
                <div className="flex flex-col items-start gap-3 px-5 py-8 text-[14px] text-body">
                  <span>{filtered ? t("No clients match that filter.") : t("No clients yet. Start with a first chart.")}</span>
                  {!filtered ? <Btn href="/clients/new">{t("+ New chart")}</Btn> : null}
                </div>
              ) : null}
            </div>
          </div>
        </Panel>
        {cursor ? (
          <div className="flex justify-center">
            <Btn variant="outline" onClick={() => void more()} disabled={loadingMore}>
              {loadingMore ? t("Loading") : t("Load more")}
            </Btn>
          </div>
        ) : null}
      </main>
      <ClientFormDialog open={dialog} onOpenChange={setDialog} onSaved={() => void load(query, filter, sort)} />
    </>
  );
}
