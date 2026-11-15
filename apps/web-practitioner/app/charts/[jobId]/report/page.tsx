"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useRef, useState } from "react";

import { Topbar } from "@/components/ankana/topbar";
import { PRIMARY_FILL, PRIMARY_SHADOW } from "@/components/ankana/ui";
import { cap, buildHouses, buildPlanetRows, buildDashaTimeline, currentDasha } from "@/lib/api/chart-views";
import { NorthChart } from "@/components/ankana/north-chart";
import { api, isFixtures } from "@/lib/api/client";
import { absoluteDownloadUrl, renderReport, v1Api, type BrandingV1, type ReportV1 } from "@/lib/api/live";
import { problemMessage } from "@/lib/api/v1";
import type { ChartBundle } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type SectionKey = "summary" | "kundali" | "planets" | "houses" | "yogas" | "dasha" | "vargas" | "panchang" | "reading" | "lal_kitab" | "remedies";

const SECTIONS: Array<{ key: SectionKey; label: string; lal?: boolean }> = [
  { key: "summary", label: "Cover and summary" },
  { key: "kundali", label: "Rashi chart" },
  { key: "houses", label: "Houses" },
  { key: "planets", label: "Planet positions" },
  { key: "dasha", label: "Dasha timeline" },
  { key: "reading", label: "Life reading" },
  { key: "yogas", label: "Yogas" },
  { key: "vargas", label: "Divisional charts" },
  { key: "panchang", label: "Panchang at birth" },
  { key: "lal_kitab", label: "Lal Kitab and debts", lal: true },
  { key: "remedies", label: "Remedy plan" },
];
const DEFAULTS: SectionKey[] = ["summary", "kundali", "planets", "houses", "yogas", "dasha", "panchang", "lal_kitab", "remedies"];

function Check({ on, label, onToggle, sub, lal }: { on: boolean; label: string; onToggle: () => void; sub?: string; lal?: boolean }) {
  return (
    <button type="button" role="checkbox" aria-checked={on} onClick={onToggle} className={cn("flex h-10 w-full items-center gap-[10px] rounded-[6px] px-3 text-left", on && sub === "active" && "bg-sidebar-wash")}>
      <span className={cn("flex size-[18px] shrink-0 items-center justify-center rounded-[5px] border", on ? "border-ink bg-ink" : "border-rule bg-white")}>
        {on ? (
          <svg width="11" height="11" viewBox="0 0 14 14" aria-hidden>
            <path d="M2.5 7.5L5.5 10.5L11.5 3.5" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ) : null}
      </span>
      {lal ? <span className="size-[6px] shrink-0 rounded-[2px] bg-alert" /> : null}
      <span className={cn("grow text-[14px] leading-[18px]", on ? "text-ink" : "text-soft")}>{label}</span>
    </button>
  );
}

function Switch({ on, label, onToggle }: { on: boolean; label: string; onToggle: () => void }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={onToggle} className="flex w-full items-center justify-between bg-transparent p-0 text-left">
      <span className="text-[14px] leading-[18px] text-ink">{label}</span>
      <span className={cn("flex h-[22px] w-[38px] shrink-0 items-center rounded-[8px] px-[3px]", on ? "justify-end bg-ink" : "justify-start bg-chip")}>
        <span className="size-4 rounded-full bg-white" />
      </span>
    </button>
  );
}

