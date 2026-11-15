"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Btn } from "@/components/ankana/ui";
import { cap, capNames } from "@/lib/api/chart-views";
import { v1Api } from "@/lib/api/live";
import { problemMessage } from "@/lib/api/v1";
import type { ChartBundle } from "@/lib/api/types";
import { cn } from "@/lib/utils";

interface Cite {
  printed_page?: number;
  vol?: string;
}
interface Upay {
  rank: number;
  kind: string;
  planet: string;
  house: number;
  title: string;
  action: string;
  why: string;
  durationDays?: number;
  cites?: Cite[];
  needs_review?: boolean;
}
export interface ParashariRemedy {
  kind: string;
  planet: string;
  title: string;
  practice: string;
  rationale: string;
  strengthOfRecommendation?: string;
  cautions?: string[];
}

const GAP_DAYS = 4;
const BAR_CLASSES = ["bg-ink", "bg-sindoor", "bg-accent-light", "bg-accent-light", "bg-accent-light"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const dm = (d: Date) => `${d.getDate()} ${MONTHS[d.getMonth()]}`;
const isoDay = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Friendly heading from the book title: "Awaken venus (via jupiter)" style titles read fine; trim the trailing detail. */
function headline(u: Upay) {
  const t = u.title.replace(/:.*$/, "").replace(/\s*\(([^)]*)\)\s*$/, (_, g: string) => `, ${g}`);
  return cap(t).replace(/\b(jupiter|mercury|venus|saturn|moon|sun|mars|rahu|ketu)\b/g, (m) => cap(m));
}
function subline(u: Upay) {
  return `${cap(u.planet)}, H${u.house}`;
}
function pages(u: Upay) {
  const p = Array.from(new Set((u.cites ?? []).map((c) => c.printed_page).filter(Boolean)));
  return p.length ? `Vol ${u.cites?.[0]?.vol ?? "I"} p.${p.join(", ")}` : "";
}
function firstSentence(s: string) {
  const m = /^(.*?[.!?])(\s|$)/.exec(s);
  return m ? m[1]! : s;
}

function LkBadge() {
  return (
    <span className="flex items-center gap-[5px] rounded-full bg-alert-wash px-[9px] py-[2px]">
      <span className="size-[6px] shrink-0 rounded-[2px] bg-alert" />
      <span className="text-[12px] font-bold leading-4 text-alert">Lal Kitab</span>
    </span>
  );
}

const CARD_SHADOW = "0 1px 2px rgba(34,30,29,0.04), 0 6px 18px rgba(34,30,29,0.04)";

/**
 * Remedies tab (Paper U09): ranked upay builder, one at a time, schedule, and the wording the
 * client will read. "Start plan" saves a remedy plan through /v1 and starts it.
 */
