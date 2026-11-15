"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Hourglass, Orbit, Sparkles, Waypoints, BookOpen, X } from "lucide-react";

import { useDateFmt } from "@/components/ankana/consult-brief";
import { Panel } from "@/components/ankana/ui";
import { Banner } from "@/components/ui/data";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { DateField, TimeField } from "@/components/ui/date-time-fields";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  consultApi,
  onConsultChanged,
  factHref,
  newFactId,
  splitNoteBody,
  type ChartFactOption,
  type ConsultationFull,
  type FactType,
  type NoteFact,
  type NoteFull,
  type PredictionDraft,
  type PredictionStatus,
  type PredictionV1,
  type SummaryBody,
  type SummaryV1,
} from "@/lib/api/consult";
import { problemMessage } from "@/lib/api/v1";
import { useT } from "@/lib/i18n/provider";

const FACT_ICON: Record<FactType, typeof Orbit> = { planet: Orbit, dasha: Hourglass, yoga: Sparkles, transit: Waypoints, lal_kitab: BookOpen };

function Head({ title, note }: { title: string; note?: string }) {
  const t = useT();
  return (
    <div className="flex items-baseline justify-between gap-3">
      <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">{t(title)}</h2>
      {note ? <span className="text-[13px] leading-4 text-soft">{note}</span> : null}
    </div>
  );
}

function ErrorLine({ children }: { children: string }) {
  return children ? <Banner tone="error">{children}</Banner> : null;
}

/* ------------------------------------------------------------------- chips */
export function FactChip({ fact, chartId }: { fact: NoteFact; chartId: string | null }) {
  const t = useT();
  const Icon = FACT_ICON[fact.type];
  const href = factHref(chartId, fact);
  const cls = "mx-[2px] inline-flex max-w-full items-center gap-1 rounded-[4px] border border-accent-line bg-accent-wash px-[6px] py-[1px] align-baseline text-[13px] font-bold leading-[18px] text-accent-text no-underline";
  const inner = (
    <>
      <Icon aria-hidden className="size-[13px] shrink-0" />
      <span className="truncate">{fact.label}</span>
    </>
  );
  return href ? (
    <Link href={href} className={`${cls} hover:border-sindoor`} title={t("Open on the chart")} data-fact-type={fact.type} data-fact-ref={fact.ref}>
      {inner}
    </Link>
  ) : (
    <span className={cls} data-fact-type={fact.type} data-fact-ref={fact.ref}>
      {inner}
    </span>
  );
}

/** A note body with its pinned facts rendered as chips in place. */
export function NoteBody({ body, facts, chartId }: { body: string; facts: NoteFact[]; chartId: string | null }) {
  const parts = useMemo(() => splitNoteBody(body, facts), [body, facts]);
  return (
    <p className="m-0 whitespace-pre-wrap text-[14px] leading-[26px] text-body">
      {parts.map((p, i) => (
        <Fragment key={i}>{"fact" in p ? <FactChip fact={p.fact} chartId={chartId} /> : p.text}</Fragment>
      ))}
    </p>
  );
}

/* ---------------------------------------------------------------- composer */
const token = (label: string) => `[[${label}]]`;

/** Turn the editing text (with [[label]] tokens) into a stored body plus its facts. */
export function encodeNote(text: string, pinned: NoteFact[]): { body: string; facts: NoteFact[] } {
  let body = text;
  const used: NoteFact[] = [];
  for (const f of pinned) {
    const at = body.indexOf(token(f.label));
    if (at < 0) continue; // the practitioner deleted or edited the token: the chip goes too
    body = `${body.slice(0, at)}{{fact:${f.id}}}${body.slice(at + token(f.label).length)}`;
    used.push(f);
  }
  return { body: body.trim(), facts: used };
}

function useFactOptions(clientId: string) {
  const [facts, setFacts] = useState<ChartFactOption[] | null>(null);
  const [chartId, setChartId] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    consultApi.getChartFacts(clientId).then((r) => live && (setFacts(r.facts), setChartId(r.chart_id))).catch(() => live && (setFacts([]), setFailed(true)));
    return () => {
      live = false;
    };
  }, [clientId]);
  return { facts, chartId, failed };
}

