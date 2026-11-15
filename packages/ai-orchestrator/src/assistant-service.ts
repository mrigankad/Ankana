import type { VedicChartArtifact } from "@astro/astrology-core";

import {
  applyGroundingCaution,
  assessGrounding,
} from "./grounding";
import type { ChartReadingContext } from "./reading-context";
import {
  TOOL_DEFINITIONS,
  executeTool,
  parseToolArgs,
} from "./tools";

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  tool_calls?: Array<{ function: { name: string; arguments: unknown } }>;
}

export interface OllamaClient {
  chat(messages: ChatMessage[], tools: typeof TOOL_DEFINITIONS): Promise<ChatMessage>;
}

export interface Citation {
  index: number;
  tool: string;
  fact: string;
  /** Chart section / row id for UI jump-to-evidence. */
  anchor?: string;
}

export interface AssistantAnswer {
  answer: string;
  citations: Citation[];
  toolsUsed: string[];
  groundingWarning?: string;
}

export const SYSTEM_PROMPT = `You are Nakshatra, a senior Jyotish practitioner assistant. You are warm, precise, and never fatalistic.

STRICT RULES:
1. Every astrological claim MUST come from a tool result and carry a bracket citation formatted EXACTLY like [1] (plain square brackets, tool-call order). Never invent chart facts. House lordships must come from the houses data in get_birth_chart, never from memory. For life chapters or deep narrative, use get_life_story or get_reading_summary. Use search_classical only for interpretive language (house/graha/yoga themes); never treat classical snippets as this chart's placements, degrees, or dasha dates.
2. If the tools do not contain the answer, say so plainly.
3. Refuse: birth-time rectification claims, predictions of death or serious disease, litigation outcomes, and medical, legal, or financial instructions. Frame health, money, and career strictly as wellness and timing guidance.
4. Only discuss the person whose chart is loaded. Prior chat turns (if any) are about THIS chart only - use them for continuity, never as a source of planetary facts.
5. Keep answers under 220 words, in plain language a client can follow. Format as short markdown: a bold one-line summary, then 3-6 bullet points. Never use markdown tables or horizontal rules; never use <br> or raw HTML. Never use em dashes (—) or en dashes (–); use a plain hyphen (-) only.
6. End every answer with: "Advisory guidance only - not medical, legal, or financial advice."`;

export interface AssistantHistoryTurn {
  role: "user" | "assistant";
  content: string;
}

const MAX_HISTORY_MESSAGES = 10;

/**
 * Keep the last N turns; when older turns exist, prepend a short continuity
 * summary so early questions are not silently dropped.
 */
export function windowHistory(
  history: AssistantHistoryTurn[] | undefined,
): ChatMessage[] {
  if (!history?.length) return [];
  const cleaned: ChatMessage[] = [];
  for (const turn of history) {
    if (turn.role !== "user" && turn.role !== "assistant") continue;
    const content = turn.content?.trim();
    if (!content) continue;
    cleaned.push({ role: turn.role, content: content.slice(0, 4000) });
  }
  if (cleaned.length <= MAX_HISTORY_MESSAGES) return cleaned;

  const summaryBudget = 2;
  const kept = cleaned.slice(-(MAX_HISTORY_MESSAGES - summaryBudget));
  const dropped = cleaned.slice(0, -kept.length);
  const topics = dropped
    .filter((m) => m.role === "user")
    .map((m) => m.content.replace(/\s+/g, " ").slice(0, 48))
    .filter(Boolean)
    .slice(0, 4);
  const summary = `Earlier discussion on THIS chart only (${Math.ceil(dropped.length / 2)} exchanges). Topics touched: ${topics.join(" · ") || "prior questions"}. Use for continuity, never as planetary facts.`;
  return [
    { role: "user", content: summary },
    {
      role: "assistant",
      content:
        "Understood - I will keep continuity from earlier turns on this chart and still ground every placement in tools.",
    },
    ...kept,
  ];
}

