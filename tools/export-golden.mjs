// Export golden chart artifacts from the validated TS engine for the Python port.
// Run: apps/api/node_modules/.bin/tsx tools/export-golden.mjs
import { mkdirSync, writeFileSync } from "node:fs";
import {
  computeVedicChartArtifact,
  computeTransitSnapshot,
  computeTransitTimeline,
} from "../packages/astrology-core/src/index.ts";
import {
  evaluatePredictions,
  evaluateRemedies,
} from "../packages/rule-engine/src/index.ts";

const charts = [
  {
    label: "raiganj-2003",
    input: {
      birthDate: "2003-08-29",
      birthTime: "12:22",
      timezoneName: "Asia/Kolkata",
      latitude: 25.6167,
      longitude: 88.1233,
      placeLabel: "Raiganj, Uttar Dinajpur, West Bengal, India",
    },
  },
  {
    label: "varanasi-1990",
    input: {
      birthDate: "1990-01-01",
      birthTime: "10:30",
      timezoneName: "Asia/Kolkata",
      latitude: 25.3176,
      longitude: 82.9739,
      placeLabel: "Varanasi, India",
    },
  },
  {
    label: "newyork-1985",
    input: {
      birthDate: "1985-06-15",
      birthTime: "23:45",
      timezoneName: "America/New_York",
      latitude: 40.7128,
      longitude: -74.006,
      placeLabel: "New York, USA",
    },
  },
];

const out = charts.map(({ label, input }) => ({
  label,
  input,
  artifact: computeVedicChartArtifact(input),
}));

mkdirSync("services/api-py/tests/golden", { recursive: true });
writeFileSync(
  "services/api-py/tests/golden/charts.json",
  JSON.stringify(out, null, 1),
);
console.log(
  out
    .map((c) => `${c.label}: lagna ${c.artifact.ascendant.signName} ${c.artifact.ascendant.degreesInSign.toFixed(2)}`)
    .join("\n"),
);

// Transit goldens: snapshot for the Raiganj natal chart at a fixed instant,
// plus a half-year event timeline from the same instant.
const transitDate = new Date("2026-07-19T00:00:00.000Z");
const transitGolden = {
  natalLabel: out[0].label,
  snapshot: computeTransitSnapshot(out[0].artifact, transitDate),
  timeline: {
    from: transitDate.toISOString(),
    years: 0.5,
    events: computeTransitTimeline(transitDate, 0.5),
  },
};
writeFileSync(
  "services/api-py/tests/golden/transits.json",
  JSON.stringify(transitGolden, null, 1),
);
console.log(`transits: ${transitGolden.timeline.events.length} timeline events`);

// Rule-engine goldens for the Raiganj chart at a fixed evaluation date.
const rulesGolden = {
  natalLabel: out[0].label,
  from: "2026-07-19T00:00:00.000Z",
  horizonYears: 5,
  predictions: evaluatePredictions(out[0].artifact, {
    from: new Date("2026-07-19T00:00:00.000Z"),
    horizonYears: 5,
  }),
  remedies: evaluateRemedies(out[0].artifact),
};
writeFileSync(
  "services/api-py/tests/golden/rules.json",
  JSON.stringify(rulesGolden, null, 1),
);
console.log(
  `rules: ${rulesGolden.predictions.length} predictions, ${rulesGolden.remedies.length} remedies`,
);