/** Free text plus a chart fact picker. Picking a fact drops a chip token where the cursor is. */
export function NoteComposer({
  clientId,
  value,
  onChange,
  pinned,
  onPinned,
  label,
  placeholder,
  rows = 3,
}: {
  clientId: string;
  value: string;
  onChange: (v: string) => void;
  pinned: NoteFact[];
  onPinned: (f: NoteFact[]) => void;
  label: string;
  placeholder: string;
  rows?: number;
}) {
  const t = useT();
  const ref = useRef<HTMLTextAreaElement>(null);
  const { facts, chartId } = useFactOptions(clientId);
  const options: ComboboxOption[] = useMemo(() => (facts ?? []).map((f) => ({ value: f.ref, label: f.label, description: t(f.group) })), [facts, t]);
  const preview = useMemo(() => encodeNote(value, pinned), [value, pinned]);

  function insert(refValue: string | null) {
    const fact = facts?.find((f) => f.ref === refValue);
    if (!fact) return;
    const pin: NoteFact = { id: newFactId(), type: fact.type, ref: fact.ref, label: fact.label };
    const el = ref.current;
    const at = el?.selectionStart ?? value.length;
    const end = el?.selectionEnd ?? at;
    const before = value.slice(0, at);
    const sep = before && !/\s$/.test(before) ? " " : "";
    onChange(`${before}${sep}${token(fact.label)} ${value.slice(end)}`.replace(/ $/, ""));
    onPinned([...pinned, pin]);
    window.setTimeout(() => el?.focus(), 0);
  }

  return (
    <div className="flex flex-col gap-2">
      <Textarea ref={ref} aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={rows} className="min-h-[84px]" />
      <div className="flex flex-wrap items-center gap-2">
        <div className="w-full sm:w-[320px]">
          <Combobox
            value={null}
            onChange={(v) => insert(v)}
            options={options}
            placeholder={t("Pin a chart fact")}
            searchPlaceholder={t("Search planets, periods, yogas, transits")}
            emptyText={facts && facts.length === 0 ? t("This client has no chart yet.") : t("No matching fact")}
            aria-label={t("Pin a chart fact")}
            disabled={!facts || facts.length === 0}
          />
        </div>
        <span className="text-[12px] leading-4 text-soft">{t("It appears as a chip that opens the chart.")}</span>
      </div>
      {preview.facts.length ? (
        <div className="rounded-[6px] border border-rule px-3 py-2" aria-label={t("Preview")}>
          <NoteBody body={preview.body} facts={preview.facts} chartId={chartId} />
        </div>
      ) : null}
    </div>
  );
}

