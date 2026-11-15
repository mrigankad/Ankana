import { SIGN_NAMES, type TransitEvent, type TransitSnapshot } from "@astro/astrology-core";

import type { TransitEventV1, TransitTimelineV1 } from "./live";

const idx = (name: string) => SIGN_NAMES.findIndex((s) => name.toLowerCase().startsWith(s.toLowerCase()));
const CASTS: Record<string, number[]> = {
  mars: [7, 4, 8],
  jupiter: [7, 5, 9],
  saturn: [7, 3, 10],
  rahu: [5, 7, 9],
  ketu: [5, 7, 9],
};
const casts = (planet: string) => CASTS[planet] ?? [7];
const house = (from: number, to: number) => ((to - from + 12) % 12) + 1;

/** Shapes the offline transit computation into the same timeline the live API returns, so both modes render one component. */
export function timelineFromCore(snapshot: TransitSnapshot, events: TransitEvent[], chartId: string): TransitTimelineV1 {
  const ref = snapshot.planets.find((p) => p.houseFromLagna && p.houseFromMoon);
  const refSign = ref ? idx(ref.signName) : 0;
  const lagna = ref ? (refSign - (ref.houseFromLagna - 1) + 12) % 12 : 0;
  const moon = ref ? (refSign - (ref.houseFromMoon - 1) + 12) % 12 : 0;
  const mapped: TransitEventV1[] = events.flatMap((e) => {
    // Ingress detail ends with the new sign; stations carry the sign in the detail too, falling back to the first name found.
    const found = SIGN_NAMES.find((s) => e.detail.includes(s));
    const sign = found ? SIGN_NAMES.indexOf(found) : 0;
    const base: TransitEventV1 = {
      date: e.date,
      planet: e.planet.toLowerCase(),
      kind: e.kind,
      sign: SIGN_NAMES[sign].toLowerCase(),
      sign_index: sign,
      house_from_lagna: house(lagna, sign),
      house_from_moon: house(moon, sign),
      target: null,
      aspect: null,
      phase: null,
    };
    if (e.kind !== "ingress") return [base];
    // Graha drishti is checked when a planet changes sign, as the backend does.
    const out: TransitEventV1[] = [base];
    for (const [target, natalSign] of [["moon", moon], ["lagna", lagna]] as const) {
      const n = house(sign, natalSign);
      if (n === 1) out.push({ ...base, kind: "conjunction", target, aspect: 1 });
      else if (casts(base.planet).includes(n)) out.push({ ...base, kind: "aspect", target, aspect: n });
    }
    return out;
  });
  const sorted = [...mapped].sort((a, b) => a.date.localeCompare(b.date));
  return {
    chart_id: chartId,
    start: sorted[0]?.date ?? snapshot.date,
    end: sorted[sorted.length - 1]?.date ?? snapshot.date,
    months: 24,
    natal: { lagna_sign: SIGN_NAMES[lagna].toLowerCase(), moon_sign: SIGN_NAMES[moon].toLowerCase() },
    sade_sati: {
      active_now: snapshot.sadeSati.active,
      phase_now: snapshot.sadeSati.phase,
      phases: snapshot.sadeSati.active && snapshot.sadeSati.phase ? [{ phase: snapshot.sadeSati.phase, starts_at: null, ends_at: null }] : [],
    },
    events: sorted,
  };
}