function sanitizeHistory(
  history: AssistantHistoryTurn[] | undefined,
): ChatMessage[] {
  return windowHistory(history);
}

/**
 * Real Ollama client. Works against Ollama Pro cloud
 * (OLLAMA_BASE_URL=https://ollama.com with OLLAMA_API_KEY) or a local
 * daemon (http://127.0.0.1:11434, no key).
 */
export class HttpOllamaClient implements OllamaClient {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string | undefined,
    private readonly model: string,
    private readonly fetchImpl: typeof fetch = fetch,
  ) {}

  async chat(
    messages: ChatMessage[],
    tools: typeof TOOL_DEFINITIONS,
  ): Promise<ChatMessage> {
    const response = await this.fetchImpl(`${this.baseUrl}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
      },
      body: JSON.stringify({
        model: this.model,
        messages,
        tools,
        stream: false,
      }),
      signal: AbortSignal.timeout(60_000),
    });

    if (!response.ok) {
      throw new Error(`Ollama request failed with status ${response.status}`);
    }

    const payload = (await response.json()) as { message: ChatMessage };
    return payload.message;
  }
}

/** Deterministic mock for CI and keyless development (OLLAMA_MOCK=1). */
export class MockOllamaClient implements OllamaClient {
  private turn = 0;

  async chat(messages: ChatMessage[]): Promise<ChatMessage> {
    this.turn += 1;
    if (this.turn === 1) {
      return {
        role: "assistant",
        content: "",
        tool_calls: [
          { function: { name: "get_birth_chart", arguments: {} } },
          { function: { name: "get_dashas", arguments: {} } },
        ],
      };
    }
    const question =
      [...messages].reverse().find((m) => m.role === "user")?.content ?? "";
    return {
      role: "assistant",
      content: `Regarding "${question}": your lagna and placements are set out in the chart [1], and the current dasha period frames the timing [2]. Advisory guidance only - not medical, legal, or financial advice.`,
    };
  }
}

/** Rewrites model citation variants and strips em/en dashes to plain hyphens. */
export function normalizeCitations(text: string): string {
  return text
    .replace(/【(\d+)[^】]*】/g, "[$1]")
    .replace(/\[(\d+)\s*,\s*(\d+)\]/g, "[$1][$2]")
    .replace(/\u2014/g, "-") // em dash —
    .replace(/\u2013/g, "-") // en dash –
    .replace(/\u2212/g, "-"); // minus −
}

const MAX_TOOL_ROUNDS = 6;

const TOOL_STATUS_LABELS: Record<string, string> = {
  get_birth_chart: "Consulting birth chart…",
  get_dashas: "Consulting dasha timeline…",
  get_yogas: "Reviewing yogas…",
  get_strengths: "Checking planetary strengths…",
  get_transits: "Reading current transits…",
  get_predictions: "Scanning prediction windows…",
  get_remedies: "Looking up remedies…",
  get_reading_summary: "Opening deep reading…",
  get_life_story: "Opening Your Life chapters…",
  lk_chart: "Reading Lal Kitab chart…",
  lk_sleeping: "Checking dormant planets…",
  lk_rin: "Checking Lal Kitab debts…",
  lk_masnui: "Checking artificial planets…",
  lk_varshphal: "Casting the annual chart…",
  lk_upay: "Ranking Lal Kitab upay…",
  search_classical: "Searching classical notes…",
};

export function toolStatusLabel(toolName: string): string {
  return TOOL_STATUS_LABELS[toolName] ?? `Consulting ${toolName}…`;
}

export interface AskAssistantOptions {
  history?: AssistantHistoryTurn[];
  /** Deterministic reading + lifeStory for richer tools (fail-soft if missing). */
  reading?: ChartReadingContext | null;
  onStatus?: (message: string) => void;
  signal?: AbortSignal;
}

export async function askAssistant(
  client: OllamaClient,
  artifact: VedicChartArtifact,
  question: string,
  now: Date = new Date(),
  historyOrOptions?: AssistantHistoryTurn[] | AskAssistantOptions,
): Promise<AssistantAnswer> {
  const options: AskAssistantOptions = Array.isArray(historyOrOptions)
    ? { history: historyOrOptions }
    : (historyOrOptions ?? {});

  const messages: ChatMessage[] = [
    { role: "system", content: SYSTEM_PROMPT },
    ...sanitizeHistory(options.history),
    { role: "user", content: question },
  ];

  const citations: Citation[] = [];
  const toolsUsed: string[] = [];

  for (let round = 0; round < MAX_TOOL_ROUNDS; round += 1) {
    if (options.signal?.aborted) {
      const error = new Error("Assistant request aborted");
      error.name = "AbortError";
      throw error;
    }
    const reply = await client.chat(messages, TOOL_DEFINITIONS);

    if (!reply.tool_calls || reply.tool_calls.length === 0) {
      const normalized = normalizeCitations(reply.content);
      const grounding = assessGrounding(normalized, artifact);
      return {
        answer: applyGroundingCaution(normalized, grounding),
        citations,
        toolsUsed,
        groundingWarning: grounding.warning,
      };
    }

    messages.push(reply);
    for (const call of reply.tool_calls) {
      if (options.signal?.aborted) {
        const error = new Error("Assistant request aborted");
        error.name = "AbortError";
        throw error;
      }
      const name = call.function.name;
      options.onStatus?.(toolStatusLabel(name));
      const result = executeTool(name, artifact, now, {
        reading: options.reading,
        args: parseToolArgs(call.function.arguments),
      });
      toolsUsed.push(name);
      citations.push({
        index: citations.length + 1,
        tool: name,
        fact: result.summary,
        anchor: result.anchor,
      });
      messages.push({
        role: "tool",
        content: JSON.stringify({
          citationIndex: citations.length,
          summary: result.summary,
          data: result.data,
        }),
      });
    }
  }

  return {
    answer:
      "I could not ground an answer in the chart data within the allowed steps. Please rephrase the question. Advisory guidance only - not medical, legal, or financial advice.",
    citations,
    toolsUsed,
  };
}

export function createOllamaClient(): OllamaClient {
  if (process.env.OLLAMA_MOCK === "1") {
    return new MockOllamaClient();
  }
  return new HttpOllamaClient(
    process.env.OLLAMA_BASE_URL ?? "http://127.0.0.1:11434",
    process.env.OLLAMA_API_KEY,
    process.env.OLLAMA_MODEL ?? "qwen3:32b",
  );
}

export interface AssistantHealth {
  status: "ok" | "degraded" | "offline";
  mode: "mock" | "live";
  model: string;
  detail?: string;
}

/** Lightweight readiness probe for UI banners (mock always ok). */
export async function probeAssistantHealth(
  fetchImpl: typeof fetch = fetch,
): Promise<AssistantHealth> {
  if (process.env.OLLAMA_MOCK === "1") {
    return { status: "ok", mode: "mock", model: "mock" };
  }
  const baseUrl = process.env.OLLAMA_BASE_URL ?? "http://127.0.0.1:11434";
  const model = process.env.OLLAMA_MODEL ?? "qwen3:32b";
  const apiKey = process.env.OLLAMA_API_KEY;
  try {
    const response = await fetchImpl(`${baseUrl}/api/tags`, {
      headers: {
        ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
      },
      signal: AbortSignal.timeout(4_000),
    });
    if (!response.ok) {
      return {
        status: "degraded",
        mode: "live",
        model,
        detail: `HTTP ${response.status}`,
      };
    }
    return { status: "ok", mode: "live", model };
  } catch (error) {
    return {
      status: "offline",
      mode: "live",
      model,
      detail: error instanceof Error ? error.message : "unreachable",
    };
  }
}
