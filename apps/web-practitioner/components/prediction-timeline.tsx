"use client";

import { useState } from "react";
import type { Domain, EnrichedPrediction } from "@astro/rule-engine";
import {
  CircleAlert,
  CircleCheck,
  CircleDot,
  Link2,
  TrendingUp,
} from "lucide-react";

const DOMAINS: Array<{ key: Domain; label: string }> = [
  { key: "career", label: "Career" },
  { key: "wealth", label: "Wealth" },
  { key: "marriage", label: "Marriage" },
  { key: "health", label: "Health" },
  { key: "education", label: "Education" },
  { key: "travel", label: "Travel" },
  { key: "spiritual", label: "Spiritual" },
];

function formatDate(iso: string): string {
  return iso.slice(0, 10);
}

function EffectIcon({ effect }: { effect: EnrichedPrediction["effect"] }) {
  if (effect === "supportive") {
    return <CircleCheck size={15} className="nk-effect-supportive" aria-hidden />;
  }
  if (effect === "challenging") {
    return <CircleAlert size={15} className="nk-effect-challenging" aria-hidden />;
  }
  return <CircleDot size={15} className="nk-effect-mixed" aria-hidden />;
}

export function PredictionTimeline({
  predictions,
}: {
  predictions: EnrichedPrediction[];
}) {
  const [activeDomain, setActiveDomain] = useState<Domain | "all">("all");

  const visible =
    activeDomain === "all"
      ? predictions
      : predictions.filter((p) => p.domain === activeDomain);

  const firingDomains = new Set(predictions.map((p) => p.domain));

  return (
    <section className="nk-card" aria-label="Predictions" id="predictions">
      <h2 className="nk-h2">
        <TrendingUp size={16} aria-hidden /> Prediction Windows
      </h2>
      <p className="nk-muted">
        Dated windows from dasha periods crossed with natal strengths and
        transits. Every window lists the exact rules and placements behind it.
      </p>

      <div className="nk-domain-chips" role="tablist" aria-label="Filter by domain">
        <button
          type="button"
          className={`nk-chip${activeDomain === "all" ? " active" : ""}`}
          onClick={() => setActiveDomain("all")}
        >
          All
        </button>
        {DOMAINS.filter((d) => firingDomains.has(d.key)).map((domain) => (
          <button
            key={domain.key}
            type="button"
            className={`nk-chip${activeDomain === domain.key ? " active" : ""}`}
            onClick={() => setActiveDomain(domain.key)}
          >
            {domain.label}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <p className="nk-muted">
          No rule-backed windows for this filter in the evaluated horizon.
        </p>
      ) : (
        <ol className="nk-prediction-list">
          {visible.map((prediction) => (
            <li
              key={`${prediction.domain}-${prediction.window.start}`}
              className="nk-prediction"
            >
              <div className="nk-prediction-head">
                <EffectIcon effect={prediction.effect} />
                <span className="nk-prediction-domain">{prediction.domain}</span>
                <span className="data">
                  {formatDate(prediction.window.start)} –{" "}
                  {formatDate(prediction.window.end)}
                </span>
                <span
                  className={`nk-badge nk-confidence-band nk-confidence-band-${prediction.confidenceBand}`}
                  title={
                    prediction.confidenceDrivers?.join(" · ") ??
                    `Confidence ${(prediction.confidence * 100).toFixed(0)}%`
                  }
                >
                  {prediction.confidenceBand} ·{" "}
                  {(prediction.confidence * 100).toFixed(0)}%
                </span>
                {prediction.tension ? (
                  <span className="nk-badge nk-badge-danger">tension</span>
                ) : null}
              </div>
              <p className="nk-prediction-headline">{prediction.headline}</p>
              <p className="nk-prediction-text">{prediction.narrative}</p>
              {prediction.linkedRemedyPlanets?.length ? (
                <p className="nk-prediction-remedy-link">
                  <Link2 size={13} aria-hidden /> Linked remedies for{" "}
                  {prediction.linkedRemedyPlanets.join(", ")}
                </p>
              ) : null}
              <details>
                <summary>
                  Why this window ({prediction.ruleIds.length} rule
                  {prediction.ruleIds.length > 1 ? "s" : ""}
                  {prediction.confidenceDrivers?.length
                    ? ` · ${prediction.confidenceDrivers.length} strength driver${prediction.confidenceDrivers.length > 1 ? "s" : ""}`
                    : ""}
                  )
                </summary>
                <ul>
                  {prediction.confidenceDrivers?.map((line, index) => (
                    <li key={`driver-${index}-${line}`}>{line}</li>
                  ))}
                  {prediction.evidence.map((line, index) => (
                    <li key={`evidence-${index}-${line}`}>{line}</li>
                  ))}
                </ul>
              </details>
            </li>
          ))}
        </ol>
      )}
      <p className="nk-hint">
        Timing guidance is advisory and probabilistic - never a substitute for
        medical, legal, or financial advice.
      </p>
    </section>
  );
}
