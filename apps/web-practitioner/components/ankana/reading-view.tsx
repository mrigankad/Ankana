"use client";

import { useMemo, useState } from "react";

import type { ChartReading, LifeChapter } from "@/components/reading-panel";
import { SampleBadge } from "@/components/ankana/server-unavailable";
import { cn } from "@/lib/utils";

function ageLabel(c: LifeChapter) {
  return c.ageRange.to === null ? `Ages ${c.ageRange.from} onward` : `Ages ${c.ageRange.from} to ${c.ageRange.to}`;
}

function Pill({ children }: { children: string }) {
  return (
    <span className="rounded-full border border-rule px-[10px] py-1 text-[12px] font-bold leading-[14px] text-accent-text">{children}</span>
  );
}

/** Reading tab (Paper U07): life chapters rail on the left, the chapter as prose with evidence chips. */
export function ReadingView({ reading, clientFirstName, sample }: { reading: ChartReading; clientFirstName?: string; sample?: boolean }) {
  const chapters = useMemo<LifeChapter[]>(() => reading.lifeStory?.lenses.hybrid ?? reading.lifeStory?.lenses.dashaChapters ?? [], [reading]);
  const currentIdx = Math.max(0, chapters.findIndex((c) => c.isCurrent));
  const [picked, setPicked] = useState<string | null>(null);
  const active = chapters.find((c) => c.key === picked) ?? chapters[currentIdx];

  const claims = useMemo(() => (active ? active.items.reduce((n, i) => n + i.evidence.length, 0) : 0), [active]);

  if (!chapters.length || !active) {
    // No life story: fall back to the flat sections so the tab is never empty.
    return (
      <div className="flex flex-col gap-6 px-4 py-[22px] sm:px-8">
        {reading.sections.map((s) => (
          <section key={s.key} className="flex flex-col gap-[10px]">
            <h2 className="m-0 text-[22px] font-bold leading-7 tracking-[-0.01em] text-ink">{s.title}</h2>
            {s.items.map((it) => (
              <div key={it.title} className="flex flex-col gap-[10px]">
                <p className="m-0 text-[17px] leading-7 text-ink">{it.text}</p>
                <div className="flex flex-wrap gap-[6px]">{it.evidence.map((e) => <Pill key={e}>{e}</Pill>)}</div>
              </div>
            ))}
          </section>
        ))}
      </div>
    );
  }

  return (
    <div className="flex min-h-0 grow flex-col gap-6 px-4 py-[22px] sm:px-8 lg:flex-row lg:gap-7">
      <nav aria-label="Life chapters" className="flex shrink-0 gap-1 overflow-x-auto lg:w-44 lg:flex-col lg:overflow-visible">
        <div className="hidden px-[10px] pb-2 text-[12px] font-bold leading-4 tracking-[0.06em] text-soft lg:block">LIFE CHAPTERS</div>
        {chapters.map((c) => {
          const on = c.key === active.key;
          return (
            <button
              key={c.key}
              type="button"
              aria-current={on ? "true" : undefined}
              onClick={() => setPicked(c.key)}
              className={cn("flex shrink-0 flex-col gap-[2px] rounded-[6px] px-[10px] py-2 text-left", on && "bg-wash")}
            >
              <span className={cn("text-[14px] font-bold leading-[18px]", on ? "text-ink" : "text-body")}>{c.title}</span>
              <span className={cn("text-[12px] leading-4", on ? "font-bold text-accent-text" : "text-soft")}>
                {c.ageRange.to === null ? `Ages ${c.ageRange.from} onward` : `Ages ${c.ageRange.from} to ${c.ageRange.to}`}
                {c.isCurrent ? ", now" : ""}
              </span>
            </button>
          );
        })}
      </nav>

      <article className="flex min-w-0 grow basis-0 flex-col gap-[18px]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-wash px-[10px] py-1 text-[12px] font-bold leading-[14px] text-accent-text">
              {clientFirstName ? `Draft for ${clientFirstName}` : "Draft"}
            </span>
            {sample ? <SampleBadge /> : <span className="rounded-full bg-ok-wash px-[10px] py-1 text-[12px] font-bold leading-[14px] text-ok">{claims} claims verified</span>}
          </div>
        </div>
        <header className="flex flex-col gap-[6px]">
          <div className="text-[13px] font-bold leading-4 text-soft">{ageLabel(active)}</div>
          <h2 className="m-0 text-[32px] font-bold leading-[38px] tracking-[-0.02em] text-ink">{active.title}</h2>
        </header>
        {active.summary ? <p className="m-0 text-[17px] leading-7 text-ink">{active.summary}</p> : null}
        {active.items.map((it) => (
          <section key={`${it.title}-${it.text.slice(0, 20)}`} className="flex flex-col gap-[10px]">
            <p className="m-0 text-[17px] leading-7 text-ink">{it.text}</p>
            {it.evidence.length ? (
              <div className="flex flex-wrap gap-[6px]">
                {it.evidence.map((e) => (
                  <Pill key={e}>{e}</Pill>
                ))}
              </div>
            ) : null}
          </section>
        ))}
      </article>
    </div>
  );
}
