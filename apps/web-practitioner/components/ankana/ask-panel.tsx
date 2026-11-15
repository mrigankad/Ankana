"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { CONSENT_NOTICE_VERSION } from "@/lib/api/intake-flow";
import { askChart, v1Api, type AskResult } from "@/lib/api/live";
import { ProblemError, problemMessage } from "@/lib/api/v1";
import type { AskThread } from "@/lib/api/types";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

function Segmented({ items, active, onChange, className }: { items: string[]; active: string; onChange?: (v: string) => void; className?: string }) {
  const t = useT();
  return (
    <div className={cn("flex gap-[2px] rounded-[6px] bg-sidebar-wash p-[3px]", className)}>
      {items.map((it) => (
        <button
          key={it}
          type="button"
          onClick={() => onChange?.(it)}
          className={cn("rounded-[5px] px-[10px] py-1 text-[12px] leading-[14px]", it === active ? "bg-white font-bold text-ink" : "text-body")}
        >
          {t(it)}
        </button>
      ))}
    </div>
  );
}
export { Segmented };

interface Turn {
  id: number;
  question: string;
  status: string;
  result: AskResult | null;
  error: string;
  needsConsent?: boolean;
}

const SUGGESTIONS = ["What supports career now?", "Which remedy fits Mars?", "When does this dasha end?"];

