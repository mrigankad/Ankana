"use client";

import { formatDay } from "@/lib/utils";
import { AnkanaMark } from "@/components/ankana/logo";
import type { VedicChartArtifact } from "@astro/astrology-core";
import type { EnrichedPrediction, Remedy } from "@astro/rule-engine";

import { KundaliChart } from "./kundali-chart";
import type { ChartReading, LifeStory } from "./reading-panel";

const PLANET_LABEL: Record<string, string> = {
  sun: "Sun",
  moon: "Moon",
  mars: "Mars",
  mercury: "Mercury",
  jupiter: "Jupiter",
  venus: "Venus",
  saturn: "Saturn",
  rahu: "Rahu",
  ketu: "Ketu",
};

function formatDegrees(value: number): string {
  const degrees = Math.floor(value);
  const minutes = Math.round((value - degrees) * 60);
  return `${degrees}°${String(minutes).padStart(2, "0")}'`;
}

function formatDate(iso: string): string {
  return formatDay(iso.slice(0, 10));
}

export interface ChartReportSubject {
  name: string;
  birthDate: string;
  birthTime: string;
  placeLabel?: string;
}

export function ChartReportDocument({
  jobId,
  artifact,
  subject,
  reading,
  lifeStory,
  predictions,
  remedies,
  generatedAt,
}: {
  jobId: string;
  artifact: VedicChartArtifact;
  subject: ChartReportSubject;
  reading?: ChartReading | null;
  lifeStory?: LifeStory | null;
  predictions: EnrichedPrediction[];
  remedies: Remedy[];
  generatedAt: string;
}) {
  const meta = artifact.calculationMetadata;
  const currentMd = artifact.vimshottari.mahadashas.find((m) => {
    const now = Date.now();
    return new Date(m.start).getTime() <= now && now < new Date(m.end).getTime();
  });
  const presentYogas = artifact.yogas.filter((y) => y.present);
  const hybridChapters = lifeStory?.lenses.hybrid.slice(0, 5) ?? [];

  return (
    <article className="nk-report" data-testid="report-ready">
      {/* Cover */}
      <header className="nk-report-cover">
        <div className="nk-report-cover-brand">
          <AnkanaMark size={44} tone="light" className="nk-report-logo" />
          <div>
            <p className="nk-report-eyebrow">Ankana Practitioner</p>
            <h1 className="nk-report-cover-title">Birth Chart Report</h1>
          </div>
        </div>
        <div className="nk-report-subject">
          <h2 className="nk-report-name">{subject.name}</h2>
          <p className="nk-report-meta">
            Born {formatDay(subject.birthDate)} · {subject.birthTime}
            {subject.placeLabel ? ` · ${subject.placeLabel}` : ""}
          </p>
          <p className="nk-report-meta">
            {artifact.ascendant.signName} Lagna · {artifact.ascendant.nakshatra}{" "}
            pada {artifact.ascendant.pada}
            {currentMd
              ? ` · Current ${PLANET_LABEL[currentMd.planet] ?? currentMd.planet} mahadasha`
              : ""}
          </p>
        </div>
        <dl className="nk-report-facts">
          <div>
            <dt>Ayanamsa</dt>
            <dd>
              {meta.ayanamsa.name} {meta.ayanamsa.value.toFixed(4)}°
            </dd>
          </div>
          <div>
            <dt>Engine</dt>
            <dd>{meta.engineVersion}</dd>
          </div>
          <div>
            <dt>Job</dt>
            <dd className="nk-report-mono">{jobId}</dd>
          </div>
          <div>
            <dt>Generated</dt>
            <dd>{formatDay(generatedAt)}, {generatedAt.slice(11, 16)} UTC</dd>
          </div>
        </dl>
        <nav className="nk-report-toc" aria-label="Report contents">
          <p className="nk-report-toc-label">Contents</p>
          <ol>
            <li>Rashi chart (D1)</li>
            <li>Planetary positions</li>
            <li>Houses &amp; lords</li>
            <li>Vimshottari mahadashas</li>
            <li>Yogas &amp; doshas</li>
            <li>Shadbala</li>
            {hybridChapters.length > 0 ? <li>Your Life</li> : null}
            {reading?.sections?.length ? <li>Deep reading</li> : null}
            <li>Prediction windows</li>
            <li>Remedies</li>
          </ol>
        </nav>
      </header>

      {/* Kundali */}
      <section className="nk-report-section">
        <h3 className="nk-report-h">Rashi chart (D1)</h3>
        <div className="nk-report-kundali">
          <KundaliChart artifact={artifact} />
        </div>
      </section>

      {/* Planets */}
      <section className="nk-report-section">
        <h3 className="nk-report-h">Planetary positions</h3>
        <table className="nk-report-table max-sm:block max-sm:max-w-full max-sm:overflow-x-auto">
          <thead>
            <tr>
              <th>Planet</th>
              <th>Sign</th>
              <th>House</th>
              <th>Nakshatra</th>
              <th>Dignity</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {artifact.planets.map((p) => (
              <tr key={p.planet}>
                <td>{PLANET_LABEL[p.planet] ?? p.planet}</td>
                <td>
                  {p.signName} {formatDegrees(p.degreesInSign)}
                </td>
                <td>{p.house}</td>
                <td>
                  {p.nakshatra} p{p.pada}
                </td>
                <td>{p.dignity}</td>
                <td>
                  {[p.retrograde ? "R" : null, p.combust ? "Combust" : null]
                    .filter(Boolean)
                    .join(", ") || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Houses */}
      <section className="nk-report-section">
        <h3 className="nk-report-h">Houses & lords</h3>
        <table className="nk-report-table max-sm:block max-sm:max-w-full max-sm:overflow-x-auto">
          <thead>
            <tr>
              <th>House</th>
              <th>Sign</th>
              <th>Lord</th>
              <th>Occupants</th>
            </tr>
          </thead>
          <tbody>
            {artifact.houses.map((h) => (
              <tr key={h.number}>
                <td>{h.number}</td>
                <td>{h.signName}</td>
                <td>{PLANET_LABEL[h.lord] ?? h.lord}</td>
                <td>
                  {(h.occupants ?? [])
                    .map((p) => PLANET_LABEL[p] ?? p)
                    .join(", ") || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Dashas */}
      <section className="nk-report-section">
        <h3 className="nk-report-h">Vimshottari mahadashas</h3>
        <table className="nk-report-table max-sm:block max-sm:max-w-full max-sm:overflow-x-auto">
          <thead>
            <tr>
              <th>Lord</th>
              <th>Start</th>
              <th>End</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {artifact.vimshottari.mahadashas.map((m) => {
              const now = Date.now();
              const start = new Date(m.start).getTime();
              const end = new Date(m.end).getTime();
              const status =
                start <= now && now < end
                  ? "Current"
                  : end <= now
                    ? "Past"
                    : "Future";
              return (
                <tr key={`${m.planet}-${m.start}`}>
                  <td>{PLANET_LABEL[m.planet] ?? m.planet}</td>
                  <td>{formatDate(m.start)}</td>
                  <td>{formatDate(m.end)}</td>
                  <td>{status}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {/* Yogas */}
      <section className="nk-report-section">
        <h3 className="nk-report-h">Active yogas & doshas</h3>
        {presentYogas.length === 0 ? (
          <p className="nk-report-copy">No active yogas detected in this chart.</p>
        ) : (
          <ul className="nk-report-list">
            {presentYogas.map((y) => (
              <li key={y.key}>
                <strong>{y.name}</strong>
                <span className="nk-report-muted"> ({y.category})</span>
                <p>{y.description}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Strengths */}
      <section className="nk-report-section">
        <h3 className="nk-report-h">Shadbala (strength ratios)</h3>
        <table className="nk-report-table max-sm:block max-sm:max-w-full max-sm:overflow-x-auto">
          <thead>
            <tr>
              <th>Planet</th>
              <th>Ratio</th>
              <th>Rupa</th>
            </tr>
          </thead>
          <tbody>
            {artifact.strengthMetrics.shadbala.map((row) => (
              <tr key={row.planet}>
                <td>{PLANET_LABEL[row.planet] ?? row.planet}</td>
                <td>{row.ratio.toFixed(2)}</td>
                <td>{row.totalRupas.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Your Life */}
      {hybridChapters.length > 0 ? (
        <section className="nk-report-section">
          <h3 className="nk-report-h">Your Life (hybrid)</h3>
          {hybridChapters.map((chapter) => (
            <div key={chapter.key} className="nk-report-chapter">
              <h4>{chapter.title}</h4>
              <p>{chapter.summary}</p>
              {chapter.items.slice(0, 2).map((item) => (
                <div key={item.title} className="nk-report-item">
                  <strong>{item.title}</strong>
                  <p>{item.text}</p>
                </div>
              ))}
            </div>
          ))}
        </section>
      ) : null}

      {/* Deep reading highlights */}
      {reading?.sections?.length ? (
        <section className="nk-report-section">
          <h3 className="nk-report-h">Deep reading highlights</h3>
          {reading.sections
            .filter((s) => ["lagna", "dasha", "yogas"].includes(s.key))
            .map((section) => (
              <div key={section.key} className="nk-report-chapter">
                <h4>{section.title}</h4>
                {section.items.slice(0, 3).map((item) => (
                  <div key={item.title} className="nk-report-item">
                    <strong>{item.title}</strong>
                    <p>{item.text}</p>
                  </div>
                ))}
              </div>
            ))}
        </section>
      ) : null}

      {/* Predictions */}
      <section className="nk-report-section">
        <h3 className="nk-report-h">Prediction windows</h3>
        {predictions.length === 0 ? (
          <p className="nk-report-copy">No prediction windows in range.</p>
        ) : (
          <table className="nk-report-table max-sm:block max-sm:max-w-full max-sm:overflow-x-auto">
            <thead>
              <tr>
                <th>Domain</th>
                <th>Window</th>
                <th>Headline</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {predictions.slice(0, 18).map((p, i) => (
                <tr key={`${p.domain}-${p.window.start}-${i}`}>
                  <td>{p.domain}</td>
                  <td>
                    {formatDate(p.window.start)} to {formatDate(p.window.end)}
                  </td>
                  <td>
                    <strong>{p.headline}</strong>
                    {p.narrative ? (
                      <span className="nk-report-muted">
                        {" "}
                        · {p.narrative.slice(0, 160)}
                        {p.narrative.length > 160 ? "…" : ""}
                      </span>
                    ) : null}
                  </td>
                  <td>{Math.round(p.confidence * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Remedies */}
      <section className="nk-report-section">
        <h3 className="nk-report-h">Remedies</h3>
        {remedies.length === 0 ? (
          <p className="nk-report-copy">No remedies suggested for this chart.</p>
        ) : (
          <ul className="nk-report-list">
            {remedies.map((r, i) => (
              <li key={`${r.kind}-${r.title}-${i}`}>
                <strong>
                  {r.title}
                  <span className="nk-report-muted">
                    {" "}
                    · {r.kind} · {r.strengthOfRecommendation}
                  </span>
                </strong>
                {r.practice ? <p>{r.practice}</p> : null}
                {r.rationale ? <p>{r.rationale}</p> : null}
                {r.cautions?.length ? (
                  <p className="nk-report-muted">
                    Caution: {r.cautions.join("; ")}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Closing */}
      <footer className="nk-report-footer">
        <p className="nk-report-disclaimer">
          Advisory guidance only - not medical, legal, or financial advice.
          Deterministic Vedic computation with evidence-cited readings.
        </p>
        <div className="nk-report-footer-brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo-nakshatra-light.svg"
            alt=""
            className="nk-report-logo-sm"
            aria-hidden
          />
          <div>
            <p className="nk-report-footer-title">Ankana</p>
            <p>
              Built by{" "}
              <a
                href="https://github.com/mrigankad"
                target="_blank"
                rel="noreferrer"
              >
                github.com/mrigankad
              </a>
            </p>
          </div>
        </div>
      </footer>
    </article>
  );
}
