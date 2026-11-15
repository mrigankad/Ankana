"use client";

import { use, useEffect, useState } from "react";
import type { VedicChartArtifact } from "@astro/astrology-core";
import type { EnrichedPrediction, Remedy } from "@astro/rule-engine";

import {
  ChartReportDocument,
  type ChartReportSubject,
} from "@/components/chart-report-document";
import { ServerUnavailable } from "@/components/ankana/server-unavailable";
import { api } from "@/lib/api/client";
import { fixtureReading } from "@/lib/api/fixture-reading";
import { v1Api } from "@/lib/api/live";
import type { ChartReading, LifeStory } from "@/components/reading-panel";

/** Print-optimized report page rendered by the PDF pipeline. */
export default function ChartPrintPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = use(params);
  const [artifact, setArtifact] = useState<VedicChartArtifact | null>(null);
  const [subject, setSubject] = useState<ChartReportSubject | null>(null);
  const [reading, setReading] = useState<ChartReading | null>(null);
  const [lifeStory, setLifeStory] = useState<LifeStory | null>(null);
  const [predictions, setPredictions] = useState<EnrichedPrediction[]>([]);
  const [remedies, setRemedies] = useState<Remedy[]>([]);
  const [generatedAt, setGeneratedAt] = useState("");
  const [ready, setReady] = useState(false);

  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setFailed(false);
      try {
        const bundle = await api.getChart(jobId);
        if (cancelled) return;
        const live = Boolean(bundle.reading);
        let nextPredictions: EnrichedPrediction[] = [];
        let nextRemedies: Remedy[] = [];
        if (live) {
          const [p, r] = await Promise.all([
            v1Api.getPredictions(jobId).catch(() => null),
            v1Api.getRemedies(jobId).catch(() => null),
          ]);
          nextPredictions = (p?.predictions ?? []) as EnrichedPrediction[];
          nextRemedies = (r?.remedies ?? []) as Remedy[];
        }
        if (cancelled) return;
        const reading = bundle.reading ?? fixtureReading(bundle.artifact);
        const input = bundle.artifact.calculationMetadata.input;
        setArtifact(bundle.artifact);
        setPredictions(nextPredictions);
        setRemedies(nextRemedies);
        setReading(reading);
        setLifeStory((reading as ChartReading & { lifeStory?: LifeStory }).lifeStory ?? null);
        setSubject({
          name: bundle.client.name || "Client",
          birthDate: input.birthDate,
          birthTime: input.birthTime,
          placeLabel: input.placeLabel,
        });
        setGeneratedAt(new Date().toISOString());
        setReady(true);
      } catch {
        if (!cancelled) setFailed(true);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [jobId, attempt]);

  return (
    <main className="nk-print">
      {failed ? (
        <ServerUnavailable
          title="The report is not available yet"
          onRetry={() => setAttempt((n) => n + 1)}
        />
      ) : !ready || !artifact || !subject ? (
        <p className="nk-muted">Preparing report…</p>
      ) : (
        <ChartReportDocument
          jobId={jobId}
          artifact={artifact}
          subject={subject}
          reading={reading}
          lifeStory={lifeStory}
          predictions={predictions}
          remedies={remedies}
          generatedAt={generatedAt}
        />
      )}
    </main>
  );
}
