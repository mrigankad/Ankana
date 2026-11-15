import type { VedicChartArtifact } from "@astro/astrology-core";

import type { ChartReading, ChartReadingItem, LifeChapter } from "@/components/reading-panel";
import { cap, ordinal } from "./chart-views";

/** What each planet colours in a life chapter; plain wording for a client to read. */
const THEME: Record<string, { years: string; focus: string; care: string }> = {
  ketu: { years: "Early years", focus: "a quiet, inward start, with lessons learned by letting go", care: "Steady routines help the child feel settled." },
  venus: { years: "Growing up and learning", focus: "study, friendships, taste and the first serious relationships", care: "Comfort can crowd out discipline, so keep habits simple and regular." },
  sun: { years: "Finding your footing", focus: "authority, recognition and the question of who you answer to", care: "Pride in the work is a strength; stubbornness with seniors is the risk." },
  moon: { years: "The years of the mind", focus: "feelings, home, public contact and everyday work done with care", care: "Moods swing with the Moon, so rest and routine are part of the plan." },
  mars: { years: "Drive and effort", focus: "energy, property, courage and competition", care: "Anger and haste are the cost of this much drive. Channel it into one project at a time." },
  rahu: { years: "Ambition and change", focus: "reinvention, foreign or unusual paths and rapid gains", care: "Gains come fast and can leave as fast. Keep records and avoid shortcuts." },
  jupiter: { years: "Wisdom and ease", focus: "teaching, family, faith and a wider view", care: "Weight and complacency creep in. Keep learning." },
  saturn: { years: "Later life", focus: "duty, patience and a slower pace", care: "Health needs regular attention." },
  mercury: { years: "Late years", focus: "reading, trade, conversation", care: "Keep the mind engaged." },
};

type Dasha = VedicChartArtifact["vimshottari"]["mahadashas"][number];

function ageAt(birth: Date, iso: string) {
  return Math.max(0, Math.round((new Date(iso).getTime() - birth.getTime()) / (365.2425 * 86_400_000)));
}

function chapterFor(a: VedicChartArtifact, m: Dasha, birth: Date, now: Date): LifeChapter {
  const p = a.planets.find((x) => x.planet === m.planet);
  const theme = THEME[m.planet] ?? THEME.ketu!;
  const name = cap(m.planet);
  const from = ageAt(birth, m.start);
  const to = ageAt(birth, m.end);
  const start = m.start.slice(0, 4);
  const end = m.end.slice(0, 4);
  const where = p ? `${name} sits in ${p.signName} in the ${ordinal(p.house)} house` : `${name} leads this period`;
  const dignity = p && p.dignity !== "neutral" && p.dignity !== "friend" ? `, ${p.dignity}` : "";
  const items: ChartReadingItem[] = [
    {
      title: "What this period is about",
      text: `${name} years bring ${theme.focus}. ${where}, so these themes show up through that part of life.`,
      evidence: [`${name} mahadasha ${start} to ${end}`, p ? `${name} in ${p.signName}, house ${p.house}${dignity}` : `${name} mahadasha`],
    },
    {
      title: "What to watch",
      text: theme.care,
      evidence: p ? [`${name}${p.retrograde ? " retrograde" : ""}, ${p.dignity}`, `Lagna ${a.ascendant.signName}`] : [`Lagna ${a.ascendant.signName}`],
    },
  ];
  const isCurrent = new Date(m.start) <= now && now < new Date(m.end);
  return {
    key: `${m.planet}-${start}`,
    title: `${name} years, ${start} to ${end}`,
    ageRange: { from, to },
    years: { start: m.start, end: m.end },
    dashas: [{ planet: m.planet, level: "mahadasha", start: m.start, end: m.end, ageFrom: from, ageTo: to }],
    summary: `${theme.years}: ${theme.focus}.`.replace(/^./, (c) => c.toUpperCase()),
    items,
    isCurrent,
  };
}

/** A deterministic sample deep reading built from the chart itself, so fixtures mode shows the real Reading tab layout. */
export function fixtureReading(a: VedicChartArtifact, now = new Date()): ChartReading {
  const birth = new Date(a.calculationMetadata.input.birthDate);
  const chapters = a.vimshottari.mahadashas.filter((m) => ageAt(birth, m.start) < 80).map((m) => chapterFor(a, m, birth, now));
  return {
    generatedAt: now.toISOString(),
    engineVersion: "sample",
    sections: [],
    lifeStory: {
      generatedAt: now.toISOString(),
      birthDate: a.calculationMetadata.input.birthDate,
      currentAgeYears: Math.floor((now.getTime() - birth.getTime()) / (365.2425 * 86_400_000)),
      lenses: { hybrid: chapters, ageBands: chapters, dashaChapters: chapters },
    },
  };
}