/** One A4 page showing the selected section from the chart itself. */
function PagePreview({ bundle, section, branding, language }: { bundle: ChartBundle; section: SectionKey; branding: BrandingV1 | null; language: "en" | "hi" }) {
  const a = bundle.artifact;
  const practice = branding?.name || "Your practice";
  const planets = useMemo(() => buildPlanetRows(a).slice(0, 9), [a]);
  const houses = useMemo(() => buildHouses(a), [a]);
  const { maha, antar } = currentDasha(a);
  const title = SECTIONS.find((s) => s.key === section)?.label ?? "";
  const lk = bundle.lalKitab as { rin?: Array<{ kind?: string; planet?: string; house?: number }>; remedies?: { upay?: Array<{ title: string; action: string; durationDays?: number }> } };

  let content: React.ReactNode;
  if (section === "kundali") content = <div className="flex justify-center py-2"><NorthChart houses={houses} ascLabel="Asc" size={300} /></div>;
  else if (section === "planets")
    content = (
      <table className="w-full border-collapse text-[11px] leading-4">
        <tbody>
          {planets.map((p) => (
            <tr key={p.key} className="border-t border-rule">
              <td className="py-[5px] pr-2 font-bold text-ink">{p.label}</td>
              <td className="py-[5px] text-body">{p.signName}</td>
              <td className="py-[5px] text-right text-body">House {p.house}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  else if (section === "dasha")
    content = (
      <p className="m-0 text-[12px] leading-[18px] text-body">
        Running period: {maha ? cap(maha.planet) : "n/a"}
        {antar ? ` / ${cap(antar.planet)}` : ""}. {a.vimshottari.mahadashas.slice(0, 6).map((m) => `${cap(m.planet)} ${m.start.slice(0, 4)} to ${m.end.slice(0, 4)}`).join(", ")}.
      </p>
    );
  else if (section === "lal_kitab")
    content = (
      <div className="flex flex-col gap-2">
        {(lk.rin ?? []).slice(0, 3).map((r, i) => (
          <div key={i} className="border-t border-rule pt-[6px] text-[11px] leading-4 text-body">
            <b className="text-ink">{r.kind}</b>, {cap(r.planet ?? "")} in house {r.house}
          </div>
        ))}
      </div>
    );
  else if (section === "remedies")
    content = (
      <div className="flex flex-col gap-2">
        {(lk.remedies?.upay ?? []).slice(0, 3).map((u, i) => (
          <div key={i} className="border-t border-rule pt-[6px] text-[11px] leading-4 text-body">
            <b className="text-ink">{i + 1}. {u.title}</b>
            <div>{u.action}</div>
          </div>
        ))}
      </div>
    );
  else
    content = (
      <p className="m-0 text-[12px] leading-[18px] text-body">
        {section === "summary"
          ? `${a.ascendant.signName} lagna, Moon in ${a.planets.find((p) => p.planet === "moon")?.nakshatra}. Born ${a.calculationMetadata.input.birthDate} in ${(a.calculationMetadata.input.placeLabel ?? "").split(",")[0]}.`
          : "This section is rendered in full in the PDF."}
      </p>
    );

  return (
    <div className="flex aspect-[210/297] w-full max-w-[500px] flex-col gap-[14px] bg-white px-[38px] py-[34px] shadow-[0_2px_4px_rgba(34,30,29,0.06),0_16px_40px_rgba(34,30,29,0.10)]" aria-label="A4 page preview">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {branding?.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={branding.logo_url} alt="" className="size-[26px] rounded-[4px] object-contain" />
          ) : (
            <span className="flex size-[26px] items-center justify-center rounded-[4px] bg-ink">
              <span className="size-2 rotate-45 bg-accent-light" />
            </span>
          )}
          <span className="text-[15px] font-bold leading-5 text-ink">{practice}</span>
        </div>
        <span className="text-[9px] leading-3 text-soft">{new Date().toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</span>
      </div>
      <div>
        <div className="text-[22px] font-bold leading-7 tracking-[-0.01em] text-ink">{language === "hi" ? `${title} (हिन्दी)` : title}</div>
        <div className="text-[10px] leading-[14px] text-body">Prepared for {bundle.client.name} · {a.ascendant.signName} lagna</div>
      </div>
      {content}
      <div className="mt-auto flex justify-between border-t border-rule pt-2 text-[9px] leading-3 text-soft">
        <span>{branding?.brand_footer || "Advisory only. Traditional practice, not a prediction or prescription."}</span>
      </div>
    </div>
  );
}

export default function ReportPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const [bundle, setBundle] = useState<ChartBundle | null>(null);
  const [error, setError] = useState("");
  const [picked, setPicked] = useState<Set<SectionKey>>(new Set(DEFAULTS));
  const [focus, setFocus] = useState<SectionKey>("summary");
  const [language, setLanguage] = useState<"en" | "hi">("en");
  const [branding, setBranding] = useState<BrandingV1 | null>(null);
  const [report, setReport] = useState<ReportV1 | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    api.getChart(jobId).then(setBundle).catch((e) => setError(problemMessage(e, "This chart could not be loaded.")));
    if (!isFixtures()) v1Api.getBranding().then(setBranding).catch(() => undefined);
    return () => abort.current?.abort();
  }, [jobId]);

  const ordered = SECTIONS.filter((s) => picked.has(s.key));
  const toggle = (k: SectionKey) =>
    setPicked((p) => {
      const n = new Set(p);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });

  async function exportPdf() {
    if (isFixtures()) {
      window.open(`/charts/${jobId}/print`, "_blank");
      return;
    }
    setBusy(true);
    setError("");
    setReport(null);
    abort.current = new AbortController();
    try {
      const done = await renderReport({ chart_id: jobId, language, sections: ordered.map((s) => s.key) }, setReport, { signal: abort.current.signal });
      setReport(done);
      if (done.status === "failed") setError(done.error ? `The report could not be rendered: ${done.error}` : "The report could not be rendered.");
      else if (done.download_url) window.open(absoluteDownloadUrl(done.download_url), "_blank");
    } catch (cause) {
      setError(problemMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  const url = report?.download_url ? absoluteDownloadUrl(report.download_url) : "";
  const idx = Math.max(0, ordered.findIndex((s) => s.key === focus));
  const statusLabel = busy ? (report?.status === "running" ? "Rendering the PDF" : "Queued") : "";

  return (
    <>
      <Topbar
        crumbs={[{ label: "Clients", href: "/clients" }, { label: bundle?.client.name ?? "Chart", href: bundle ? `/charts/${jobId}` : undefined }, { label: "Report export" }]}
        right={<span className="hidden items-center gap-[6px] rounded-full bg-sidebar-wash px-[12px] py-1 sm:flex"><span className="size-[6px] rounded-full bg-ok" /><span className="text-[13px] leading-4 text-body">Template: Standard, {ordered.length} sections</span></span>}
      />
      <main className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <aside className="flex shrink-0 flex-col gap-3 border-b border-rule p-5 lg:w-[264px] lg:border-b-0 lg:border-r" aria-label="Sections">
          <div>
            <h1 className="m-0 text-[20px] font-bold leading-6 tracking-[-0.01em] text-ink">Report for {bundle?.client.name ?? "client"}</h1>
            <div className="text-[13px] leading-4 text-soft">{ordered.length} of {SECTIONS.length} sections included</div>
          </div>
          <div className="flex flex-col">
            {SECTIONS.map((s) => (
              <Check key={s.key} on={picked.has(s.key)} label={s.label} lal={s.lal} sub={focus === s.key ? "active" : ""} onToggle={() => { toggle(s.key); setFocus(s.key); }} />
            ))}
          </div>
          <p className="m-0 mt-auto text-[12px] leading-4 text-soft">Sections print in the order shown. Pages renumber on export.</p>
        </aside>

        <section className="flex min-w-0 grow basis-0 flex-col items-center gap-[14px] bg-sidebar-wash px-5 py-5" aria-label="Preview">
          <div className="text-[13px] leading-4 text-soft">
            <b className="text-ink">Page {idx + 1} of {Math.max(ordered.length, 1)}</b> &nbsp; A4 preview · {language === "en" ? "English" : "Hindi"}
          </div>
          {bundle ? <PagePreview bundle={bundle} section={ordered[idx]?.key ?? "summary"} branding={branding} language={language} /> : <div className="h-[520px] w-full max-w-[500px] animate-pulse bg-white" />}
        </section>

        <aside className="flex shrink-0 flex-col gap-4 border-t border-rule p-5 lg:w-[300px] lg:border-l lg:border-t-0" aria-label="Options">
          <h2 className="m-0 text-[20px] font-bold leading-6 tracking-[-0.01em] text-ink">Options</h2>
          <div className="flex flex-col gap-[6px]">
            <div className="text-[13px] font-bold leading-4 text-body">Language</div>
            <div role="radiogroup" aria-label="Report language" className="flex rounded-[6px] border border-rule p-[3px]">
              {(["en", "hi"] as const).map((l) => (
                <button key={l} type="button" role="radio" aria-checked={language === l} onClick={() => setLanguage(l)} className={cn("h-[34px] grow basis-0 rounded-[5px] text-[14px] leading-[18px]", language === l ? "bg-ink font-bold text-white" : "text-body")}>
                  {l === "en" ? "English" : "हिन्दी"}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-3">
            <div className="text-[13px] font-bold leading-4 text-body">Include</div>
            <Switch on={picked.has("lal_kitab")} label="Lal Kitab module" onToggle={() => toggle("lal_kitab")} />
            <Switch on={picked.has("remedies")} label="Remedies with schedule" onToggle={() => toggle("remedies")} />
            <Switch on={picked.has("reading")} label="Life reading" onToggle={() => toggle("reading")} />
          </div>
          <div className="flex flex-col gap-[6px]">
            <div className="text-[13px] font-bold leading-4 text-body">Branding</div>
            <Link href="/settings/branding" className="flex items-center gap-3 rounded-[8px] border border-rule p-3 no-underline">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-[5px] bg-ink">
                <span className="size-[10px] rotate-45 bg-accent-light" />
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[14px] font-bold leading-[18px] text-ink">{branding?.name ?? "Your practice"}</span>
                <span className="truncate text-[12px] leading-4 text-soft">Logo, colours, footer. Edit in settings.</span>
              </span>
            </Link>
          </div>
          <div className="rounded-[8px] bg-wash px-[14px] py-3 text-[13px] leading-[18px] text-accent-text">Every page carries an advisory only line.</div>

          <div className="mt-auto flex flex-col gap-[10px]">
            {error ? (
              <p role="alert" className="m-0 rounded-[6px] bg-alert-wash px-3 py-2 text-[13px] font-bold leading-[18px] text-alert">
                {error}
              </p>
            ) : null}
            {statusLabel ? (
              <p role="status" className="m-0 flex items-center gap-2 rounded-[6px] bg-wash px-3 py-2 text-[13px] font-bold leading-4 text-accent-text">
                <span className="size-[6px] animate-pulse rounded-full bg-sindoor" />
                {statusLabel}
              </p>
            ) : null}
            <button
              type="button"
              onClick={() => void exportPdf()}
              disabled={busy || !ordered.length || !bundle}
              className="h-[52px] rounded-xl text-[16px] font-bold leading-5 text-white disabled:opacity-50"
              style={{ backgroundColor: "var(--accent)", backgroundImage: PRIMARY_FILL, boxShadow: PRIMARY_SHADOW }}
            >
              {busy ? "Preparing PDF" : `Export PDF, ${ordered.length} sections`}
            </button>
            {url ? (
              <div className="flex items-center justify-between gap-2 rounded-[6px] border border-rule px-3 py-[10px]">
                <a href={url} target="_blank" rel="noreferrer" className="truncate text-[13px] font-bold leading-4 text-ink">Download PDF</a>
                <button
                  type="button"
                  className="shrink-0 text-[13px] font-bold leading-4 text-accent-text"
                  onClick={() => {
                    void navigator.clipboard?.writeText(url).then(() => setCopied(true));
                  }}
                >
                  {copied ? "Copied" : "Copy link"}
                </button>
              </div>
            ) : null}
            {url ? <p className="m-0 text-[12px] leading-4 text-soft">The signed link expires in {Math.round((report?.download_expires_in ?? 900) / 60)} minutes. Export again for a fresh one.</p> : null}
          </div>
        </aside>
      </main>
    </>
  );
}
