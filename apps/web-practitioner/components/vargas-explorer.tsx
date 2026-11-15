"use client";

import { useState } from "react";

import { ChartLegend } from "./chart-legend";

const SIGN_NAMES = [
  "Aries",
  "Taurus",
  "Gemini",
  "Cancer",
  "Leo",
  "Virgo",
  "Libra",
  "Scorpio",
  "Sagittarius",
  "Capricorn",
  "Aquarius",
  "Pisces",
] as const;

const SIGN_SHORT = [
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
] as const;

const PLANET_ORDER = [
  "sun",
  "moon",
  "mars",
  "mercury",
  "jupiter",
  "venus",
  "saturn",
  "rahu",
  "ketu",
] as const;

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

export const VARGA_META = [
  {
    key: "d1",
    code: "D1",
    name: "Rashi",
    purpose: "Main birth chart. Body, temperament, and overall life results.",
  },
  {
    key: "d2",
    code: "D2",
    name: "Hora",
    purpose: "Wealth capacity and how resources accumulate.",
  },
  {
    key: "d3",
    code: "D3",
    name: "Drekkana",
    purpose: "Siblings, courage, and efforts through co-borns.",
  },
  {
    key: "d7",
    code: "D7",
    name: "Saptamsa",
    purpose: "Children and creative progeny themes.",
  },
  {
    key: "d9",
    code: "D9",
    name: "Navamsa",
    purpose: "Marriage, dharma, and the deeper strength of planets.",
  },
  {
    key: "d10",
    code: "D10",
    name: "Dasamsa",
    purpose: "Career, status, and public work.",
  },
  {
    key: "d12",
    code: "D12",
    name: "Dwadasamsa",
    purpose: "Parents and ancestral lineage.",
  },
  {
    key: "d30",
    code: "D30",
    name: "Trimsamsa",
    purpose: "Misfortune patterns and general adversity.",
  },
  {
    key: "d60",
    code: "D60",
    name: "Shashtiamsa",
    purpose: "Fine-grain karma; used to refine dignity judgments.",
  },
] as const;

export type VargaChartData = {
  ascendantSign: number;
  planets: Record<string, number>;
};

type VargasExplorerProps = {
  vargas: Record<string, VargaChartData>;
  /** D1 planet signs for same-sign highlighting */
  rashiPlanets?: Record<string, number>;
};

function orderedPlanets(planets: Record<string, number>) {
  const known = PLANET_ORDER.filter((p) => p in planets);
  const rest = Object.keys(planets).filter(
    (p) => !PLANET_ORDER.includes(p as (typeof PLANET_ORDER)[number]),
  );
  return [...known, ...rest];
}

export function VargasExplorer({ vargas, rashiPlanets }: VargasExplorerProps) {
  const available = VARGA_META.filter((meta) => vargas[meta.key]);
  const [activeKey, setActiveKey] = useState<string>(
    available[0]?.key ?? "d1",
  );
  const activeMeta =
    available.find((meta) => meta.key === activeKey) ?? available[0];
  const active = activeMeta ? vargas[activeMeta.key] : null;

  if (!activeMeta || !active) {
    return <p className="nk-muted">No divisional charts available.</p>;
  }

  const planets = orderedPlanets(active.planets);

  return (
    <div className="nk-vargas">
      <p className="nk-vargas-lede">
        Divisional charts (vargas) zoom into life areas. Each planet keeps its
        longitude but is read in a finer sign map - pick a chart to inspect
        lagna and placements.
      </p>

      <div className="nk-vargas-tabs" role="tablist" aria-label="Divisional charts">
        {available.map((meta) => {
          const selected = meta.key === activeMeta.key;
          const lagna = vargas[meta.key]?.ascendantSign;
          return (
            <button
              key={meta.key}
              type="button"
              role="tab"
              aria-selected={selected}
              className={`nk-vargas-tab${selected ? " is-active" : ""}`}
              onClick={() => setActiveKey(meta.key)}
            >
              <span className="nk-vargas-tab-code">{meta.code}</span>
              <span className="nk-vargas-tab-name">{meta.name}</span>
              {typeof lagna === "number" ? (
                <span className="nk-vargas-tab-lagna data">
                  {SIGN_SHORT[lagna]} lagna
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      <div
        className="nk-vargas-panel"
        role="tabpanel"
        aria-label={`${activeMeta.code} ${activeMeta.name}`}
      >
        <div className="nk-vargas-panel-head">
          <div>
            <p className="nk-vargas-panel-code">
              {activeMeta.code} · {activeMeta.name}
            </p>
            <h3 className="nk-vargas-panel-title">
              {SIGN_NAMES[active.ascendantSign]} lagna
            </h3>
          </div>
          <p className="nk-vargas-panel-purpose">{activeMeta.purpose}</p>
        </div>

        <div className="nk-vargas-planets">
          {planets.map((planet) => {
            const sign = active.planets[planet];
            const rashiSign = rashiPlanets?.[planet];
            const sameAsRashi =
              activeMeta.key !== "d1" &&
              typeof rashiSign === "number" &&
              rashiSign === sign;
            return (
              <div
                key={planet}
                className={`nk-vargas-planet${sameAsRashi ? " is-same" : ""}`}
              >
                <span className="nk-vargas-planet-name">
                  {PLANET_LABEL[planet] ?? planet}
                </span>
                <span className="nk-vargas-planet-sign">
                  {SIGN_NAMES[sign]}
                </span>
                <span className="nk-vargas-planet-meta data">
                  {SIGN_SHORT[sign]}
                  {sameAsRashi ? " · same as D1" : ""}
                </span>
              </div>
            );
          })}
        </div>

        <ChartLegend
          title={`${activeMeta.code} legend`}
          items={[
            {
              id: "lagna",
              label: "Lagna",
              hint: `ascendant in this varga (${SIGN_NAMES[active.ascendantSign]})`,
              swatchClassName: "is-varga-lagna",
            },
            {
              id: "planet",
              label: "Planet card",
              hint: "sign occupied in this divisional chart",
              swatchClassName: "is-varga-planet",
            },
            {
              id: "same",
              label: "Same as D1",
              hint: "planet sign matches the rashi chart",
              swatchClassName: "is-varga-same",
            },
            {
              id: "purpose",
              label: activeMeta.name,
              hint: activeMeta.purpose,
              swatchClassName: "is-varga-purpose",
            },
          ]}
        />
      </div>
    </div>
  );
}
