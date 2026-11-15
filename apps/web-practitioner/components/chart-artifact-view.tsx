"use client";

import { useState } from "react";
import type { VedicChartArtifact, YogaCategory } from "@astro/astrology-core";
import {
  CalendarDays,
  Compass,
  Flame,
  Gem,
  Grid3X3,
  Hourglass,
  Gauge,
  Orbit,
  RotateCcw,
} from "lucide-react";

import { KundaliChart } from "./kundali-chart";
import { ChartLegend } from "./chart-legend";
import { VargasExplorer } from "./vargas-explorer";
import { VimshopakaChart } from "./vimshopaka-chart";

function formatDegrees(value: number): string {
  const degrees = Math.floor(value);
  const minutes = Math.round((value - degrees) * 60);
  return `${degrees}°${String(minutes).padStart(2, "0")}'`;
}

function formatDate(iso: string): string {
  return iso.slice(0, 10);
}

const PLANET_SHORT: Record<string, string> = {
  sun: "Su",
  moon: "Mo",
  mars: "Ma",
  mercury: "Me",
  jupiter: "Ju",
  venus: "Ve",
  saturn: "Sa",
  rahu: "Ra",
  ketu: "Ke",
};

const SIGN_ABBREVIATIONS = [
  "Ari",
  "Tau",
  "Gem",
  "Can",
  "Leo",
  "Vir",
  "Lib",
  "Sco",
  "Sag",
  "Cap",
  "Aqu",
  "Pis",
];

const YOGA_GROUP_ORDER: Array<{ category: YogaCategory; label: string }> = [
  { category: "raj", label: "Raj Yogas" },
  { category: "dhan", label: "Dhan Yogas" },
  { category: "pancha-mahapurusha", label: "Pancha Mahapurusha Yogas" },
  { category: "lunar", label: "Lunar Yogas" },
  { category: "solar", label: "Solar Yogas" },
  { category: "dosha", label: "Doshas" },
  { category: "other", label: "Other" },
];

const MS_PER_YEAR = 365.25 * 24 * 60 * 60 * 1000;

function yearsSpan(startIso: string, endIso: string): number {
  return (new Date(endIso).getTime() - new Date(startIso).getTime()) / MS_PER_YEAR;
}

