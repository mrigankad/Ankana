"use client";

import { use, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import type { TransitEvent, TransitSnapshot } from "@astro/astrology-core";
import type { EnrichedPrediction, Remedy } from "@astro/rule-engine";

import { AskPanel } from "@/components/ankana/ask-panel";
import { ChartFrame } from "@/components/ankana/chart-frame";
import { ChartOverview } from "@/components/ankana/chart-overview";
import { AshtakavargaView } from "@/components/ankana/ashtakavarga-view";
import { DashasView } from "@/components/ankana/dasha-timeline";
import { PlanetsDepthView } from "@/components/ankana/planets-depth";
import { LalKitabView } from "@/components/ankana/lal-kitab-view";
import { Btn } from "@/components/ankana/ui";
import { ChartArtifactView } from "@/components/chart-artifact-view";
import { ChartAssistant } from "@/components/chart-assistant";
import { PredictionTimeline } from "@/components/prediction-timeline";
import { ReadingView } from "@/components/ankana/reading-view";
import { RemediesView, type ParashariRemedy } from "@/components/ankana/remedies-view";
import type { ChartReading } from "@/components/reading-panel";
import { TransitPanel } from "@/components/transit-panel";
import { TransitDepthTab } from "@/components/ankana/transit-depth";
import { TransitTimeline } from "@/components/ankana/transit-timeline";
import { ServerUnavailable } from "@/components/ankana/server-unavailable";
import { Skeleton } from "@/components/ui/skeleton";
import { api, getApiBaseUrl, isFixtures, mode } from "@/lib/api/client";
import { v1Api, type TransitTimelineV1 } from "@/lib/api/live";
import { problemMessage } from "@/lib/api/v1";
import { timelineFromCore } from "@/lib/api/fixture-transits";
import { fixtureReading } from "@/lib/api/fixture-reading";
import { askDashasFixture, buildHeader } from "@/lib/api/chart-views";
import type { ChartBundle } from "@/lib/api/types";
import { useT } from "@/lib/i18n/provider";

const ANCHOR_TAB: Record<string, string> = {
  planets: "planets",
  dashas: "dashas",
  yogas: "yogas",
  strengths: "strengths",
  vargas: "vargas",
  predictions: "predictions",
  remedies: "remedies",
  transits: "transits",
  reading: "reading",
  "your-life": "reading",
  panchang: "overview",
  "rashi-chart": "overview",
};

function tabForAnchor(anchor: string): string {
  if (ANCHOR_TAB[anchor]) return ANCHOR_TAB[anchor];
  if (anchor.startsWith("planet-")) return "planets";
  if (anchor.startsWith("dasha-")) return "dashas";
  if (anchor.startsWith("transit-")) return "transits";
  if (anchor.startsWith("yoga-")) return "yogas";
  return "overview";
}

const KNOWN_TABS = new Set([
  "overview", "reading", "planets", "dashas", "yogas", "strengths", "vargas", "lal-kitab", "remedies", "transits", "predictions",
]);

interface TransitData {
  snapshot: TransitSnapshot;
  timeline: TransitEvent[];
}

function Body({ children }: { children: ReactNode }) {
  return <div className="flex flex-col gap-5 px-4 py-[22px] sm:px-8 [&_.nk-cosmic]:hidden">{children}</div>;
}

export default function ChartPage({ params }: { params: Promise<{ jobId: string }> }) {
  const t = useT();
  const { jobId } = use(params);
  const [bundle, setBundle] = useState<ChartBundle | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("overview");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantFullscreen, setAssistantFullscreen] = useState(false);
  const [clientName, setClientName] = useState<string | null>(null);
  const [transits, setTransits] = useState<TransitData | null>(null);
  const [timeline, setTimeline] = useState<TransitTimelineV1 | null>(null);
  const [timelineError, setTimelineError] = useState("");
  const [predictions, setPredictions] = useState<EnrichedPrediction[] | null>(null);
  const [remedies, setRemedies] = useState<Remedy[] | null>(null);
  const [reused, setReused] = useState(false);
  const [reading, setReading] = useState<ChartReading | null>(null);
  const [readingError, setReadingError] = useState("");
  const [readingSample, setReadingSample] = useState(false);
  const [panelDown, setPanelDown] = useState<Record<string, boolean>>({});
  const [retry, setRetry] = useState(0);
  const [panelError, setPanelError] = useState("");

  // Initial URL state: ?tab=... and ?assistant=open
  useEffect(() => {
    try {
      const q = new URLSearchParams(window.location.search);
      const t = q.get("tab");
      if (t && KNOWN_TABS.has(t)) setTab(t);
      if (q.get("reused") === "1") setReused(true);
      const flag = q.get("assistant");
      if (flag === "open" || flag === "1" || flag === "true") setAssistantOpen(true);
    } catch {
      // ignore malformed URL
    }
  }, [jobId]);

  // Keep the URL in step with the tab and the assistant sheet.
  useEffect(() => {
    try {
      const url = new URL(window.location.href);
      if (tab === "overview") url.searchParams.delete("tab");
      else url.searchParams.set("tab", tab);
      if (assistantOpen) url.searchParams.set("assistant", "open");
      else url.searchParams.delete("assistant");
      const next = `${url.pathname}${url.search}${url.hash}`;
      const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      if (next !== current) window.history.replaceState(window.history.state, "", next);
    } catch {
      // ignore
    }
  }, [tab, assistantOpen]);

  useEffect(() => {
    const toggle = () => setAssistantOpen((open) => !open);
    window.addEventListener("nk:assistant", toggle);
    return () => window.removeEventListener("nk:assistant", toggle);
  }, []);

  useEffect(() => {
    if (!assistantOpen) setAssistantFullscreen(false);
  }, [assistantOpen]);

  // Chart bundle (typed api layer; fixtures fall back to the Ananya example).
  useEffect(() => {
    let cancelled = false;
    setBundle(null);
    setError("");
    setClientName(null);
    api
      .getChart(jobId)
      .then((b) => {
        if (!cancelled) setBundle(b);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Chart is not available.");
      });

    // Optional chrome: real client name when the live API knows this job.
    if (process.env.NEXT_PUBLIC_ANKANA_DATA === "legacy") {
      void (async () => {
        try {
          const job = await fetch(`${getApiBaseUrl()}/api/v1/charts/jobs/${jobId}`);
          if (!job.ok) return;
          const { clientId } = (await job.json()) as { clientId?: string };
          if (!clientId) return;
          const res = await fetch(`${getApiBaseUrl()}/api/v1/clients/${clientId}`);
          if (!res.ok) return;
          const c = (await res.json()) as { fullName?: string; preferredName?: string | null };
          const name = c.preferredName?.trim() || c.fullName?.trim();
          if (name && !cancelled) setClientName(name);
        } catch {
          // Name is optional chrome.
        }
      })();
    }
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  // Secondary panels load when their tab opens; the chart stays useful if they fail.
  const isLive = Boolean(bundle?.reading);
  useEffect(() => {
    if (!bundle) return;
    let cancelled = false;
    const ok = <T,>(p: Promise<T>, set: (v: T) => void, msg?: (e: unknown) => void) =>
      p.then((v) => !cancelled && set(v)).catch((e) => msg?.(e));
    if (isLive) {
      if (tab === "predictions" && !predictions) void ok(v1Api.getPredictions(jobId), (r) => setPredictions(r.predictions as EnrichedPrediction[]));
      if ((tab === "remedies") && !remedies) void ok(v1Api.getRemedies(jobId), (r) => setRemedies(r.remedies as Remedy[]), (e) => setPanelError(problemMessage(e)));
      if (tab === "transits" && !transits) void ok(v1Api.getTransits(jobId), (r) => setTransits({ snapshot: r.transits as TransitSnapshot, timeline: [] }), (e) => setPanelError(problemMessage(e)));
      if (tab === "transits" && !timeline) void ok(v1Api.getTransitTimeline(jobId, 12), setTimeline, (e) => setTimelineError(problemMessage(e)));
      if (tab === "reading" && !reading) setReading(bundle.reading ?? null);
      return () => {
        cancelled = true;
      };
    }
    const base = `${getApiBaseUrl()}/api/v1/charts/jobs/${jobId}`;
    async function get<T>(path: string): Promise<T | null> {
      try {
        const res = await fetch(`${base}${path}`);
        return res.ok ? ((await res.json()) as T) : null;
      } catch {
        return null;
      }
    }
    const fail = (key: string) => !cancelled && setPanelDown((d) => ({ ...d, [key]: true }));
    async function sampleTransits(): Promise<TransitData> {
      const core = await import("@astro/astrology-core");
      const now = new Date();
      return { snapshot: core.computeTransitSnapshot(bundle!.artifact, now), timeline: core.computeTransitTimeline(now, 2) };
    }
    if (tab === "predictions" && !predictions) {
      if (isFixtures())
        void import("@astro/rule-engine")
          .then((m) => m.evaluatePredictionsEnriched(bundle.artifact, { horizonYears: 5 }))
          .then((r) => !cancelled && setPredictions(r))
          .catch(() => fail("predictions"));
      else
        void get<{ predictions: EnrichedPrediction[] }>("/predictions?horizonYears=5").then((r) => {
          if (r && !cancelled) setPredictions(r.predictions);
          else fail("predictions");
        });
    }
    if (tab === "remedies" && !remedies) {
      void get<{ remedies: Remedy[] }>("/remedies").then((r) => {
        if (r && !cancelled) setRemedies(r.remedies);
      });
    }
    if (tab === "transits" && !transits) {
      const sample = () =>
        sampleTransits()
          .then((r) => !cancelled && setTransits(r))
          .catch(() => fail("transits"));
      if (isFixtures()) void sample();
      else
        void get<TransitData>("/transits?years=2").then((r) => {
          if (r && !cancelled) setTransits(r);
          else if (mode() === "auto") void sample();
          else fail("transits");
        });
    }
    if (tab === "reading" && !reading) {
      if (isFixtures()) {
        setReading(fixtureReading(bundle.artifact));
        setReadingSample(true);
        return;
      }
      void (async () => {
        const unavailable = () => {
          if (cancelled) return;
          if (mode() === "auto") {
            setReading(fixtureReading(bundle.artifact));
            setReadingSample(true);
          } else setReadingError("unavailable");
        };
        try {
          const res = await fetch(`${base}/reading`);
          if (res.ok) {
            const p = (await res.json()) as { reading: ChartReading };
            if (!cancelled) {
              setReading(p.reading);
              setReadingError("");
            }
          } else unavailable();
        } catch {
          unavailable();
        }
      })();
    }
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, jobId, bundle, retry]);

  const downloadReport = useCallback(async () => {
    if (!isFixtures() && bundle?.reading) {
      window.location.assign(`/charts/${jobId}/report`);
      return;
    }
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/v1/reports/${jobId}`, { method: "POST" });
      if (response.ok) window.open(`${getApiBaseUrl()}/api/v1/reports/${jobId}`, "_blank");
      else window.open(`/charts/${jobId}/print`, "_blank");
    } catch {
      window.open(`/charts/${jobId}/print`, "_blank");
    }
  }, [jobId, bundle]);

  const share = useCallback(() => {
    void navigator.clipboard?.writeText(window.location.href).catch(() => undefined);
  }, []);

  const revealEvidence = useCallback((anchor: string) => {
    setTab(tabForAnchor(anchor));
    window.setTimeout(() => {
      const el = document.getElementById(anchor);
      if (!el) return;
      el.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "center",
      });
      el.classList.add("nk-cite-flash");
      window.setTimeout(() => el.classList.remove("nk-cite-flash"), 2000);
    }, 60);
  }, []);

  const header = useMemo(() => {
    if (!bundle) return null;
    const h = buildHeader(bundle);
    return clientName ? { ...h, name: clientName } : h;
  }, [bundle, clientName]);

  const retryPanel = (key: string) => {
    setPanelDown((d) => ({ ...d, [key]: false }));
    setRetry((n) => n + 1);
  };

  const openAssistant = useCallback(() => setAssistantOpen(true), []);
  const lal = tab === "lal-kitab";
  const rem = tab === "remedies";
  const pad = lal || rem;

  const topRight = rem ? (
    <>
      <Btn variant="outline" href={`/charts/${jobId}/report`}>Preview as client</Btn>
      <Btn href={`/charts/${jobId}/report`}>Add plan to report</Btn>
    </>
  ) : lal ? (
    <>
      <span className="hidden items-center gap-[6px] rounded-full bg-sidebar-wash px-[10px] py-1 sm:flex">
        <span className="size-[6px] rounded-full bg-ok" />
        <span className="text-[13px] leading-4 text-body">{t("Lal Kitab engine · Gosvami 1952")}</span>
      </span>
      <Btn variant="outline" onClick={share}>{t("Share chart")}</Btn>
      <Btn href={`/charts/${jobId}/print`}>{t("Add to report")}</Btn>
    </>
  ) : (
    <>
      <Btn variant="outline" href={`/charts/${jobId}/print`} className="hidden sm:inline-flex">{t("Present to client")}</Btn>
      <Btn variant="outline" onClick={share} className="hidden sm:inline-flex">{t("Share")}</Btn>
      <Btn onClick={() => void downloadReport()}>{t("Export PDF")}</Btn>
    </>
  );

  if (!bundle || !header) {
    return (
      <main className="flex min-h-0 flex-1 flex-col" data-tab={tab}>
        <div className="flex flex-col gap-3 px-4 py-6 sm:px-8">
          {error ? (
            <p role="alert" className="nk-alert">
              {error}
            </p>
          ) : (
            <>
              <Skeleton className="h-10 w-64" />
              <Skeleton className="h-48 w-full" />
            </>
          )}
        </div>
      </main>
    );
  }

  const artifact = bundle.artifact;
  const ask = (
    <AskPanel
      key={tab}
      thread={tab === "dashas" ? askDashasFixture : bundle.asked}
      chartId={jobId}
      clientId={bundle.client.id}
      live={isLive}
      onRevealEvidence={revealEvidence}
      onOpenAssistant={openAssistant}
      className="h-full"
    />
  );

  let body: ReactNode;
  switch (tab) {
    case "overview":
      body = <ChartOverview bundle={bundle} onOpenTab={setTab} />;
      break;
    case "dashas":
      body = <DashasView bundle={bundle} chartId={jobId} live={isLive} onOpenPredictions={() => setTab("predictions")} />;
      break;
    case "planets":
      body = <PlanetsDepthView chartId={jobId} live={isLive} />;
      break;
    case "strengths":
      body = (
        <>
          <AshtakavargaView chartId={jobId} live={isLive} />
          <Body>
            <ChartArtifactView artifact={artifact} />
          </Body>
        </>
      );
      break;
    case "lal-kitab":
      body = <LalKitabView bundle={bundle} onOpenTab={setTab} />;
      break;
    case "reading":
      body = reading ? (
        <ReadingView reading={reading} clientFirstName={bundle.client.name.split(" ")[0]} sample={readingSample} />
      ) : readingError ? (
        <Body>
          <ServerUnavailable
            title="The deep reading is not available yet"
            onRetry={() => {
              setReadingError("");
              setBundle({ ...bundle });
            }}
          />
        </Body>
      ) : (
        <Body>
          <Skeleton className="h-48 w-full" />
        </Body>
      );
      break;
    case "remedies":
      body = (
        <>
          {panelError ? <p role="alert" className="nk-alert mx-8 mt-4">{panelError}</p> : null}
          <RemediesView bundle={bundle} parashari={remedies as unknown as ParashariRemedy[] | null} live={isLive} />
        </>
      );
      break;
    case "transits":
      body = (
        <Body>
          <TransitDepthTab chartId={jobId} live={isLive} artifact={artifact} />
          {panelError ? <p role="alert" className="nk-alert">{panelError}</p> : null}
          {transits ? (
            <TransitPanel snapshot={transits.snapshot} timeline={isLive ? transits.timeline : []} />
          ) : panelDown.transits ? (
            <ServerUnavailable onRetry={() => retryPanel("transits")} />
          ) : (
            <Skeleton className="h-48 w-full" />
          )}
          {!isLive && transits ? <TransitTimeline data={timelineFromCore(transits.snapshot, transits.timeline, jobId)} /> : null}
          {isLive ? (
            timeline ? (
              <TransitTimeline data={timeline} />
            ) : timelineError ? (
              <p role="alert" className="nk-alert">{timelineError}</p>
            ) : (
              <Skeleton className="h-64 w-full" />
            )
          ) : null}
        </Body>
      );
      break;
    case "predictions":
      body = (
        <Body>
          {predictions ? (
            <PredictionTimeline predictions={predictions} />
          ) : panelDown.predictions ? (
            <ServerUnavailable onRetry={() => retryPanel("predictions")} />
          ) : (
            <Skeleton className="h-48 w-full" />
          )}
        </Body>
      );
      break;
    default:
      // planets, yogas, strengths, vargas: the existing artifact view, one section per tab.
      body = (
        <Body>
          <ChartArtifactView artifact={artifact} />
        </Body>
      );
  }

  return (
    <main data-tab={tab} className="flex min-h-0 flex-1 flex-col">
      <ChartFrame
        crumbs={[
          { label: pad ? "Clients" : "Clients", href: "/clients" },
          { label: header.name, href: bundle.client.id && isLive ? `/clients/${bundle.client.id}` : undefined },
          { label: rem ? "Remedies" : lal ? "Lal Kitab" : "Birth chart" },
        ]}
        topRight={topRight}
        header={header}
        tab={tab === "predictions" ? "dashas" : tab}
        onTab={setTab}
        variant={pad ? "lalkitab" : "chart"}
        ask={pad ? undefined : ask}
        mobileAsk
      >
        {reused ? (
          <div role="status" className="mx-4 mt-4 flex items-center justify-between gap-3 rounded-[6px] bg-wash px-4 py-[10px] sm:mx-8">
            <span className="text-[14px] font-bold leading-[18px] text-accent-text">
              Existing chart reused. Same birth record and settings, so nothing was recalculated.
            </span>
            <button type="button" onClick={() => setReused(false)} className="text-[13px] font-bold leading-4 text-accent-text">
              Dismiss
            </button>
          </div>
        ) : null}
        {body}
      </ChartFrame>
      {isLive ? null : (
      <aside
        className="nk-assistant-dock"
        data-open={assistantOpen ? "true" : "false"}
        data-fullscreen={assistantFullscreen ? "true" : "false"}
        aria-label={t("Chart assistant panel")}
      >
        <ChartAssistant
          jobId={jobId}
          artifact={artifact}
          subject={{
            name: header.name,
            birthDate: artifact.calculationMetadata.input.birthDate,
            birthTime: artifact.calculationMetadata.input.birthTime,
            placeLabel: artifact.calculationMetadata.input.placeLabel,
          }}
          fullscreen={assistantFullscreen}
          onFullscreenChange={setAssistantFullscreen}
          onClose={() => setAssistantOpen(false)}
          onRevealEvidence={revealEvidence}
        />
      </aside>
      )}
    </main>
  );
}
