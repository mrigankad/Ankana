"use client";

import { isFixtures } from "@/lib/api/client";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  Children,
  cloneElement,
  isValidElement,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import type { VedicChartArtifact } from "@astro/astrology-core";
import {
  ArrowUp,
  Eraser,
  Maximize2,
  Minimize2,
  Sparkle,
  Square,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:3001";
}

function threadStorageKey(jobId: string) {
  return `nk-assistant-thread:${jobId}`;
}

export interface ChartAssistantSubject {
  name: string;
  birthDate: string;
  birthTime?: string;
  placeLabel?: string;
}

interface Citation {
  index: number;
  tool: string;
  fact: string;
  anchor?: string;
}

interface Exchange {
  question: string;
  answer: string;
  citations: Citation[];
  groundingWarning?: string;
}

const TOOL_FALLBACK_ANCHOR: Record<string, string> = {
  get_birth_chart: "planets",
  get_dashas: "dashas",
  get_yogas: "yogas",
  get_strengths: "strengths",
  get_transits: "transits",
  get_predictions: "predictions",
  get_remedies: "remedies",
  get_reading_summary: "reading",
  get_life_story: "your-life",
};

function citationAnchor(citation: Citation): string | undefined {
  return citation.anchor || TOOL_FALLBACK_ANCHOR[citation.tool];
}

function historyFromThread(thread: Exchange[]) {
  const turns: Array<{ role: "user" | "assistant"; content: string }> = [];
  for (const exchange of thread) {
    turns.push({ role: "user", content: exchange.question });
    turns.push({ role: "assistant", content: exchange.answer });
  }
  return turns.slice(-10);
}

function citeAwareChildren(
  children: ReactNode,
  byIndex: Map<number, Citation>,
  onCite: (citation: Citation) => void,
): ReactNode {
  return Children.map(children, (child, i) => {
    if (typeof child === "string") {
      const parts = child.split(/(\[\d+\])/g);
      if (parts.length === 1) return child;
      return parts.map((part, j) => {
        const match = /^\[(\d+)\]$/.exec(part);
        if (!match) return <span key={`${i}-${j}`}>{part}</span>;
        const index = Number(match[1]);
        const citation = byIndex.get(index);
        if (!citation) return <span key={`${i}-${j}`}>{part}</span>;
        return (
          <button
            key={`${i}-${j}`}
            type="button"
            className="nk-cite-chip"
            title={citation.fact}
            aria-label={`Show evidence for citation ${index}`}
            onClick={() => onCite(citation)}
          >
            [{index}]
          </button>
        );
      });
    }
    if (isValidElement<{ children?: React.ReactNode }>(child) && child.props.children) {
      return cloneElement(child, {
        ...child.props,
        children: citeAwareChildren(child.props.children, byIndex, onCite),
      });
    }
    return child;
  });
}

function AnswerText({
  answer,
  citations,
  onCite,
}: {
  answer: string;
  citations: Citation[];
  onCite: (citation: Citation) => void;
}) {
  const cleaned = answer
    .replace(/\u2014/g, "-")
    .replace(/\u2013/g, "-")
    .replace(/\u2212/g, "-");
  const byIndex = new Map(citations.map((c) => [c.index, c]));
  const wrap =
    (Tag: "p" | "li" | "strong" | "em") =>
    ({ children }: { children?: ReactNode }) => {
      const El = Tag;
      return <El>{citeAwareChildren(children, byIndex, onCite)}</El>;
    };

  return (
    <div className="nk-md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: wrap("p"),
          li: wrap("li"),
          strong: wrap("strong"),
          em: wrap("em"),
        }}
      >
        {cleaned}
      </ReactMarkdown>
    </div>
  );
}