export function RemediesView({
  bundle,
  parashari,
  live,
}: {
  bundle: ChartBundle;
  parashari: ParashariRemedy[] | null;
  live: boolean;
}) {
  const remedies = bundle.lalKitab.remedies as { upay?: Upay[] } | undefined;
  const all = useMemo(
    () => (remedies?.upay ?? []).map((u) => ({ ...u, title: capNames(u.title), action: capNames(u.action), why: capNames(u.why) })),
    [remedies],
  );
  const [filter, setFilter] = useState<"all" | "lk" | "parashari">("all");
  const [showAll, setShowAll] = useState(false);
  const [editing, setEditing] = useState(false);
  const [wording, setWording] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<string | null>(null);

  const list = showAll ? all : all.slice(0, 5);
  const start = useMemo(() => {
    const t = new Date();
    const d = new Date(t.getFullYear(), t.getMonth(), t.getDate());
    return addDays(d, (8 - d.getDay()) % 7 || 7); // next Monday
  }, []);

  const phases = list.map((u, i) => {
    const days = u.durationDays ?? 43;
    const from = addDays(start, list.slice(0, i).reduce((n, x) => n + (x.durationDays ?? 43) + GAP_DAYS, 0));
    return { u, from, to: addDays(from, days - 1), days };
  });
  const span = phases.length ? (phases.at(-1)!.to.getTime() - start.getTime()) / 86_400_000 + 1 : 1;

  const first = phases[0];
  const second = phases[1];
  const defaultWording = first
    ? `For the next ${first.days} days, please follow one practice only. ${firstSentence(first.u.action)} ${
        second ? `We will begin the next practice on ${dm(second.from)}, once these ${first.days} days are complete.` : ""
      }`.trim()
    : "";
  const text = wording ?? defaultWording;
  const firstName = bundle.client.name.split(" ")[0] ?? bundle.client.name;

  async function startPlan() {
    if (!live || !first) return;
    setBusy(true);
    setError("");
    try {
      const plan = await v1Api.createRemedyPlan(bundle.client.id, {
        title: headline(first.u),
        cycle_days: first.days,
        missed_day_policy: "restart",
        items: [{ title: headline(first.u), instructions: text, planet: first.u.planet }],
      });
      await v1Api.startRemedyPlan(plan.id, isoDay(start));
      setSaved(plan.id);
    } catch (cause) {
      setError(problemMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  const showLk = filter !== "parashari";
  const showPar = filter !== "lk";

  return (
    <div className="flex min-h-0 grow flex-col gap-6 px-4 py-5 sm:px-8 xl:flex-row">
      <div className="flex min-w-0 flex-col gap-[10px] xl:w-[700px] xl:shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-baseline gap-2">
            <h2 className="m-0 text-[18px] font-bold leading-6 text-ink">Remedy plan builder</h2>
            <span className="text-[13px] leading-4 text-soft">{list.length} ranked upay, one at a time</span>
          </div>
          <div role="tablist" aria-label="Remedy source" className="flex rounded-full border border-rule p-[2px]">
            {(
              [
                ["all", "All"],
                ["lk", "Lal Kitab"],
                ["parashari", "Parashari"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={filter === id}
                onClick={() => setFilter(id)}
                className={cn("rounded-full px-3 py-1 text-[12px] leading-4", filter === id ? "bg-ink font-bold text-white" : "text-body")}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {showLk
          ? phases.map(({ u, from, to, days }, i) => (
              <article
                key={`${u.rank}-${u.title}`}
                className={cn("flex gap-[14px] rounded-2xl border bg-white px-[18px] py-3", i === 0 ? "border-ink" : "border-rule")}
                style={{ boxShadow: CARD_SHADOW }}
              >
                <div className={cn("flex size-7 shrink-0 items-center justify-center rounded-full text-[13px] font-bold leading-4", i === 0 ? "bg-ink text-white" : "bg-sidebar-wash text-body")}>
                  {i + 1}
                </div>
                <div className="flex min-w-0 grow basis-0 flex-col gap-[6px]">
                  <div className="flex flex-wrap items-center gap-2">
                    <LkBadge />
                    <span className="text-[12px] leading-4 text-soft">{subline(u)}</span>
                    <span className="grow" />
                    {u.needs_review ? <span className="rounded-full bg-wash px-[9px] py-[2px] text-[12px] font-bold leading-4 text-accent-text">Needs review</span> : null}
                    <span className={cn("rounded-full px-[9px] py-[2px] text-[12px] font-bold leading-4", i === 0 ? "bg-ok-wash text-ok" : "bg-sidebar-wash text-body")}>
                      {i === 0 ? "Starts first" : `After ${i}`}
                    </span>
                  </div>
                  <h3 className="m-0 text-[16px] font-bold leading-5 text-ink">{headline(u)}</h3>
                  <p className="m-0 text-[13px] leading-[18px] text-body">{u.action}</p>
                  <div className="flex items-center gap-[6px] text-[12px] leading-4">
                    <span className="font-bold text-ink">
                      {days} days, {dm(from)} to {dm(to)}
                    </span>
                    {pages(u) ? (
                      <>
                        <span className="text-soft">·</span>
                        <span className="text-accent-text">{pages(u)}</span>
                      </>
                    ) : null}
                  </div>
                </div>
              </article>
            ))
          : null}
        {showLk && all.length > 5 ? (
          <button type="button" onClick={() => setShowAll((v) => !v)} className="self-start text-[13px] font-bold leading-4 text-accent-text">
            {showAll ? "Show the first 5" : `Show all ${all.length} upay`}
          </button>
        ) : null}
        {showLk && !all.length ? <p className="m-0 text-[14px] text-body">The Lal Kitab engine found no upay for this chart.</p> : null}

        {showPar
          ? (parashari ?? []).map((r) => (
              <article key={`${r.planet}-${r.kind}-${r.title}`} className="flex flex-col gap-[6px] rounded-2xl border border-rule bg-white px-[18px] py-3" style={{ boxShadow: CARD_SHADOW }}>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-chip px-[9px] py-[2px] text-[12px] font-bold leading-4 text-ink">Parashari</span>
                  <span className="text-[12px] leading-4 text-soft">
                    {cap(r.planet)}, {r.kind}
                  </span>
                  <span className="grow" />
                  {r.strengthOfRecommendation ? <span className="rounded-full bg-sidebar-wash px-[9px] py-[2px] text-[12px] font-bold leading-4 text-body">{r.strengthOfRecommendation}</span> : null}
                </div>
                <h3 className="m-0 text-[16px] font-bold leading-5 text-ink">{r.title}</h3>
                <p className="m-0 text-[13px] leading-[18px] text-body">{capNames(r.practice)}</p>
                <p className="m-0 text-[12px] leading-4 text-soft">{capNames(r.rationale)}</p>
                {r.cautions?.length ? <p className="m-0 text-[12px] leading-4 text-alert">{r.cautions.join(" ")}</p> : null}
              </article>
            ))
          : null}
        {showPar && parashari && !parashari.length ? <p className="m-0 text-[14px] text-body">No Parashari remedy is called for by this chart.</p> : null}
      </div>

      <div className="flex min-w-0 grow basis-0 flex-col gap-4">
        <section className="flex flex-col gap-3 rounded-2xl border border-rule bg-white px-5 py-4" style={{ boxShadow: CARD_SHADOW }} aria-label="Schedule">
          <div className="flex items-baseline justify-between">
            <h2 className="m-0 text-[17px] font-bold leading-[22px] text-ink">Schedule</h2>
            <span className="text-[12px] leading-4 text-soft">
              Start {DAYS[start.getDay()]} {dm(start)} {start.getFullYear()}
            </span>
          </div>
          <div className="flex flex-col gap-[9px]">
            {phases.map(({ u, from, to, days }, i) => (
              <div key={u.rank} className="flex items-center gap-[10px]">
                <div className="w-[52px] shrink-0 truncate text-[12px] leading-4 text-body">{cap(u.planet)}</div>
                <div className="relative h-[10px] min-w-0 grow rounded-[5px] bg-sidebar-wash">
                  <div
                    className={cn("absolute top-0 h-[10px] rounded-[5px]", BAR_CLASSES[Math.min(i, BAR_CLASSES.length - 1)])}
                    style={{
                      left: `${((from.getTime() - start.getTime()) / 86_400_000 / span) * 100}%`,
                      width: `${(days / span) * 100}%`,
                    }}
                  />
                </div>
                <div className="w-[100px] shrink-0 whitespace-pre text-right text-[12px] leading-4 text-body">
                  {dm(from)}, {dm(to)}
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-[6px] bg-ok-wash px-3 py-2 text-[12px] leading-4 text-ok">
            One upay at a time, 43 days each with a few days between. No overlaps.
          </div>
        </section>

        <section className="flex flex-col gap-[10px] rounded-[10px] border border-rule bg-wash-soft px-[18px] py-4" aria-label="What the client will read">
          <div className="flex items-center justify-between gap-3">
            <h2 className="m-0 grow text-[16px] font-bold leading-5 text-ink">What {firstName} will read</h2>
            <button type="button" onClick={() => setEditing((v) => !v)} className="text-[13px] font-bold leading-4 text-accent-text">
              {editing ? "Done" : "Edit wording"}
            </button>
          </div>
          {editing ? (
            <textarea
              aria-label="Client wording"
              value={text}
              onChange={(e) => setWording(e.target.value)}
              className="min-h-[150px] w-full resize-none rounded-[6px] border border-rule bg-white p-3 text-[15px] leading-[23px] text-ink outline-none focus:border-sindoor"
            />
          ) : (
            <p className="m-0 text-[15px] leading-[23px] text-ink">{text || "No upay to explain yet."}</p>
          )}
          <p className="m-0 text-[12px] leading-4 text-soft">A traditional practice from the Lal Kitab. Advisory only, not a medical or financial prescription.</p>
        </section>

        {error ? (
          <p role="alert" className="m-0 rounded-[6px] bg-alert-wash px-3 py-2 text-[13px] font-bold leading-[18px] text-alert">
            {error}
          </p>
        ) : null}
        {saved ? (
          <p role="status" className="m-0 rounded-[6px] bg-ok-wash px-3 py-2 text-[13px] font-bold leading-[18px] text-ok">
            Plan started. Track check-ins on the client page.{" "}
            <Link href={`/clients/${bundle.client.id}`} className="underline">
              Open client
            </Link>
          </p>
        ) : null}
        <div className="flex gap-[10px]">
          <Btn href={`/charts/${bundle.chartId}/report`} className="grow basis-0 py-[11px]">
            Add to report
          </Btn>
          {live ? (
            <Btn variant="outline" onClick={() => void startPlan()} disabled={busy || !first || Boolean(saved)} className="grow basis-0 py-[10px]">
              {busy ? "Starting" : saved ? "Plan started" : "Start plan with check-ins"}
            </Btn>
          ) : null}
        </div>
      </div>
    </div>
  );
}