/** Answer text with [n] markers rendered as accent citation numbers. */
function Answer({ text }: { text: string }): ReactNode {
  return (
    <p className="m-0 text-[14px] leading-[21px] text-ink">
      {text.split(/(\[\d+\])/g).map((part, i) =>
        /^\[\d+\]$/.test(part) ? (
          <span key={i} className="font-bold text-accent-text">
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </p>
  );
}

function Fixture({ thread }: { thread: AskThread }) {
  return (
    <>
      <div className="flex justify-end">
        <div className="max-w-[260px] rounded-[10px] bg-sidebar-wash px-[14px] py-[10px] text-[14px] leading-5 text-ink">{thread.question}</div>
      </div>
      <div className="flex flex-col gap-[6px]">
        <div className="flex items-center gap-2 rounded-[6px] bg-wash px-3 py-2">
          <span className="size-[6px] shrink-0 rounded-full bg-sindoor" />
          <span className="text-[13px] font-bold leading-4 text-accent-text">{thread.checks.engine}</span>
        </div>
        <div className="flex items-center gap-2 rounded-[6px] bg-wash px-3 py-2">
          <span className="size-[6px] shrink-0 rounded-full bg-ok" />
          <span className="text-[13px] font-bold leading-4 text-accent-text">{thread.checks.verifier}</span>
        </div>
      </div>
      <div className="flex flex-col gap-[10px]">
        <p className="m-0 text-[14px] leading-[21px] text-ink">
          {thread.answer.map((seg, i) => (
            <span key={i}>
              {seg.text}
              {seg.cite ? <span className="font-bold text-accent-text">[{seg.cite}]</span> : null}
            </span>
          ))}
        </p>
        <div className="flex flex-col gap-[6px]">
          {thread.citations.map((c) => (
            <div key={c.n} className="flex items-center gap-2 rounded-[6px] border border-rule px-[10px] py-[7px]">
              <span className="text-[12px] font-bold leading-4 text-accent-text">{c.n}</span>
              <span className="text-[12px] leading-4 text-body">
                {c.source} · {c.detail}
              </span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

/**
 * Persistent Ask panel (Paper U05 to U07). Live: streams /v1/charts/{id}/ask over SSE with citations that
 * jump to their evidence. Fixtures: shows the design thread.
 */
export function AskPanel({
  thread,
  chartId,
  clientId,
  live = false,
  onOpenAssistant,
  onRevealEvidence,
  className,
}: {
  thread: AskThread;
  chartId?: string;
  clientId?: string;
  live?: boolean;
  onOpenAssistant?: () => void;
  onRevealEvidence?: (anchor: string) => void;
  className?: string;
}) {
  const [tab, setTab] = useState<"Ask" | "Notes">("Ask");
  const [scope, setScope] = useState("This chart");
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");
  const [noteState, setNoteState] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight });
  }, [turns]);
  useEffect(() => () => abort.current?.abort(), []);

  async function send(question: string, retry?: number) {
    if (!chartId || !question.trim() || busy) return;
    const id = retry ?? Date.now();
    setBusy(true);
    setDraft("");
    setTurns((t) => (retry ? t.map((x) => (x.id === id ? { ...x, status: "Starting", error: "", needsConsent: false } : x)) : [...t, { id, question, status: "Starting", result: null, error: "" }]));
    const history = turns
      .filter((t) => t.result && t.id !== id)
      .flatMap((t) => [
        { role: "user" as const, content: t.question },
        { role: "assistant" as const, content: t.result!.answer },
      ]);
    abort.current = new AbortController();
    try {
      const result = await askChart(
        chartId,
        { question, history, deep: false },
        { onStatus: (m) => setTurns((t) => t.map((x) => (x.id === id ? { ...x, status: m } : x))) },
        abort.current.signal,
      );
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, status: "", result } : x)));
    } catch (cause) {
      const needsConsent = cause instanceof ProblemError && cause.code === "consent_required";
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, status: "", error: problemMessage(cause), needsConsent } : x)));
    } finally {
      setBusy(false);
    }
  }

  async function grantAndRetry(turn: Turn) {
    if (!clientId) return;
    try {
      await v1Api.recordConsent(clientId, { purpose: "ai_assistant", notice_version: CONSENT_NOTICE_VERSION, channel: "in_person" });
      await send(turn.question, turn.id);
    } catch (cause) {
      setTurns((t) => t.map((x) => (x.id === turn.id ? { ...x, error: problemMessage(cause) } : x)));
    }
  }

  async function saveNote() {
    if (!clientId || !note.trim()) return;
    setNoteState("Saving");
    try {
      await v1Api.createConsultation(clientId, { topic: "Chart note", note: note.trim(), chart_artifact_id: chartId, mode: "in_person" });
      setNote("");
      setNoteState("Saved to the client's consultation notes.");
    } catch (cause) {
      setNoteState(problemMessage(cause));
    }
  }

  return (
    <div className={cn("flex min-h-0 min-w-0 flex-col overflow-hidden bg-white", className)}>
      <div className="flex h-12 shrink-0 items-end gap-5 border-b border-rule px-5" role="tablist" aria-label="Ask panel">
        {(["Ask", "Notes"] as const).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={cn("text-[14px] leading-[18px]", tab === t ? "border-b-2 border-sindoor pb-[14px] font-bold text-ink" : "pb-[15px] text-body")}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Ask" ? (
        <>
          <div ref={scroller} className="flex min-h-0 grow basis-0 flex-col gap-[14px] overflow-y-auto px-5 py-[18px]" aria-live="polite">
            {!live ? <Fixture thread={thread} /> : null}
            {live && !turns.length ? (
              <p className="m-0 text-[14px] leading-5 text-body">Ask anything about this chart. Every claim in an answer is checked against the engine and cited.</p>
            ) : null}
            {turns.map((t) => (
              <div key={t.id} className="flex min-w-0 flex-col gap-[10px]">
                <div className="flex justify-end">
                  <div className="max-w-[260px] rounded-[10px] bg-sidebar-wash px-[14px] py-[10px] text-[14px] leading-5 text-ink">{t.question}</div>
                </div>
                {t.status ? (
                  <div className="flex items-center gap-2 rounded-[6px] bg-wash px-3 py-2">
                    <span className="size-[6px] shrink-0 animate-pulse rounded-full bg-sindoor" />
                    <span className="text-[13px] font-bold leading-4 text-accent-text">{t.status}</span>
                  </div>
                ) : null}
                {t.result ? (
                  <>
                    <div className="flex flex-col gap-[6px]">
                      <div className="flex items-center gap-2 rounded-[6px] bg-wash px-3 py-2">
                        <span className="size-[6px] shrink-0 rounded-full bg-sindoor" />
                        <span className="text-[13px] font-bold leading-4 text-accent-text">Engine · checked {t.result.verification?.claimsChecked ?? t.result.toolsUsed.length} facts</span>
                      </div>
                      <div className="flex items-center gap-2 rounded-[6px] bg-wash px-3 py-2">
                        <span className={cn("size-[6px] shrink-0 rounded-full", (t.result.verification?.claimsFailed ?? 0) === 0 ? "bg-ok" : "bg-alert")} />
                        <span className="text-[13px] font-bold leading-4 text-accent-text">
                          {(t.result.verification?.claimsFailed ?? 0) === 0 ? "Verifier · all claims match" : `Verifier · ${t.result.verification?.claimsFailed} claims removed`}
                        </span>
                      </div>
                    </div>
                    <Answer text={t.result.answer} />
                    <div className="flex flex-col gap-[6px]">
                      {t.result.citations.map((c) => (
                        <button
                          key={c.index}
                          type="button"
                          onClick={() => c.anchor && onRevealEvidence?.(c.anchor)}
                          className="flex min-w-0 items-start gap-2 rounded-[6px] border border-rule px-[10px] py-[7px] text-left"
                        >
                          <span className="text-[12px] font-bold leading-4 text-accent-text">{c.index}</span>
                          <span className="min-w-0 break-words text-[12px] leading-4 text-body">{c.fact.length > 140 ? `${c.fact.slice(0, 140)}…` : c.fact}</span>
                        </button>
                      ))}
                    </div>
                  </>
                ) : null}
                {t.error ? (
                  <div role="alert" className="flex flex-col gap-2 rounded-[6px] bg-alert-wash px-3 py-2 text-[13px] font-bold leading-[18px] text-alert">
                    {t.error}
                    {t.needsConsent && clientId ? (
                      <button type="button" onClick={() => void grantAndRetry(t)} className="self-start rounded-[5px] bg-ink px-3 py-[6px] text-[12px] font-bold text-white">
                        Record consent and ask again
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          <div className="flex shrink-0 flex-col gap-[10px] border-t border-rule px-5 pb-[18px] pt-3">
            <div className="flex flex-wrap gap-[6px]">
              {(live ? SUGGESTIONS : thread.suggestions).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => (live ? void send(s) : onOpenAssistant?.())}
                  className="rounded-full border border-rule px-[11px] py-[6px] text-[12px] font-bold leading-[14px] text-body"
                >
                  {s}
                </button>
              ))}
            </div>
            <form
              className="flex flex-col gap-[10px] rounded-[10px] border border-rule px-[14px] py-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (live) void send(draft);
                else {
                  setDraft("");
                  onOpenAssistant?.();
                }
              }}
            >
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Ask about this chart"
                aria-label="Ask about this chart"
                className="w-full bg-transparent text-[14px] leading-[18px] text-ink outline-none placeholder:text-soft"
              />
              <div className="flex items-center justify-between">
                <Segmented items={["This chart", "Lal Kitab"]} active={scope} onChange={setScope} />
                <button type="submit" aria-label="Send question" disabled={busy} className="flex size-[30px] shrink-0 items-center justify-center rounded-[6px] bg-ink disabled:opacity-50">
                  <svg width="14" height="14" viewBox="0 0 14 14" className="shrink-0" aria-hidden>
                    <path d="M7 12V2M3 6l4-4 4 4" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </div>
            </form>
            {!live && onOpenAssistant ? (
              <button type="button" onClick={onOpenAssistant} className="self-start text-[12px] font-bold leading-4 text-accent-text">
                Open full assistant
              </button>
            ) : null}
          </div>
        </>
      ) : (
        <div className="flex min-h-0 grow basis-0 flex-col gap-3 px-5 py-[18px]">
          <label htmlFor="chart-note" className="text-[12px] font-bold leading-4 tracking-[0.06em] text-soft">
            CONSULT NOTE
          </label>
          <textarea
            id="chart-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Private notes for this client"
            className="min-h-[160px] w-full resize-none rounded-[10px] border border-rule p-[14px] text-[14px] leading-5 text-ink outline-none placeholder:text-soft"
          />
          {live ? (
            <div className="flex items-center justify-between gap-3">
              <span className="text-[12px] leading-4 text-soft">{noteState}</span>
              <button type="button" onClick={() => void saveNote()} disabled={!note.trim()} className="rounded-[6px] bg-ink px-[14px] py-2 text-[13px] font-bold text-white disabled:opacity-50">
                Save note
              </button>
            </div>
          ) : (
            <p className="m-0 text-[12px] leading-4 text-soft">Notes stay on this device in the demo.</p>
          )}
        </div>
      )}
    </div>
  );
}
