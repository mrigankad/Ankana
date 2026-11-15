/** Lightweight reading payload for assistant tools (matches Python build_reading). */

export interface ReadingItem {
  title: string;
  text: string;
  evidence: string[];
}

export interface ReadingSection {
  key: string;
  title: string;
  items: ReadingItem[];
}

export interface LifeChapter {
  key: string;
  title: string;
  ageRange: { from: number; to: number | null };
  years?: { start: string; end: string };
  dashas: Array<{
    planet: string;
    level: string;
    start: string;
    end: string;
    ageFrom: number;
    ageTo: number;
  }>;
  summary: string;
  items: ReadingItem[];
  isCurrent?: boolean;
}

export interface LifeStory {
  generatedAt: string;
  birthDate: string;
  currentAgeYears: number;
  lenses: {
    hybrid: LifeChapter[];
    ageBands: LifeChapter[];
    dashaChapters: LifeChapter[];
  };
}

export interface ChartReadingContext {
  generatedAt: string;
  engineVersion: string;
  sections: ReadingSection[];
  lifeStory?: LifeStory;
}

export type LifeStoryLens = keyof LifeStory["lenses"];

export const LIFE_STORY_LENSES: LifeStoryLens[] = [
  "hybrid",
  "ageBands",
  "dashaChapters",
];

export function isLifeStoryLens(value: unknown): value is LifeStoryLens {
  return (
    typeof value === "string" &&
    (LIFE_STORY_LENSES as string[]).includes(value)
  );
}
