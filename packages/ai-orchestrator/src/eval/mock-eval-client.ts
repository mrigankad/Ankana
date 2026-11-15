import type { ChatMessage, OllamaClient } from "../assistant-service";

const REFUSAL_RE =
  /\b(die|death|cancer|diagnos|lawsuit|court case|litigation|rectif(?:y|ication)|birth time.*wrong|stocks?|invest|guarante(?:e|ed) money)\b/i;

const ADVISORY =
  "Advisory guidance only - not medical, legal, or financial advice.";

function lastUserQuestion(messages: ChatMessage[]): string {
  return (
    [...messages].reverse().find((m) => m.role === "user")?.content ?? ""
  );
}

function hasToolMessages(messages: ChatMessage[]): boolean {
  return messages.some((m) => m.role === "tool");
}

function pickTools(question: string): string[] {
  const q = question.toLowerCase();
  if (/\blife stage|childhood|your life|life chapters?\b/.test(q)) {
    return ["get_life_story", "get_dashas"];
  }
  if (/\bdeep reading|reading highlights?\b/.test(q)) {
    return ["get_reading_summary", "get_birth_chart"];
  }
  if (
    /\bclassically|classical meaning|what does .* (mean|signify)|karaka|signification of\b/.test(
      q,
    )
  ) {
    return ["search_classical", "get_birth_chart"];
  }
  if (/\bremed/.test(q)) return ["get_remedies", "get_birth_chart"];
  if (/\bpredict|window|next (few )?years?|career timing\b/.test(q)) {
    return ["get_predictions", "get_dashas"];
  }
  if (/\btransit|sade sati\b/.test(q)) {
    return ["get_birth_chart", "get_transits"];
  }
  if (/\byoga|dosha\b/.test(q)) return ["get_yogas", "get_birth_chart"];
  if (/\bshadbala|strength\b/.test(q)) return ["get_strengths", "get_birth_chart"];
  if (/\bmahadasha|antardasha|dasha\b/.test(q)) {
    return ["get_dashas", "get_birth_chart"];
  }
  if (/\b10th|tenth house|vocation\b/.test(q)) {
    return ["get_birth_chart", "get_predictions"];
  }
  return ["get_birth_chart", "get_dashas"];
}

function parseToolPayload(content: string): {
  summary?: string;
  data?: unknown;
} {
  try {
    return JSON.parse(content) as { summary?: string; data?: unknown };
  } catch {
    return {};
  }
}

function lagnaFromTools(messages: ChatMessage[]): string | null {
  for (const message of messages) {
    if (message.role !== "tool") continue;
    const payload = parseToolPayload(message.content);
    const data = payload.data as
      | { ascendant?: { signName?: string } }
      | undefined;
    // Natal get_birth_chart payload includes ascendant; transits do not.
    if (data?.ascendant?.signName) return data.ascendant.signName;
  }
  return null;
}

function planetLineFromTools(
  messages: ChatMessage[],
  planet: string,
): string | null {
  for (const message of messages) {
    if (message.role !== "tool") continue;
    const payload = parseToolPayload(message.content);
    const data = payload.data as
      | {
          ascendant?: { signName?: string };
          planets?: Array<{ planet: string; signName: string; house: number }>;
        }
      | undefined;
    // Only natal chart rows (paired with ascendant) - never transit snapshots.
    if (!data?.ascendant) continue;
    const row = data.planets?.find((p) => p.planet === planet);
    if (row) {
      return `${row.planet} in ${row.signName} in house ${row.house}`;
    }
  }
  return null;
}

/**
 * Deterministic eval mock: refuses banned topics; otherwise calls tools and
 * cites lagna/placements drawn from tool JSON (never invents signs).
 */
export class EvalMockOllamaClient implements OllamaClient {
  async chat(messages: ChatMessage[]): Promise<ChatMessage> {
    const question = lastUserQuestion(messages);

    if (REFUSAL_RE.test(question)) {
      return {
        role: "assistant",
        content: `I cannot answer that request. Nakshatra refuses birth-time rectification claims, predictions of death or serious disease, litigation outcomes, and medical, legal, or financial instructions. I can discuss chart structure and timing themes from the tools instead. ${ADVISORY}`,
      };
    }

    if (!hasToolMessages(messages)) {
      return {
        role: "assistant",
        content: "",
        tool_calls: pickTools(question).map((name) => ({
          function: {
            name,
            arguments:
              name === "search_classical"
                ? { query: question.slice(0, 120), topK: 3 }
                : {},
          },
        })),
      };
    }

    const lagna = lagnaFromTools(messages);
    const moon = planetLineFromTools(messages, "moon");
    const toolSummaries = messages
      .filter((m) => m.role === "tool")
      .map((m) => parseToolPayload(m.content).summary)
      .filter(Boolean);

    const bullets = [
      lagna ? `Lagna is ${lagna} [1].` : "Natal structure is in the chart tools [1].",
      moon ? `Moon placement: ${moon} [1].` : null,
      toolSummaries[1]
        ? `Supporting timing/context: ${toolSummaries[1]} [2].`
        : "Current periods frame timing [2].",
    ].filter(Boolean);

    return {
      role: "assistant",
      content: `**Chart-grounded notes**\n\n${bullets.map((b) => `- ${b}`).join("\n")}\n\n${ADVISORY}`,
    };
  }
}
