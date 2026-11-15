import type { VedicChartArtifact } from "@astro/astrology-core";

import { ChartLegend } from "./chart-legend";

const PLANET_ABBREVIATIONS: Record<string, string> = {
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

/**
 * Label anchors for the twelve houses of a North-Indian chart drawn in a
 * 400x400 frame: house 1 in the top diamond, houses counted anticlockwise.
 */
const HOUSE_ANCHORS: Array<{ x: number; y: number }> = [
  { x: 200, y: 108 }, // 1
  { x: 100, y: 54 }, // 2
  { x: 54, y: 108 }, // 3
  { x: 108, y: 200 }, // 4
  { x: 54, y: 292 }, // 5
  { x: 100, y: 346 }, // 6
  { x: 200, y: 292 }, // 7
  { x: 300, y: 346 }, // 8
  { x: 346, y: 292 }, // 9
  { x: 292, y: 200 }, // 10
  { x: 346, y: 108 }, // 11
  { x: 300, y: 54 }, // 12
];

/** Sign-number label offsets, tucked toward each house's outer edge. */
const SIGN_ANCHORS: Array<{ x: number; y: number }> = [
  { x: 200, y: 168 },
  { x: 100, y: 24 },
  { x: 24, y: 108 },
  { x: 168, y: 200 },
  { x: 24, y: 298 },
  { x: 100, y: 380 },
  { x: 200, y: 242 },
  { x: 300, y: 380 },
  { x: 376, y: 298 },
  { x: 242, y: 200 },
  { x: 376, y: 108 },
  { x: 300, y: 24 },
];

/** Soft wash polygons for angular houses (1 / 4 / 7 / 10) - subtle depth. */
const ANGULAR_FILLS: Array<{ house: number; points: string }> = [
  { house: 1, points: "200,4 299,101 200,200 101,101" },
  { house: 4, points: "4,200 101,101 200,200 101,299" },
  { house: 7, points: "200,396 299,299 200,200 101,299" },
  { house: 10, points: "396,200 299,101 200,200 299,299" },
];

function chunk<T>(items: T[], size: number): T[][] {
  const rows: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    rows.push(items.slice(i, i + size));
  }
  return rows;
}

export function KundaliChart({ artifact }: { artifact: VedicChartArtifact }) {
  const retrogradeSet = new Set(
    artifact.planets.filter((p) => p.retrograde).map((p) => p.planet),
  );
  const lagnaSign = artifact.ascendant.signName;

  return (
    <figure className="nk-kundali-wrap">
      <svg
        viewBox="0 0 400 400"
        role="img"
        aria-label={`North Indian rashi chart with ${lagnaSign} lagna`}
        className="nk-kundali"
      >
        <defs>
          <linearGradient id="nk-kundali-face" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="var(--surface-2)" />
          </linearGradient>
          <linearGradient id="nk-kundali-lagna" x1="50%" y1="0%" x2="50%" y2="100%">
            <stop offset="0%" stopColor="var(--text-primary)" stopOpacity="0.14" />
            <stop offset="100%" stopColor="var(--text-primary)" stopOpacity="0.04" />
          </linearGradient>
        </defs>

        {/* Chart face */}
        <rect
          x="3"
          y="3"
          width="394"
          height="394"
          rx="4"
          className="nk-kundali-face"
        />

        {/* Angular house washes - quieter structure */}
        {ANGULAR_FILLS.map(({ house, points }) => (
          <polygon
            key={house}
            points={points}
            className={
              house === 1 ? "nk-kundali-lagna-fill" : "nk-kundali-angular"
            }
          />
        ))}

        {/* Structure lines */}
        <line x1="3" y1="3" x2="397" y2="397" className="nk-kundali-line" />
        <line x1="397" y1="3" x2="3" y2="397" className="nk-kundali-line" />
        <polygon
          points="200,3 397,200 200,397 3,200"
          className="nk-kundali-diamond"
        />
        <rect
          x="3"
          y="3"
          width="394"
          height="394"
          rx="4"
          className="nk-kundali-frame"
        />

        {/* Center mark */}
        <circle cx="200" cy="200" r="3.5" className="nk-kundali-center" />

        {artifact.houses.map((house, index) => {
          const anchor = HOUSE_ANCHORS[index];
          const signAnchor = SIGN_ANCHORS[index];
          const rows = chunk(house.occupants, 3);
          const isLagna = house.number === 1;

          return (
            <g key={house.number} className="nk-kundali-house">
              <text
                x={signAnchor.x}
                y={signAnchor.y}
                className="nk-kundali-sign"
              >
                {house.signIndex + 1}
              </text>

              {isLagna ? (
                <text
                  x={anchor.x}
                  y={anchor.y - 24}
                  className="nk-kundali-lagna"
                >
                  La
                </text>
              ) : null}

              <text x={anchor.x} y={anchor.y} className="nk-kundali-planets">
                {rows.map((row, rowIndex) => (
                  <tspan
                    key={rowIndex}
                    x={anchor.x}
                    dy={rowIndex === 0 ? 0 : 16}
                  >
                    {row.map((planet, planetIndex) => {
                      const abbrev = PLANET_ABBREVIATIONS[planet] ?? planet;
                      const retro = retrogradeSet.has(planet);
                      return (
                        <tspan key={planet}>
                          {planetIndex > 0 ? " " : ""}
                          <tspan className="nk-kundali-planet">{abbrev}</tspan>
                          {retro ? (
                            <tspan className="nk-kundali-retro">ʳ</tspan>
                          ) : null}
                        </tspan>
                      );
                    })}
                  </tspan>
                ))}
              </text>
            </g>
          );
        })}
      </svg>

      <figcaption className="nk-kundali-caption">
        <span className="nk-kundali-caption-lagna">{lagnaSign} lagna</span>
        <span className="nk-kundali-caption-sep" aria-hidden>
          ·
        </span>
        <span>North Indian diamond chart</span>
      </figcaption>
      <ChartLegend
        title="Rashi chart legend"
        items={[
          {
            id: "lagna",
            label: "Lagna house",
            hint: "shaded diamond (house 1)",
            swatchClassName: "is-lagna",
          },
          {
            id: "angular",
            label: "Angular houses",
            hint: "1 / 4 / 7 / 10 wash",
            swatchClassName: "is-angular",
          },
          {
            id: "sign",
            label: "Sign number",
            hint: "1-12 in each house",
            swatchClassName: "is-sign",
          },
          {
            id: "planet",
            label: "Planet abbreviation",
            hint: "Su Mo Ma Me Ju Ve Sa Ra Ke",
            swatchClassName: "is-planet",
          },
          {
            id: "retro",
            label: "ʳ retrograde",
            hint: "planet moving apparently backward",
            swatchClassName: "is-retro",
          },
        ]}
      />
    </figure>
  );
}
