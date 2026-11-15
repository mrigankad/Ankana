"use client";

import { useEffect, useState } from "react";
import { BookOpen, Orbit } from "lucide-react";

export interface ChartReadingItem {
  title: string;
  text: string;
  evidence: string[];
}

export interface ChartReadingSection {
  key: string;
  title: string;
  items: ChartReadingItem[];
}

export interface LifeChapter {
  key: string;
  title: string;
  ageRange: { from: number; to: number | null };
  years?: { start: string; end: string };
  dashas: Array<{
    planet: string;
    level: "mahadasha";
    start: string;
    end: string;
    ageFrom: number;
    ageTo: number;
  }>;
  summary: string;
  items: ChartReadingItem[];
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

export interface ChartReading {
  generatedAt: string;
  engineVersion: string;
  sections: ChartReadingSection[];
  lifeStory?: LifeStory;
}

type LifeLens = "hybrid" | "ageBands" | "dashaChapters";

const LENS_STORAGE_KEY = "nk-life-story-lens";

const LENS_OPTIONS: Array<{ key: LifeLens; label: string }> = [
  { key: "hybrid", label: "Hybrid" },
  { key: "ageBands", label: "Age bands" },
  { key: "dashaChapters", label: "Dasha chapters" },
];

function EvidenceList({ item }: { item: ChartReadingItem }) {
  return (
    <details className="nk-reading-evidence">
      <summary>Evidence ({item.evidence.length})</summary>
      <ul>
        {item.evidence.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </details>
  );
}

function LifeStoryBlock({
  lifeStory,
  engineVersion,
}: {
  lifeStory: LifeStory;
  engineVersion: string;
}) {
  const [lens, setLens] = useState<LifeLens>("hybrid");

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(LENS_STORAGE_KEY);
      if (
        stored === "hybrid" ||
        stored === "ageBands" ||
        stored === "dashaChapters"
      ) {
        setLens(stored);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(LENS_STORAGE_KEY, lens);
    } catch {
      // ignore
    }
  }, [lens]);

  const chapters = lifeStory.lenses[lens];

  return (
    <div className="nk-life-story" id="your-life">
      <h2 className="nk-h2">
        <Orbit size={16} aria-hidden /> Your Life
      </h2>
      <p className="nk-muted">
        Life chapters from the birth chart and Vimshottari timeline.
        Client-facing summary first; expand evidence for placements.
      </p>
      <p className="nk-muted font-data text-[0.75rem]">
        Born {lifeStory.birthDate} · age {lifeStory.currentAgeYears} · engine{" "}
        {engineVersion}
      </p>

      <div
        className="nk-life-lens"
        role="tablist"
        aria-label="Life story lens"
      >
        {LENS_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            type="button"
            role="tab"
            aria-selected={lens === opt.key}
            className="nk-life-lens-btn"
            data-active={lens === opt.key ? "true" : "false"}
            onClick={() => setLens(opt.key)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="nk-life-chapters">
        {chapters.map((chapter) => (
          <article
            key={chapter.key}
            className="nk-life-chapter"
            data-current={chapter.isCurrent ? "true" : "false"}
          >
            <header className="nk-life-chapter-header">
              <h3 className="nk-life-chapter-title">{chapter.title}</h3>
              {chapter.isCurrent ? (
                <span className="nk-life-now">Now</span>
              ) : null}
            </header>
            {chapter.years ? (
              <p className="nk-muted font-data text-[0.75rem]">
                {chapter.years.start} – {chapter.years.end}
                {chapter.ageRange.to == null
                  ? ` · ages ${chapter.ageRange.from}+`
                  : ` · ages ${chapter.ageRange.from}–${chapter.ageRange.to}`}
              </p>
            ) : null}
            <p className="nk-life-summary">{chapter.summary}</p>
            <ul className="m-0 list-none p-0">
              {chapter.items.map((item) => (
                <li key={item.title} className="nk-reading-item">
                  <p className="nk-reading-item-title">{item.title}</p>
                  <p className="nk-reading-item-text">{item.text}</p>
                  <EvidenceList item={item} />
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </div>
  );
}

export function ReadingPanel({ reading }: { reading: ChartReading }) {
  return (
    <section className="nk-card" aria-label="Reading" id="reading">
      {reading.lifeStory ? (
        <>
          <LifeStoryBlock
            lifeStory={reading.lifeStory}
            engineVersion={reading.engineVersion}
          />
          <hr className="nk-life-divider" />
        </>
      ) : null}

      <h2 className="nk-h2">
        <BookOpen size={16} aria-hidden /> Deep reading
      </h2>
      <p className="nk-muted">
        Deterministic interpretation with evidence for every claim. Expand a
        section item to see the placements that produced it.
      </p>
      <p className="nk-muted font-data text-[0.75rem]">
        Engine {reading.engineVersion} · generated{" "}
        {reading.generatedAt.slice(0, 19)}
      </p>

      <div className="nk-reading-sections">
        {reading.sections.map((section) => (
          <article key={section.key} className="nk-reading-section">
            <h3 className="nk-reading-section-title">{section.title}</h3>
            <ul className="m-0 list-none p-0">
              {section.items.map((item) => (
                <li key={item.title} className="nk-reading-item">
                  <p className="nk-reading-item-title">{item.title}</p>
                  <p className="nk-reading-item-text">{item.text}</p>
                  <EvidenceList item={item} />
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}
