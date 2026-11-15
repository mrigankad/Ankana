"use client";

import { ChartLegend } from "./chart-legend";

export type VimshopakaRow = { planet: string; score: number };

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

const MAX_SCORE = 20;
const SIZE = 300;
const CX = SIZE / 2;
const CY = SIZE / 2;
const INNER = 40;
const OUTER = 112;
const GAP = 0.035; // radians between wedges

function polar(cx: number, cy: number, r: number, angle: number) {
  return {
    x: cx + r * Math.cos(angle),
    y: cy + r * Math.sin(angle),
  };
}

function annularWedge(
  startAngle: number,
  endAngle: number,
  innerR: number,
  outerR: number,
): string {
  const large = endAngle - startAngle > Math.PI ? 1 : 0;
  const p0 = polar(CX, CY, outerR, startAngle);
  const p1 = polar(CX, CY, outerR, endAngle);
  const p2 = polar(CX, CY, innerR, endAngle);
  const p3 = polar(CX, CY, innerR, startAngle);
  return [
    `M ${p0.x} ${p0.y}`,
    `A ${outerR} ${outerR} 0 ${large} 1 ${p1.x} ${p1.y}`,
    `L ${p2.x} ${p2.y}`,
    `A ${innerR} ${innerR} 0 ${large} 0 ${p3.x} ${p3.y}`,
    "Z",
  ].join(" ");
}

function band(score: number): "strong" | "moderate" | "weak" {
  if (score >= 15) return "strong";
  if (score >= 10) return "moderate";
  return "weak";
}

function bandLabel(score: number): string {
  const b = band(score);
  if (b === "strong") return "Strong";
  if (b === "moderate") return "Moderate";
  return "Weak";
}

export function VimshopakaChart({ rows }: { rows: VimshopakaRow[] }) {
  const n = rows.length || 1;
  const slice = (Math.PI * 2) / n;
  const avg =
    rows.length === 0
      ? 0
      : rows.reduce((sum, row) => sum + row.score, 0) / rows.length;
  const strongest = rows.reduce<VimshopakaRow | null>((best, row) => {
    if (!best || row.score > best.score) return row;
    return best;
  }, null);

  return (
    <div className="nk-vim-chart">
      <div className="nk-vim-radial-wrap">
        <svg
          className="nk-vim-radial"
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          role="img"
          aria-label="Vimshopaka bala radial chart, scores from 0 to 20"
        >
          <circle
            className="nk-vim-guide"
            cx={CX}
            cy={CY}
            r={INNER + (OUTER - INNER) * 0.5}
          />
          <circle className="nk-vim-guide" cx={CX} cy={CY} r={OUTER} />
          <text className="nk-vim-guide-label" x={CX} y={CY - OUTER + 10}>
            20
          </text>
          <text
            className="nk-vim-guide-label"
            x={CX}
            y={CY - (INNER + (OUTER - INNER) * 0.5) + 4}
          >
            10
          </text>

          {rows.map((row, index) => {
            const start = -Math.PI / 2 + index * slice + GAP / 2;
            const end = -Math.PI / 2 + (index + 1) * slice - GAP / 2;
            const mid = (start + end) / 2;
            const fillR = INNER + (OUTER - INNER) * Math.min(1, row.score / MAX_SCORE);
            const labelR = OUTER + 16;
            const label = polar(CX, CY, labelR, mid);
            const abbr =
              PLANET_SHORT[row.planet] ?? row.planet.slice(0, 2).toUpperCase();

            return (
              <g key={row.planet}>
                <path
                  className="nk-vim-wedge-bg"
                  d={annularWedge(start, end, INNER, OUTER)}
                />
                <path
                  className={`nk-vim-wedge nk-vim-wedge-${band(row.score)}`}
                  d={annularWedge(start, end, INNER, Math.max(INNER + 2, fillR))}
                >
                  <title>
                    {row.planet}: {row.score.toFixed(1)} / 20 ({bandLabel(row.score)})
                  </title>
                </path>
                <text
                  className="nk-vim-wedge-label"
                  x={label.x}
                  y={label.y}
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {abbr}
                </text>
              </g>
            );
          })}

          <circle className="nk-vim-hub" cx={CX} cy={CY} r={INNER - 4} />
          <text className="nk-vim-hub-score" x={CX} y={CY - 4} textAnchor="middle">
            {avg.toFixed(1)}
          </text>
          <text className="nk-vim-hub-caption" x={CX} y={CY + 12} textAnchor="middle">
            avg
          </text>
        </svg>
      </div>

      <div className="nk-vim-side">
        <ChartLegend
          title="Vimshopaka legend"
          items={[
            {
              id: "strong",
              label: "Strong",
              hint: "score 15-20",
              swatchClassName: "is-vim-strong",
            },
            {
              id: "moderate",
              label: "Moderate",
              hint: "score 10-14.9",
              swatchClassName: "is-vim-moderate",
            },
            {
              id: "weak",
              label: "Weak",
              hint: "score under 10",
              swatchClassName: "is-vim-weak",
            },
            {
              id: "radius",
              label: "Wedge length",
              hint: "how close the planet is to 20",
              swatchClassName: "is-vim-radius",
            },
            {
              id: "avg",
              label: "Center average",
              hint: "mean across planets",
              swatchClassName: "is-vim-avg",
            },
          ]}
        />

        <ul className="nk-vim-legend">
          {rows.map((row) => (
            <li key={row.planet} className={`nk-vim-legend-item is-${band(row.score)}`}>
              <span className="nk-vim-legend-planet">{row.planet}</span>
              <span className="nk-vim-legend-bar" aria-hidden>
                <span
                  className="nk-vim-legend-fill"
                  style={{ width: `${(row.score / MAX_SCORE) * 100}%` }}
                />
              </span>
              <span className="nk-vim-legend-score data">{row.score.toFixed(1)}</span>
              <span className="nk-vim-legend-band">{bandLabel(row.score)}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="nk-vim-chart-note">
        Scale 0-20
        {strongest
          ? ` · strongest: ${strongest.planet} ${strongest.score.toFixed(1)}`
          : ""}
        .
      </p>
    </div>
  );
}
