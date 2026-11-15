// Generates lib/fixtures/ananya.generated.json from packages/astrology-core and packages/lal-kitab.
// Run: pnpm --filter @astro/web-practitioner exec tsx scripts/gen-fixtures.ts
import { writeFileSync } from "node:fs";
import { computeVedicChartArtifact } from "../../../packages/astrology-core/src/index";
import { lalKitabReport } from "../../../packages/lal-kitab/src/index";

const artifact = computeVedicChartArtifact({
  birthDate: "1995-03-15",
  birthTime: "06:42",
  timezoneName: "Asia/Kolkata",
  latitude: 25.3176,
  longitude: 82.9739,
  placeLabel: "Varanasi, Uttar Pradesh, India",
});
const lalKitab = lalKitabReport(artifact, { now: new Date("2026-11-14T00:00:00Z") });
writeFileSync(
  new URL("../lib/fixtures/ananya.generated.json", import.meta.url),
  JSON.stringify({ artifact, lalKitab }, null, 1),
);
console.log("ok", artifact.ascendant);