/* ----------------------------------------------------------- tag list input */
function ListEditor({ label, items, onChange, placeholder, addLabel }: { label: string; items: string[]; onChange: (v: string[]) => void; placeholder: string; addLabel: string }) {
  const t = useT();
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim();
    if (v && !items.includes(v)) onChange([...items, v]);
    setDraft("");
  };
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[13px] font-bold leading-4 text-ink">{t(label)}</span>
      {items.length ? (
        <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
          {items.map((it) => (
            <li key={it} className="inline-flex max-w-full items-center gap-1 rounded-[4px] bg-chip py-[3px] pl-2 pr-1 text-[13px] font-bold leading-4 text-ink">
              <span className="truncate">{it}</span>
              <button type="button" aria-label={t("Remove {item}", { item: it })} onClick={() => onChange(items.filter((x) => x !== it))} className="inline-flex size-5 items-center justify-center rounded-[4px] text-body hover:bg-rule">
                <X aria-hidden className="size-3" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="flex gap-2">
        <Input
          aria-label={t(label)}
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button type="button" variant="outline" size="md" onClick={add} disabled={!draft.trim()}>
          {t(addLabel)}
        </Button>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- status helpers */
export const STATUS_OPTIONS: Array<{ value: PredictionStatus; label: string }> = [
  { value: "pending", label: "Pending" },
  { value: "came_true", label: "Came true" },
  { value: "did_not", label: "Did not happen" },
  { value: "unclear", label: "Unclear" },
];
export const STATUS_TONE: Record<PredictionStatus, string> = {
  pending: "bg-chip text-body",
  came_true: "bg-ok-wash text-ok",
  did_not: "bg-alert-wash text-alert",
  unclear: "bg-accent-wash text-accent-text",
};

export function StatusPill({ status }: { status: PredictionStatus }) {
  const t = useT();
  const label = STATUS_OPTIONS.find((s) => s.value === status)?.label ?? status;
  return <span className={`inline-flex shrink-0 items-center rounded-[4px] px-2 py-[2px] text-[12px] font-bold leading-4 ${STATUS_TONE[status]}`}>{t(label)}</span>;
}

/* ------------------------------------------------------------ summary dialog */
const emptyPrediction = (): PredictionDraft => ({ id: null, statement: "", window_start: null, window_end: null });

export function SummaryDialog({ consultation, open, onOpenChange, onSaved }: { consultation: ConsultationFull; open: boolean; onOpenChange: (o: boolean) => void; onSaved: () => void }) {
  const t = useT();
  const [loaded, setLoaded] = useState(false);
  const [topics, setTopics] = useState<string[]>([]);
  const [remedies, setRemedies] = useState<string[]>([]);
  const [followUp, setFollowUp] = useState("");
  const [predictions, setPredictions] = useState<PredictionDraft[]>([]);
  const [resolved, setResolved] = useState<Record<string, PredictionStatus>>({});
  const [source, setSource] = useState<"manual" | "ai">("manual");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"" | "save" | "draft">("");
  const [warnings, setWarnings] = useState<Array<{ text: string; reason: string; correct: string }>>([]);
  const [drafted, setDrafted] = useState(false);

  const apply = useCallback((s: SummaryV1 | SummaryBody | null) => {
    setTopics(s?.topics ?? (consultation.topic ? [consultation.topic] : []));
    setRemedies(s?.remedies_given ?? []);
    setFollowUp(s?.follow_up_date ?? consultation.follow_up_date ?? "");
    setPredictions((s?.predictions ?? []).map((p) => ({ id: (p as PredictionV1).id ?? null, statement: p.statement, window_start: p.window_start, window_end: p.window_end })));
    setResolved(Object.fromEntries(((s?.predictions ?? []) as PredictionV1[]).filter((p) => p.id && p.status !== "pending").map((p) => [p.id, p.status])));
    setSource(s?.source ?? "manual");
  }, [consultation.topic, consultation.follow_up_date]);

  useEffect(() => {
    if (!open) return;
    setLoaded(false);
    setError("");
    setWarnings([]);
    setDrafted(false);
    consultApi.getSummary(consultation.id).then((s) => apply(s)).catch((e) => setError(problemMessage(e))).finally(() => setLoaded(true));
  }, [open, consultation.id, apply]);

  const badWindow = predictions.some((p) => p.window_start && p.window_end && p.window_end < p.window_start);

  async function save() {
    setBusy("save");
    setError("");
    try {
      await consultApi.saveSummary(consultation.id, {
        topics,
        remedies_given: remedies,
        follow_up_date: followUp || null,
        predictions: predictions.filter((p) => p.statement.trim()),
        source,
      });
      onSaved();
      onOpenChange(false);
    } catch (e) {
      setError(problemMessage(e));
    } finally {
      setBusy("");
    }
  }

  async function draft() {
    setBusy("draft");
    setError("");
    try {
      const r = await consultApi.draftSummary(consultation.id);
      const keep = predictions.filter((p) => p.id);
      apply({ ...r.summary, topics: r.summary.topics, predictions: [...keep, ...r.summary.predictions] });
      setSource("ai");
      setDrafted(true);
      setWarnings(r.verification.mismatches);
    } catch (e) {
      setError(problemMessage(e));
    } finally {
      setBusy("");
    }
  }

  const setPred = (i: number, patch: Partial<PredictionDraft>) => setPredictions((ps) => ps.map((p, j) => (j === i ? { ...p, ...patch } : p)));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-32px)] max-w-[680px] gap-4 overflow-y-auto">
        <div className="flex flex-col gap-1">
          <DialogTitle>{t("Session summary")}</DialogTitle>
          <DialogDescription>{consultation.topic || t("Consultation")}</DialogDescription>
        </div>
        <ErrorLine>{error}</ErrorLine>
        {drafted ? (
          <Banner tone={warnings.length ? "warning" : "info"} title={warnings.length ? t("Check the draft against the chart") : t("Draft ready to review")}>
            {warnings.length ? (
              <ul className="m-0 list-disc pl-4">
                {warnings.map((w, i) => (
                  <li key={i}>{t("{text}: {reason}. Chart says: {fact}", { text: w.text, reason: w.reason, fact: w.correct })}</li>
                ))}
              </ul>
            ) : (
              t("The draft matches the chart. Nothing is saved until you save it.")
            )}
          </Banner>
        ) : null}

        {!loaded ? (
          <p className="m-0 text-[14px] leading-5 text-body">{t("Loading")}</p>
        ) : (
          <div className="flex flex-col gap-5">
            <ListEditor label="Topics discussed" items={topics} onChange={setTopics} placeholder={t("For example Career change")} addLabel="Add topic" />

            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-bold leading-4 text-ink">{t("Predictions made")}</span>
              {predictions.length === 0 ? <p className="m-0 text-[13px] leading-4 text-soft">{t("Predictions you record are kept so you can note later whether they came true.")}</p> : null}
              {predictions.map((p, i) => (
                <div key={p.id ?? `new-${i}`} className="flex flex-col gap-2 rounded-[6px] border border-rule p-3">
                  <div className="flex items-start gap-2">
                    <Input aria-label={t("Prediction")} value={p.statement} onChange={(e) => setPred(i, { statement: e.target.value })} placeholder={t("What was predicted")} />
                    {p.id && resolved[p.id] ? (
                      <StatusPill status={resolved[p.id]!} />
                    ) : (
                      <Button type="button" variant="ghost" size="icon" aria-label={t("Remove prediction")} onClick={() => setPredictions((ps) => ps.filter((_, j) => j !== i))}>
                        <X aria-hidden className="size-4" />
                      </Button>
                    )}
                  </div>
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="flex min-w-[170px] grow basis-0 flex-col gap-1">
                      <span className="text-[12px] font-bold leading-4 text-soft">{t("Window starts")}</span>
                      <DateField aria-label={t("Window starts")} value={p.window_start ?? ""} onChange={(v) => setPred(i, { window_start: v || null })} showWeekday={false} />
                    </div>
                    <div className="flex min-w-[170px] grow basis-0 flex-col gap-1">
                      <span className="text-[12px] font-bold leading-4 text-soft">{t("Window ends")}</span>
                      <DateField aria-label={t("Window ends")} value={p.window_end ?? ""} onChange={(v) => setPred(i, { window_end: v || null })} showWeekday={false} />
                    </div>
                  </div>
                </div>
              ))}
              {badWindow ? <Banner tone="error">{t("A prediction window ends before it starts.")}</Banner> : null}
              <Button type="button" variant="outline" size="md" className="self-start" onClick={() => setPredictions((ps) => [...ps, emptyPrediction()])}>
                {t("Add prediction")}
              </Button>
            </div>

            <ListEditor label="Remedies given" items={remedies} onChange={setRemedies} placeholder={t("For example Lamp at a peepal, Saturdays")} addLabel="Add remedy" />

            <div className="flex max-w-[260px] flex-col gap-1">
              <span className="text-[13px] font-bold leading-4 text-ink">{t("Follow up on")}</span>
              <DateField aria-label={t("Follow-up date")} value={followUp} onChange={setFollowUp} showWeekday={false} />
            </div>
          </div>
        )}

        <DialogFooter className="sticky -bottom-6 -mx-6 -mb-6 flex-wrap items-center justify-between border-t border-rule bg-surface px-6 pb-6 pt-3">
          <Button type="button" variant="outline" size="md" onClick={() => void draft()} disabled={busy !== "" || !loaded} loading={busy === "draft"} title={t("Optional. Uses the AI assistant and needs the client's AI consent.")}>
            {t("Draft summary")}
          </Button>
          <div className="flex gap-2">
            <Button type="button" variant="ghost" size="md" onClick={() => onOpenChange(false)}>
              {t("Cancel")}
            </Button>
            <Button type="button" size="md" onClick={() => void save()} disabled={!loaded || busy !== "" || badWindow} loading={busy === "save"}>
              {t("Save summary")}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ---------------------------------------------------------- notes section */
function SummaryDigest({ s }: { s: SummaryV1 }) {
  const t = useT();
  const f = useDateFmt();
  return (
    <div className="flex flex-col gap-2 rounded-[6px] bg-accent-wash px-3 py-[10px]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12px] font-bold uppercase leading-4 tracking-[0.06em] text-accent-text">{t("Summary")}</span>
        {s.topics.map((x) => (
          <span key={x} className="rounded-[4px] bg-surface px-2 py-[2px] text-[12px] font-bold leading-4 text-ink">
            {x}
          </span>
        ))}
      </div>
      {s.predictions.map((p) => (
        <div key={p.id} className="flex flex-wrap items-center gap-2 text-[13px] leading-5 text-ink">
          <StatusPill status={p.status} />
          <span>{p.statement}</span>
          {p.window_start || p.window_end ? <span className="text-body">{`(${t("{from} to {to}", { from: p.window_start ? f.short(p.window_start) : "...", to: p.window_end ? f.short(p.window_end) : "..." })})`}</span> : null}
        </div>
      ))}
      {s.remedies_given.length ? <div className="text-[13px] leading-5 text-body">{t("Remedies: {list}", { list: s.remedies_given.join(", ") })}</div> : null}
      {s.follow_up_date ? <div className="text-[13px] leading-5 text-body">{t("Follow up on {date}", { date: f.day(s.follow_up_date) })}</div> : null}
    </div>
  );
}

function ConsultCard({ c, chartId, onChanged }: { c: ConsultationFull; chartId: string | null; onChanged: () => void }) {
  const t = useT();
  const f = useDateFmt();
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");
  const [pinned, setPinned] = useState<NoteFact[]>([]);
  const [summary, setSummary] = useState<SummaryV1 | null>(null);
  const [dialog, setDialog] = useState(false);
  const [error, setError] = useState("");

  const loadSummary = useCallback(() => consultApi.getSummary(c.id).then(setSummary).catch(() => setSummary(null)), [c.id]);
  useEffect(() => void loadSummary(), [loadSummary]);

  async function addNote() {
    const { body, facts } = encodeNote(draft, pinned);
    if (!body) return;
    setError("");
    try {
      await consultApi.addNote(c.id, body, facts);
      setDraft("");
      setPinned([]);
      setAdding(false);
      onChanged();
    } catch (e) {
      setError(problemMessage(e));
    }
  }

  return (
    <Panel className="flex flex-col gap-3 p-4" data-consultation={c.id}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div className="text-[15px] font-bold leading-[18px] text-ink">{c.topic || t("Consultation")}</div>
        <div className="text-[12px] leading-4 text-soft">{f.day(c.scheduled_at ?? c.consulted_at)}</div>
      </div>
      {c.client_question ? (
        <p className="m-0 text-[14px] leading-5 text-ink">
          <span className="font-bold">{t("The client asks")}: </span>
          {c.client_question}
        </p>
      ) : null}
      <ErrorLine>{error}</ErrorLine>
      {c.notes.map((n: NoteFull) => (
        <NoteBody key={n.id} body={n.body} facts={n.facts} chartId={chartId} />
      ))}
      {summary ? <SummaryDigest s={summary} /> : null}
      {adding ? (
        <div className="flex flex-col gap-2">
          <NoteComposer clientId={c.client_id} value={draft} onChange={setDraft} pinned={pinned} onPinned={setPinned} label={t("Add a note")} placeholder={t("What was discussed")} />
          <div className="flex gap-2">
            <Button type="button" size="md" onClick={() => void addNote()} disabled={!draft.trim()}>
              {t("Save note")}
            </Button>
            <Button type="button" variant="ghost" size="md" onClick={() => setAdding(false)}>
              {t("Cancel")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-4">
          <button type="button" onClick={() => setAdding(true)} className="text-[13px] font-bold leading-4 text-accent-text hover:underline">
            {t("Add note")}
          </button>
          <button type="button" onClick={() => setDialog(true)} className="text-[13px] font-bold leading-4 text-accent-text hover:underline">
            {summary ? t("Edit summary") : t("Write summary")}
          </button>
        </div>
      )}
      <SummaryDialog consultation={c} open={dialog} onOpenChange={setDialog} onSaved={() => { void loadSummary(); onChanged(); }} />
    </Panel>
  );
}

export function ConsultationNotesSection({ clientId, chartId }: { clientId: string; chartId: string | null }) {
  const t = useT();
  const [items, setItems] = useState<ConsultationFull[] | null>(null);
  const [error, setError] = useState("");
  const [topic, setTopic] = useState("");
  const [question, setQuestion] = useState("");
  const [note, setNote] = useState("");
  const [pinned, setPinned] = useState<NoteFact[]>([]);
  const [bookDate, setBookDate] = useState("");
  const [bookTime, setBookTime] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [factChart, setFactChart] = useState<string | null>(chartId);

  useEffect(() => {
    consultApi.getChartFacts(clientId).then((r) => setFactChart(r.chart_id ?? chartId)).catch(() => undefined);
  }, [clientId, chartId]);

  const reload = useCallback(async () => {
    try {
      setItems(await consultApi.listConsultations(clientId));
    } catch (e) {
      setError(problemMessage(e));
      setItems([]);
    }
  }, [clientId]);
  useEffect(() => void reload(), [reload]);

  async function add() {
    setError("");
    try {
      let scheduled: string | undefined;
      if (bookDate) {
        const [y, m, d] = bookDate.split("-").map(Number) as [number, number, number];
        const [hh, mm] = (bookTime || "09:00").split(":").map(Number) as [number, number];
        scheduled = new Date(y, m - 1, d, hh, mm).toISOString();
      }
      const { body, facts } = encodeNote(note, pinned);
      await consultApi.createConsultation(clientId, {
        topic: topic.trim() || undefined,
        client_question: question.trim() || undefined,
        note: body || undefined,
        note_facts: body ? facts : undefined,
        chart_artifact_id: chartId ?? undefined,
        scheduled_at: scheduled,
        follow_up_date: followUp || undefined,
      });
      setTopic("");
      setQuestion("");
      setNote("");
      setPinned([]);
      setBookDate("");
      setBookTime("");
      setFollowUp("");
      await reload();
    } catch (e) {
      setError(problemMessage(e));
    }
  }

  return (
    <section className="flex flex-col gap-3" aria-label={t("Consultation notes")}>
      <Head title="Consultation notes" note={items ? t("{n} recorded", { n: items.length }) : ""} />
      <ErrorLine>{error}</ErrorLine>
      <Panel className="flex flex-col gap-3 p-4">
        <Input aria-label={t("Consultation topic")} value={topic} onChange={(e) => setTopic(e.target.value)} placeholder={t("Topic, for example Career question")} />
        <Input aria-label={t("The client's question")} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={t("What the client wants to ask")} />
        <NoteComposer clientId={clientId} value={note} onChange={setNote} pinned={pinned} onPinned={setPinned} label={t("First note")} placeholder={t("What was discussed")} />
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-[210px] grow basis-0 flex-col gap-1">
            <span className="text-[12px] font-bold leading-4 text-soft">{t("Book for")}</span>
            <div className="flex gap-2">
              <DateField aria-label={t("Booking date")} value={bookDate} onChange={setBookDate} showWeekday={false} className="min-w-0 grow" />
              <TimeField aria-label={t("Booking time")} value={bookTime} onChange={setBookTime} />
            </div>
          </div>
          <div className="flex min-w-[170px] grow basis-0 flex-col gap-1">
            <span className="text-[12px] font-bold leading-4 text-soft">{t("Follow up on")}</span>
            <DateField aria-label={t("Follow-up date")} value={followUp} onChange={setFollowUp} showWeekday={false} />
          </div>
        </div>
        <div className="flex justify-end">
          <Button type="button" size="md" onClick={() => void add()} disabled={!topic.trim() && !note.trim() && !question.trim() && !bookDate && !followUp}>
            {t("Add consultation")}
          </Button>
        </div>
      </Panel>
      {items?.map((c) => (
        <ConsultCard key={c.id} c={c} chartId={factChart} onChanged={() => void reload()} />
      ))}
    </section>
  );
}

/* ----------------------------------------------------- prediction tracking */
function PredictionRow({ p, onChanged }: { p: PredictionV1; onChanged: () => void }) {
  const t = useT();
  const f = useDateFmt();
  const [note, setNote] = useState(p.outcome_note ?? "");
  const [error, setError] = useState("");
  const ended = p.status === "pending" && p.window_end && p.window_end < new Date().toISOString().slice(0, 10);

  async function patch(body: { status?: PredictionStatus; outcome_note?: string | null }) {
    setError("");
    try {
      await consultApi.updatePrediction(p.id, body);
      onChanged();
    } catch (e) {
      setError(problemMessage(e));
    }
  }
  return (
    <div className="flex flex-col gap-2 border-b border-rule px-4 py-3 last:border-b-0">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div className="min-w-[200px] grow basis-0">
          <div className="text-[14px] font-bold leading-5 text-ink">{p.statement}</div>
          <div className="flex flex-wrap items-center gap-2 text-[12px] leading-4 text-body">
            <span>{p.window_start || p.window_end ? t("{from} to {to}", { from: p.window_start ? f.day(p.window_start) : "...", to: p.window_end ? f.day(p.window_end) : "..." }) : t("No window set")}</span>
            {ended ? <span className="rounded-[4px] bg-alert-wash px-2 py-[2px] font-bold text-alert">{t("Window ended")}</span> : null}
          </div>
        </div>
        <div className="w-[176px] shrink-0">
          <Select
            value={p.status}
            onValueChange={(v) => void patch({ status: v as PredictionStatus })}
            options={STATUS_OPTIONS.map((s) => ({ value: s.value, label: t(s.label) }))}
            aria-label={t("Outcome")}
          />
        </div>
      </div>
      <Input
        aria-label={t("Outcome note")}
        value={note}
        placeholder={t("What actually happened")}
        onChange={(e) => setNote(e.target.value)}
        onBlur={() => note !== (p.outcome_note ?? "") && void patch({ outcome_note: note })}
        className="h-[36px]"
      />
      <ErrorLine>{error}</ErrorLine>
    </div>
  );
}

export function PredictionsSection({ clientId }: { clientId: string }) {
  const t = useT();
  const [items, setItems] = useState<PredictionV1[] | null>(null);
  const [error, setError] = useState("");
  const reload = useCallback(() => consultApi.listPredictions(clientId).then(setItems).catch((e) => (setError(problemMessage(e)), setItems([]))), [clientId]);
  useEffect(() => void reload(), [reload]);
  useEffect(() => onConsultChanged(() => void reload()), [reload]);
  const resolved = items?.filter((p) => p.status !== "pending") ?? [];
  const hit = resolved.filter((p) => p.status === "came_true").length;
  if (items && items.length === 0 && !error) return null;
  return (
    <section className="flex flex-col gap-3" aria-label={t("Predictions")}>
      <Head title="Predictions" note={resolved.length ? t("{hit} of {n} came true", { hit, n: resolved.length }) : t("{n} pending", { n: items?.length ?? 0 })} />
      <ErrorLine>{error}</ErrorLine>
      <Panel className="flex flex-col">
        {items?.map((p) => (
          <PredictionRow key={`${p.id}-${p.status}`} p={p} onChanged={() => void reload()} />
        ))}
      </Panel>
    </section>
  );
}