export function ChartAssistant({
  jobId,
  artifact,
  subject,
  fullscreen = false,
  onFullscreenChange,
  onClose,
  onRevealEvidence,
}: {
  jobId: string;
  artifact: VedicChartArtifact;
  subject: ChartAssistantSubject;
  fullscreen?: boolean;
  onFullscreenChange?: (value: boolean) => void;
  onClose?: () => void;
  /** Switch chart tab + scroll/highlight the cited section. */
  onRevealEvidence?: (anchor: string) => void;
}) {
  const [question, setQuestion] = useState("");
  const [thread, setThread] = useState<Exchange[]>([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [health, setHealth] = useState<{
    status: "ok" | "degraded" | "offline";
    mode: "mock" | "live";
    model: string;
  } | null>(null);
  const threadEndRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadHealth() {
      if (isFixtures()) {
        setHealth({ status: "offline", mode: "mock", model: "sample" });
        return;
      }
      try {
        const response = await fetch(`${getApiBaseUrl()}/api/v1/assistant/health`);
        if (!response.ok) return;
        const payload = (await response.json()) as {
          status?: "ok" | "degraded" | "offline";
          mode?: "mock" | "live";
          model?: string;
        };
        if (!cancelled && payload.status) {
          setHealth({
            status: payload.status,
            mode: payload.mode ?? "live",
            model: payload.model ?? "unknown",
          });
        }
      } catch {
        if (!cancelled) {
          setHealth({ status: "offline", mode: "live", model: "unknown" });
        }
      }
    }
    void loadHealth();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setReady(false);
    setQuestion("");
    setError("");

    async function hydrate() {
      // Instant cache while server thread loads.
      try {
        const raw = window.localStorage.getItem(threadStorageKey(jobId));
        if (raw && !cancelled) {
          const parsed = JSON.parse(raw) as Exchange[];
          if (Array.isArray(parsed)) setThread(parsed);
        } else if (!cancelled) {
          setThread([]);
        }
      } catch {
        if (!cancelled) setThread([]);
      }

      if (isFixtures()) {
        if (!cancelled) setReady(true);
        return;
      }
      try {
        const response = await fetch(
          `${getApiBaseUrl()}/api/v1/charts/jobs/${jobId}/assistant/thread`,
        );
        if (!response.ok) {
          if (!cancelled) setReady(true);
          return;
        }
        const payload = (await response.json()) as { exchanges?: Exchange[] };
        if (!cancelled) {
          setThread(Array.isArray(payload.exchanges) ? payload.exchanges : []);
          setReady(true);
        }
      } catch {
        if (!cancelled) setReady(true);
      }
    }

    void hydrate();
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  useEffect(() => {
    if (!ready) return;
    try {
      window.localStorage.setItem(
        threadStorageKey(jobId),
        JSON.stringify(thread),
      );
    } catch {
      // ignore quota / private mode
    }
  }, [jobId, thread, ready]);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [thread, busy]);

  useEffect(() => {
    if (!fullscreen) return;
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        onFullscreenChange?.(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen, onFullscreenChange]);

  const currentMahadasha = artifact.vimshottari.mahadashas.find((m) => {
    const now = Date.now();
    return new Date(m.start).getTime() <= now && now < new Date(m.end).getTime();
  });
  const topYoga = artifact.yogas.find((y) => y.present);

  const suggestions = useMemo(
    () => [
      currentMahadasha
        ? `Explain my current ${currentMahadasha.planet} mahadasha`
        : "Explain my current dasha period",
      `What does my ${artifact.ascendant.signName} lagna say about me?`,
      ...(topYoga ? [`${topYoga.name} - what does it mean for me?`] : []),
      "Walk me through my life stages from the chart",
      "Summarize my deep reading highlights",
      "What should I watch during the next year?",
    ],
    [artifact.ascendant.signName, currentMahadasha, topYoga],
  );

  const revealCitation = useCallback(
    (citation: Citation) => {
      const anchor = citationAnchor(citation);
      if (anchor) onRevealEvidence?.(anchor);
    },
    [onRevealEvidence],
  );

  const birthLine = useMemo(() => {
    const parts = [subject.birthDate];
    if (subject.birthTime) parts.push(subject.birthTime);
    if (subject.placeLabel) parts.push(subject.placeLabel);
    return parts.join(" · ");
  }, [subject.birthDate, subject.birthTime, subject.placeLabel]);

  const ask = useCallback(
    async (text: string) => {
      if (busy || text.trim().length < 3) return;
      setBusy(true);
      setError("");
      setStatus("Consulting the chart…");
      const abort = new AbortController();
      abortRef.current = abort;
      try {
        const response = await fetch(
          `${getApiBaseUrl()}/api/v1/charts/jobs/${jobId}/assistant?stream=1`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "text/event-stream",
            },
            body: JSON.stringify({
              question: text,
              history: historyFromThread(thread),
            }),
            signal: abort.signal,
          },
        );

        if (!response.ok || !response.body) {
          const payload = (await response.json().catch(() => ({}))) as {
            error?: { message?: string };
          };
          throw new Error(
            payload.error?.message ??
              "Assistant is offline - chart data is unaffected.",
          );
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finalAnswer: {
          answer: string;
          citations: Citation[];
          groundingWarning?: string;
        } | null = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split("\n\n");
          buffer = chunks.pop() ?? "";
          for (const chunk of chunks) {
            const lines = chunk.split("\n");
            let event = "message";
            let data = "";
            for (const line of lines) {
              if (line.startsWith("event:")) event = line.slice(6).trim();
              if (line.startsWith("data:")) data += line.slice(5).trim();
            }
            if (!data) continue;
            const payload = JSON.parse(data) as {
              message?: string;
              answer?: string;
              citations?: Citation[];
              groundingWarning?: string;
              code?: string;
            };
            if (event === "status" && payload.message) {
              setStatus(payload.message);
            }
            if (event === "done" && payload.answer) {
              finalAnswer = {
                answer: payload.answer,
                citations: payload.citations ?? [],
                groundingWarning: payload.groundingWarning,
              };
            }
            if (event === "error") {
              throw new Error(
                payload.message ?? "Assistant is offline - chart data is unaffected.",
              );
            }
          }
        }

        if (!finalAnswer) {
          throw new Error("Assistant returned no answer.");
        }
        setThread((prev) => [
          ...prev,
          {
            question: text,
            answer: finalAnswer!.answer,
            citations: finalAnswer!.citations,
            groundingWarning: finalAnswer!.groundingWarning,
          },
        ]);
        setQuestion("");
      } catch (cause) {
        if (cause instanceof Error && cause.name === "AbortError") {
          setError("");
          setStatus("");
        } else {
          setError(
            cause instanceof Error ? cause.message : "Assistant request failed.",
          );
        }
      } finally {
        abortRef.current = null;
        setBusy(false);
        setStatus("");
      }
    },
    [busy, jobId, thread],
  );

  function stopAsk() {
    abortRef.current?.abort();
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void ask(question);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void ask(question);
    }
  }

  async function clearThread() {
    setError("");
    try {
      await fetch(
        `${getApiBaseUrl()}/api/v1/charts/jobs/${jobId}/assistant/thread`,
        { method: "DELETE" },
      );
    } catch {
      // Still clear local UI if the network fails.
    }
    setThread([]);
    try {
      window.localStorage.removeItem(threadStorageKey(jobId));
    } catch {
      // ignore
    }
  }

  const canSend = !busy && question.trim().length >= 3;

  return (
    <section
      className="nk-assistant"
      aria-label="Chart assistant"
      id="assistant"
      role="complementary"
      data-fullscreen={fullscreen ? "true" : "false"}
    >
      <header className="nk-assistant-top">
        <div className="nk-assistant-brand">
          <span className="nk-assistant-mark" aria-hidden>
            <Sparkle size={15} strokeWidth={2.25} />
          </span>
          <div className="nk-assistant-titles">
            <p className="nk-assistant-kicker">Assistant · this chart only</p>
            <h2 className="nk-assistant-title" title={subject.name}>
              {subject.name}
            </h2>
            <p className="nk-assistant-sub" title={birthLine}>
              {birthLine}
            </p>
          </div>
        </div>
        <div className="nk-assistant-top-actions">
          {thread.length > 0 ? (
            <button
              type="button"
              className="nk-assistant-icon-btn"
              onClick={clearThread}
              disabled={busy}
              aria-label="Clear conversation for this chart"
              title="Clear conversation"
            >
              <Eraser size={15} aria-hidden />
            </button>
          ) : null}
          {onFullscreenChange ? (
            <button
              type="button"
              className="nk-assistant-icon-btn"
              onClick={() => onFullscreenChange(!fullscreen)}
              aria-label={fullscreen ? "Exit full screen" : "Full screen"}
              aria-pressed={fullscreen}
              title={fullscreen ? "Exit full screen" : "Full screen"}
            >
              {fullscreen ? (
                <Minimize2 size={15} aria-hidden />
              ) : (
                <Maximize2 size={15} aria-hidden />
              )}
            </button>
          ) : null}
          {onClose ? (
            <button
              type="button"
              className="nk-assistant-icon-btn"
              onClick={onClose}
              aria-label="Close assistant"
              title="Close"
            >
              <X size={15} aria-hidden />
            </button>
          ) : null}
        </div>
      </header>

      <div className="nk-assistant-meta-row">
        <span className="nk-assistant-pill">{artifact.ascendant.signName} lagna</span>
        {currentMahadasha ? (
          <span className="nk-assistant-pill nk-assistant-pill-soft">
            {currentMahadasha.planet} mahadasha
          </span>
        ) : null}
        <span className="nk-assistant-pill nk-assistant-pill-soft">
          {artifact.ascendant.nakshatra}
        </span>
        {health ? (
          <span
            className={`nk-assistant-health nk-assistant-health-${health.status}`}
            title={
              health.mode === "mock"
                ? "Mock assistant (CI / offline mode)"
                : `Model ${health.model}`
            }
          >
            {health.status === "ok"
              ? health.mode === "mock"
                ? "Mock ready"
                : "Model ready"
              : health.status === "degraded"
                ? "Model degraded"
                : "Model offline"}
          </span>
        ) : null}
      </div>

      {health && health.status !== "ok" ? (
        <p className="nk-assistant-health-banner" role="status">
          The assistant model looks {health.status}. Chart data stays available -
          retry in a moment or continue reading the chart.
        </p>
      ) : null}
      <div className="nk-assistant-thread nk-scroll" aria-live="polite">
        {thread.length === 0 && !busy ? (
          <div className="nk-assistant-empty">
            <p className="nk-assistant-empty-kicker">Start here</p>
            <h3 className="nk-assistant-empty-title">
              Ask about {subject.name.split(" ")[0]}&apos;s chart
            </h3>
            <p className="nk-assistant-empty-copy">
              Answers cite placements, dashas, and strengths from this job -
              nothing invented.
            </p>
            <ul className="nk-assistant-prompt-list">
              {suggestions.map((text) => (
                <li key={text}>
                  <button
                    type="button"
                    className="nk-assistant-prompt"
                    disabled={busy}
                    onClick={() => void ask(text)}
                  >
                    <span>{text}</span>
                    <span className="nk-assistant-prompt-go" aria-hidden>
                      →
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {thread.map((exchange, i) => (
          <article
            key={`${i}-${exchange.question.slice(0, 24)}`}
            className="nk-exchange"
          >
            <div className="nk-bubble nk-bubble-user">
              <p>{exchange.question}</p>
            </div>
            <div className="nk-bubble nk-bubble-assistant">
              <div className="nk-bubble-assistant-head">
                <span className="nk-assistant-avatar" aria-hidden>
                  <Sparkle size={12} strokeWidth={2.4} />
                </span>
                <span>Nakshatra</span>
              </div>
              <AnswerText
                answer={exchange.answer}
                citations={exchange.citations}
                onCite={revealCitation}
              />
              {exchange.groundingWarning ? (
                <p className="nk-assistant-grounding" role="status">
                  {exchange.groundingWarning}
                </p>
              ) : null}
              {exchange.citations.length > 0 ? (
                <details className="nk-assistant-citations">
                  <summary>
                    {exchange.citations.length} chart fact
                    {exchange.citations.length === 1 ? "" : "s"}
                  </summary>
                  <ol>
                    {exchange.citations.map((citation) => (
                      <li key={citation.index}>
                        <button
                          type="button"
                          className="nk-citation-jump"
                          onClick={() => revealCitation(citation)}
                        >
                          <span className="nk-citation">[{citation.index}]</span>
                          <span className="nk-citation-tool">
                            {citation.tool}
                          </span>
                          <span className="nk-citation-fact">
                            {citation.fact}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ol>
                </details>
              ) : null}
            </div>
          </article>
        ))}

        {busy ? (
          <div className="nk-assistant-busy" role="status">
            <span className="nk-assistant-busy-dot" aria-hidden />
            {status || `Consulting ${subject.name.split(" ")[0]}'s chart…`}
          </div>
        ) : null}
        {error ? (
          <p className="nk-alert nk-assistant-error" role="alert">
            {error}
          </p>
        ) : null}
        <div ref={threadEndRef} />
      </div>

      <footer className="nk-assistant-footer">
        <form onSubmit={handleSubmit} className="nk-assistant-composer">
          <textarea
            aria-label={`Ask about ${subject.name}'s chart`}
            placeholder={`Ask about ${subject.name}…`}
            value={question}
            disabled={busy}
            rows={1}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleKeyDown}
          />
          {busy ? (
            <button
              type="button"
              className="nk-assistant-send nk-assistant-stop"
              onClick={stopAsk}
              aria-label="Stop"
            >
              <Square size={14} strokeWidth={2.5} aria-hidden />
            </button>
          ) : (
            <button
              type="submit"
              className="nk-assistant-send"
              disabled={!canSend}
              aria-label="Send question"
            >
              <ArrowUp size={18} strokeWidth={2.4} aria-hidden />
            </button>
          )}
        </form>
        <p className="nk-assistant-disclaimer">
          Advisory only · not medical, legal, or financial advice
        </p>
      </footer>
    </section>
  );
}