export function ChartArtifactView({ artifact }: { artifact: VedicChartArtifact }) {
  const meta = artifact.calculationMetadata;
  const [dashaSystem, setDashaSystem] = useState<"vimshottari" | "yogini">(
    "vimshottari",
  );
  const shadbalaByPlanet = new Map(
    (artifact.strengthMetrics?.shadbala ?? []).map((r) => [r.planet as string, r]),
  );
  const presentYogas = artifact.yogas.filter((yoga) => yoga.present);
  const now = Date.now();

  return (
    <div>
      <section className="nk-cosmic" aria-label="Birth details">
        <p className="eyebrow">Vedic birth chart</p>
        <h2>
          {artifact.ascendant.signName} Lagna{" "}
          <span className="data">
            {formatDegrees(artifact.ascendant.degreesInSign)}
          </span>
        </h2>
        <p className="data">
          {meta.input.placeLabel ?? "Unknown place"} · {meta.input.birthDate}{" "}
          {meta.input.birthTime} ({meta.input.timezoneName})
        </p>
        <p className="data">
          {artifact.ascendant.nakshatra} pada {artifact.ascendant.pada}
          <span aria-hidden> · </span>
          {meta.ayanamsa.name} ayanamsa {meta.ayanamsa.value.toFixed(4)}°
        </p>
      </section>

      <nav className="nk-section-nav" aria-label="Chart sections">
        <a href="#rashi-chart">Chart</a>
        <a href="#panchang">Panchang</a>
        <a href="#planets">Planets</a>
        <a href="#dashas">Dashas</a>
        <a href="#yogas">Yogas</a>
        <a href="#strengths">Strengths</a>
        <a href="#vargas">Vargas</a>
        <a href="#predictions">Predictions</a>
        <a href="#remedies">Remedies</a>
        <a href="#transits">Transits</a>
        <a href="#assistant">Assistant</a>
      </nav>

      <div className="nk-duo">
        <section className="nk-card nk-rashi-panel" aria-label="Rashi chart" id="rashi-chart">
          <div className="nk-rashi-head">
            <h2 className="nk-h2 !mb-0">
              <Compass size={16} aria-hidden /> Rashi Chart
            </h2>
            <span className="nk-badge nk-badge-ink">D1</span>
          </div>
          <KundaliChart artifact={artifact} />
        </section>

        <section className="nk-card" aria-label="Panchang" id="panchang">
          <h2 className="nk-h2"><CalendarDays size={16} aria-hidden /> Panchang</h2>
          <p className="nk-panchang-lede">
            Five-limb Vedic calendar at birth - used for muhurta, rituals, and
            day quality.
          </p>
          <div className="nk-grid nk-grid-compact">
            {(
              [
                {
                  label: "Tithi",
                  value: `${artifact.panchang.tithi.name} (${artifact.panchang.tithi.paksha})`,
                  explain:
                    "Lunar day: 1 of 30 phases from New Moon to Full Moon and back. Shukla = waxing; Krishna = waning.",
                },
                {
                  label: "Nakshatra",
                  value: `${artifact.panchang.moonNakshatra.name} pada ${artifact.panchang.moonNakshatra.pada}`,
                  explain:
                    "Moon’s lunar mansion among 27 stars. Pada (1–4) is the quarter within that nakshatra.",
                },
                {
                  label: "Yoga",
                  value: artifact.panchang.yoga.name,
                  explain:
                    "Sun–Moon angular yoga (one of 27). Marks the day’s general quality for activity.",
                },
                {
                  label: "Karana",
                  value: artifact.panchang.karana.name,
                  explain:
                    "Half of a tithi (one of 11). Used for timing actions within the lunar day.",
                },
                {
                  label: "Vara",
                  value: artifact.panchang.vara.name,
                  explain:
                    "Weekday ruled by a planet (e.g. Shukravara = Friday / Venus), from sunrise.",
                },
              ] as const
            ).map((row) => (
              <div className="nk-kv" key={row.label}>
                <span className="k">{row.label}</span>
                <span className="v">{row.value}</span>
                <span className="explain">{row.explain}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="nk-card" aria-label="Planetary positions" id="planets">
        <h2 className="nk-h2"><Orbit size={16} aria-hidden /> Planetary Positions</h2>
        <div className="nk-table-wrap">
          <table className="nk-table">
            <thead>
              <tr>
                <th>Planet</th>
                <th>Sign</th>
                <th>Degrees</th>
                <th>Nakshatra</th>
                <th>House</th>
                <th>Dignity</th>
                <th>Strength</th>
                <th>Flags</th>
              </tr>
            </thead>
            <tbody>
              {artifact.planets.map((planet) => (
                <tr key={planet.planet} id={`planet-${planet.planet}`}>
                  <td className="nk-planet">{planet.planet}</td>
                  <td>{planet.signName}</td>
                  <td className="data">{formatDegrees(planet.degreesInSign)}</td>
                  <td>
                    {planet.nakshatra} <span className="data">p{planet.pada}</span>
                  </td>
                  <td className="data">{planet.house}</td>
                  <td>
                    <span
                      className={
                        planet.dignity === "exalted" ||
                        planet.dignity === "moolatrikona" ||
                        planet.dignity === "own"
                          ? "nk-badge nk-badge-ink"
                          : planet.dignity === "debilitated" ||
                              planet.dignity === "enemy"
                            ? "nk-badge nk-badge-danger"
                            : "nk-badge nk-badge-muted"
                      }
                    >
                      {planet.dignity}
                    </span>
                  </td>
                  <td>
                    {(() => {
                      const strength = shadbalaByPlanet.get(planet.planet);
                      if (!strength) {
                        return <span className="nk-muted">-</span>;
                      }
                      return (
                        <span
                          className={
                            strength.ratio >= 1
                              ? "nk-badge nk-badge-ink"
                              : strength.ratio >= 0.8
                                ? "nk-badge nk-badge-muted"
                                : "nk-badge nk-badge-danger"
                          }
                          title={`Shadbala ${strength.totalRupas.toFixed(2)} rupas / required ${strength.requiredRupas}`}
                        >
                          {strength.totalRupas.toFixed(1)} ({Math.round(strength.ratio * 100)}%)
                        </span>
                      );
                    })()}
                  </td>
                  <td>
                    {planet.retrograde ? (
                      <span className="nk-badge nk-badge-ink"><RotateCcw size={11} aria-hidden /> retrograde</span>
                    ) : null}{" "}
                    {planet.combust ? (
                      <span className="nk-badge nk-badge-danger"><Flame size={11} aria-hidden /> combust</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="nk-card" aria-label="Vimshottari dasha" id="dashas">
        <h2 className="nk-h2"><Hourglass size={16} aria-hidden /> Dasha Timeline</h2>
        <div className="nk-domain-chips" role="tablist" aria-label="Dasha system">
          <button
            type="button"
            className={`nk-chip${dashaSystem === "vimshottari" ? " active" : ""}`}
            onClick={() => setDashaSystem("vimshottari")}
          >
            Vimshottari
          </button>
          <button
            type="button"
            className={`nk-chip${dashaSystem === "yogini" ? " active" : ""}`}
            onClick={() => setDashaSystem("yogini")}
          >
            Yogini
          </button>
        </div>
        {dashaSystem === "yogini" ? (
          <div>
            <p className="nk-muted">
              Birth nakshatra {artifact.yoginiDasha.birthNakshatra}; balance of{" "}
              {artifact.yoginiDasha.balanceYears.toFixed(2)} years of{" "}
              {artifact.yoginiDasha.birthYogini} at birth. 36-year cycle.
            </p>
            {artifact.yoginiDasha.mahadashas.slice(0, 8).map((mahadasha) => {
              const isCurrent =
                now >= new Date(mahadasha.start).getTime() &&
                now < new Date(mahadasha.end).getTime();
              return (
                <details
                  key={`${mahadasha.name}-${mahadasha.start}`}
                  className="nk-dasha-details"
                  open={isCurrent}
                >
                  <summary>
                    {mahadasha.name} ({mahadasha.planet}):{" "}
                    <span className="data">
                      {formatDate(mahadasha.start)} to {formatDate(mahadasha.end)}
                    </span>{" "}
                    {isCurrent ? (
                      <span className="nk-badge nk-badge-ink">current</span>
                    ) : null}
                  </summary>
                  <ul>
                    {mahadasha.children?.map((antardasha) => (
                      <li key={`${antardasha.name}-${antardasha.start}`}>
                        {antardasha.name} ({antardasha.planet}):{" "}
                        <span className="data">
                          {formatDate(antardasha.start)} to {formatDate(antardasha.end)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              );
            })}
          </div>
        ) : null}
        {dashaSystem === "vimshottari" ? (
        <div>
        <p className="nk-muted">
          Birth nakshatra {artifact.vimshottari.birthNakshatra}; balance of{" "}
          {artifact.vimshottari.balanceYears.toFixed(2)} years of{" "}
          {artifact.vimshottari.birthLord} mahadasha at birth.
        </p>

        {(() => {
          const mahadashas = artifact.vimshottari.mahadashas;
          const spanStart = new Date(mahadashas[0].start).getTime();
          const spanEnd = new Date(mahadashas[mahadashas.length - 1].end).getTime();
          const span = Math.max(spanEnd - spanStart, 1);
          const nowPct = Math.min(100, Math.max(0, ((now - spanStart) / span) * 100));
          const currentMd = mahadashas.find(
            (md) =>
              now >= new Date(md.start).getTime() &&
              now < new Date(md.end).getTime(),
          );

          return (
            <div
              className="nk-dasha-chart"
              role="img"
              aria-label={`Vimshottari mahadasha timeline from ${formatDate(mahadashas[0].start)} to ${formatDate(mahadashas[mahadashas.length - 1].end)}${currentMd ? `, currently in ${currentMd.planet}` : ""}`}
            >
              <div className="nk-dasha-chart-head">
                <span className="nk-dasha-chart-title">Mahadasha continuum</span>
                <span className="nk-dasha-chart-range data">
                  {formatDate(mahadashas[0].start).slice(0, 4)}
                  {" to "}
                  {formatDate(mahadashas[mahadashas.length - 1].end).slice(0, 4)}
                </span>
              </div>

              <div className="nk-dasha-chart-rail">
                <div className="nk-dasha-chart-ticks" aria-hidden>
                  {mahadashas.map((md) => {
                    const left =
                      ((new Date(md.start).getTime() - spanStart) / span) * 100;
                    return (
                      <span
                        key={`${md.planet}-tick`}
                        className="nk-dasha-tick"
                        style={{ left: `${left}%` }}
                      >
                        {formatDate(md.start).slice(0, 4)}
                      </span>
                    );
                  })}
                  <span
                    className="nk-dasha-tick nk-dasha-tick-end"
                    style={{ left: "100%" }}
                  >
                    {formatDate(mahadashas[mahadashas.length - 1].end).slice(0, 4)}
                  </span>
                </div>

                <div className="nk-dasha-chart-track">
                  {mahadashas.map((mahadasha) => {
                    const startMs = new Date(mahadasha.start).getTime();
                    const endMs = new Date(mahadasha.end).getTime();
                    const durationYrs = yearsSpan(mahadasha.start, mahadasha.end);
                    const isCurrent = now >= startMs && now < endMs;
                    const isPast = endMs <= now;
                    const progressPct = isCurrent
                      ? Math.min(
                          100,
                          Math.max(0, ((now - startMs) / (endMs - startMs)) * 100),
                        )
                      : 0;
                    const abbr =
                      PLANET_SHORT[mahadasha.planet] ??
                      mahadasha.planet.slice(0, 2);

                    return (
                      <div
                        key={`${mahadasha.planet}-bar`}
                        className={[
                          "nk-dasha-cell",
                          isPast ? "is-past" : "",
                          isCurrent ? "is-current" : "",
                          !isPast && !isCurrent ? "is-future" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        style={{ flexGrow: Math.max(durationYrs, 0.5) }}
                        title={`${mahadasha.planet}: ${formatDate(mahadasha.start)} to ${formatDate(mahadasha.end)}`}
                      >
                        {isCurrent ? (
                          <span
                            className="nk-dasha-cell-progress"
                            style={{ width: `${progressPct}%` }}
                            aria-hidden
                          />
                        ) : null}
                        <span className="nk-dasha-cell-abbr">{abbr}</span>
                        <span className="nk-dasha-cell-yrs">
                          {durationYrs.toFixed(durationYrs >= 10 ? 0 : 1)}y
                        </span>
                      </div>
                    );
                  })}

                  <div
                    className="nk-dasha-now"
                    style={{ left: `${nowPct}%` }}
                    aria-hidden
                  >
                    <span className="nk-dasha-now-label">Now</span>
                  </div>
                </div>
              </div>

              <ChartLegend
                title="Dasha timeline legend"
                items={[
                  {
                    id: "past",
                    label: "Past",
                    hint: "mahadasha already completed",
                    swatchClassName: "is-dasha-past",
                  },
                  {
                    id: "current",
                    label: "Current",
                    hint: "running mahadasha; light fill = progress so far",
                    swatchClassName: "is-dasha-current",
                  },
                  {
                    id: "future",
                    label: "Upcoming",
                    hint: "mahadasha not yet started",
                    swatchClassName: "is-dasha-future",
                  },
                  {
                    id: "now",
                    label: "Now marker",
                    hint: "today on the continuum",
                    swatchClassName: "is-dasha-now",
                  },
                  {
                    id: "width",
                    label: "Segment width",
                    hint: "proportional to years in that mahadasha",
                    swatchClassName: "is-dasha-width",
                  },
                ]}
              />
            </div>
          );
        })()}

        {artifact.vimshottari.mahadashas.map((mahadasha) => {
          const isCurrent =
            now >= new Date(mahadasha.start).getTime() &&
            now < new Date(mahadasha.end).getTime();
          return (
            <details
              key={`${mahadasha.planet}-${mahadasha.start}`}
              id={`dasha-${mahadasha.planet}`}
              className="nk-dasha-details"
              open={isCurrent}
            >
              <summary>
                {mahadasha.planet} mahadasha:{" "}
                <span className="data">
                  {formatDate(mahadasha.start)} to {formatDate(mahadasha.end)}
                </span>{" "}
                {isCurrent ? <span className="nk-badge nk-badge-ink">current</span> : null}
              </summary>
              <ul>
                {mahadasha.children?.map((antardasha) => (
                  <li key={`${antardasha.planet}-${antardasha.start}`}>
                    {antardasha.planet} antardasha:{" "}
                    <span className="data">
                      {formatDate(antardasha.start)} to {formatDate(antardasha.end)}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          );
        })}
        </div>
        ) : null}
      </section>

      <section className="nk-card" aria-label="Yogas" id="yogas">
        <h2 className="nk-h2"><Gem size={16} aria-hidden /> Detected Yogas</h2>
        {presentYogas.length === 0 ? (
          <p className="nk-muted">No tracked yogas detected in this chart.</p>
        ) : (
          <>
            <p className="nk-muted" style={{ marginBottom: "1rem" }}>
              {presentYogas.length} yoga{presentYogas.length > 1 ? "s" : ""} detected
              out of {artifact.yogas.length} evaluated.
            </p>
            {YOGA_GROUP_ORDER.map(({ category, label }) => {
              const group = presentYogas.filter((y) => y.category === category);
              if (group.length === 0) return null;
              return (
                <div key={category} className="nk-yoga-group">
                  <h3 className="nk-yoga-group-title">{label}</h3>
                  {group.map((yoga) => (
                    <article
                      key={yoga.key}
                      className={`nk-yoga${category === "dosha" ? " nk-yoga-dosha" : ""}`}
                    >
                      <h4>{yoga.name}</h4>
                      <p>{yoga.description}</p>
                      <ul>
                        {yoga.evidence.map((line) => (
                          <li key={line}>{line}</li>
                        ))}
                      </ul>
                    </article>
                  ))}
                </div>
              );
            })}
          </>
        )}
      </section>

      <section className="nk-card" aria-label="Strength metrics" id="strengths">
        <h2 className="nk-h2"><Gauge size={16} aria-hidden /> Strength Metrics</h2>
        <h3 className="nk-subhead">Vimshopaka Bala (0-20)</h3>
        <VimshopakaChart rows={artifact.strengthMetrics.vimshopaka} />
        <p className="nk-hint">
          Shadbala uses documented simplifications for sub-balas needing
          horizon data; ratios are comparative, not to-the-virupa exact.
        </p>
      </section>

      <section className="nk-card" aria-label="Divisional charts" id="vargas">
        <h2 className="nk-h2"><Grid3X3 size={16} aria-hidden /> Divisional Charts</h2>
        <VargasExplorer
          vargas={artifact.vargas}
          rashiPlanets={Object.fromEntries(
            artifact.planets.map((p) => [p.planet, p.signIndex]),
          )}
        />
      </section>
    </div>
  );
}
