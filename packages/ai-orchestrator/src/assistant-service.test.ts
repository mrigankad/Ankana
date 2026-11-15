import { computeVedicChartArtifact } from "@astro/astrology-core";
import { describe, expect, it } from "vitest";

import {
  MockOllamaClient,
  SYSTEM_PROMPT,
  askAssistant,
  type ChatMessage,
  type OllamaClient,
} from "./assistant-service";
import { assessGrounding } from "./grounding";
import type { ChartReadingContext } from "./reading-context";
import { TOOL_DEFINITIONS, executeTool } from "./tools";

const artifact = computeVedicChartArtifact({
  birthDate: "1990-01-01",
  birthTime: "10:30",
  timezoneName: "Asia/Kolkata",
  latitude: 25.3176,
  longitude: 82.9739,
  placeLabel: "Varanasi, Uttar Pradesh, India",
});

const NOW = new Date("2026-07-09T00:00:00Z");

const sampleReading: ChartReadingContext = {
  generatedAt: "2026-08-02T00:00:00Z",
  engineVersion: "test",
  sections: [
    {
      key: "lagna",
      title: "Lagna",
      items: [
        {
          title: "Rising sign",
          text: "Aries lagna sets a pioneering tone.",
          evidence: ["Ascendant Aries"],
        },
      ],
    },
    {
      key: "dasha",
      title: "Dasha",
      items: [
        {
          title: "Current period",
          text: "Saturn mahadasha frames discipline.",
          evidence: ["Saturn MD"],
        },
      ],
    },
  ],
  lifeStory: {
    generatedAt: "2026-08-02T00:00:00Z",
    birthDate: "1990-01-01",
    currentAgeYears: 36,
    lenses: {
      hybrid: [
        {
          key: "hybrid-childhood",
          title: "Childhood",
          ageRange: { from: 0, to: 12 },
          summary: "Early foundations under birth dasha.",
          dashas: [],
          items: [
            {
              title: "Home tone",
              text: "Caretaking patterns form early.",
              evidence: ["4th house"],
            },
          ],
        },
      ],
      ageBands: [],
      dashaChapters: [],
    },
  },
};

describe("executeTool", () => {
  it("answers every declared tool with a summary and data", () => {
    for (const tool of TOOL_DEFINITIONS) {
      const result = executeTool(tool.function.name, artifact, NOW, {
        reading: sampleReading,
      });
      expect(result.summary.length).toBeGreaterThan(0);
      expect(result.data).not.toBeNull();
    }
  });

  it("reports the current dasha correctly", () => {
    const result = executeTool("get_dashas", artifact, NOW);
    expect(result.summary).toContain("saturn");
  });

  it("returns reading and life story when context is provided", () => {
    const reading = executeTool("get_reading_summary", artifact, NOW, {
      reading: sampleReading,
    });
    expect(reading.summary).toContain("Deep reading");
    expect(reading.anchor).toBe("reading");

    const life = executeTool("get_life_story", artifact, NOW, {
      reading: sampleReading,
      args: { lens: "hybrid" },
    });
    expect(life.summary).toContain("Your Life");
    expect(life.summary).toContain("1 chapters");
    expect(life.anchor).toBe("your-life");
    expect(life.data).toMatchObject({
      available: true,
      chapters: [{ title: "Childhood" }],
    });
  });

  it("fails soft when reading context is missing", () => {
    const reading = executeTool("get_reading_summary", artifact, NOW);
    expect(reading.summary).toContain("unavailable");
    expect(reading.data).toMatchObject({ available: false });
  });
});

describe("askAssistant", () => {
  it("runs the tool loop and returns citations for each tool call", async () => {
    const answer = await askAssistant(
      new MockOllamaClient(),
      artifact,
      "Why is my Saturn mahadasha difficult?",
      NOW,
    );

    expect(answer.answer).toContain("[1]");
    expect(answer.citations).toHaveLength(2);
    expect(answer.citations[0]).toMatchObject({
      index: 1,
      tool: "get_birth_chart",
      anchor: "planets",
    });
    expect(answer.toolsUsed).toEqual(["get_birth_chart", "get_dashas"]);
    expect(answer.answer).toContain("Advisory guidance only");
  });

  it("includes prior history turns before the new question", async () => {
    const seen: ChatMessage[][] = [];
    const client: OllamaClient = {
      async chat(messages): Promise<ChatMessage> {
        seen.push(messages);
        if (seen.length === 1) {
          return {
            role: "assistant",
            content: "",
            tool_calls: [
              { function: { name: "get_birth_chart", arguments: {} } },
            ],
          };
        }
        return {
          role: "assistant",
          content:
            "Following up on your lagna question [1]. Advisory guidance only - not medical, legal, or financial advice.",
        };
      },
    };

    await askAssistant(
      client,
      artifact,
      "And what about career?",
      NOW,
      [
        { role: "user", content: "What does my lagna say?" },
        {
          role: "assistant",
          content: "Your lagna sets temperament [1].",
        },
      ],
    );

    const firstCall = seen[0];
    expect(firstCall[0]?.role).toBe("system");
    expect(firstCall[1]).toMatchObject({
      role: "user",
      content: "What does my lagna say?",
    });
    expect(firstCall[2]).toMatchObject({
      role: "assistant",
      content: "Your lagna sets temperament [1].",
    });
    expect(firstCall[3]).toMatchObject({
      role: "user",
      content: "And what about career?",
    });
  });

  it("summarizes older turns when history exceeds the window", async () => {
    const { windowHistory } = await import("./assistant-service");
    const longHistory = Array.from({ length: 16 }, (_, i) =>
      i % 2 === 0
        ? {
            role: "user" as const,
            content: `Question number ${i / 2 + 1} about houses`,
          }
        : {
            role: "assistant" as const,
            content: `Answer ${Math.floor(i / 2) + 1} with citation [1].`,
          },
    );
    const windowed = windowHistory(longHistory);
    expect(windowed.length).toBeLessThanOrEqual(10);
    expect(windowed[0]?.content).toContain("Earlier discussion on THIS chart only");
    expect(windowed.at(-1)?.content).toContain("Answer 8");
  });
});

describe("assessGrounding", () => {
  it("flags astrological prose without citations", () => {
    const result = assessGrounding(
      "Saturn mahadasha brings heavy work.",
      artifact,
    );
    expect(result.ok).toBe(false);
    expect(result.warning).toBeTruthy();
  });

  it("passes when citations are present", () => {
    const result = assessGrounding(
      "Saturn mahadasha frames timing [1].",
      artifact,
    );
    expect(result.ok).toBe(true);
  });

  it("flags planet-sign claims that contradict the chart", () => {
    const saturn = artifact.planets.find((p) => p.planet === "saturn");
    expect(saturn).toBeTruthy();
    const wrongSign =
      saturn!.signName.toLowerCase() === "leo" ? "aries" : "leo";
    const result = assessGrounding(
      `Saturn in ${wrongSign} [1]. Advisory guidance only.`,
      artifact,
    );
    expect(result.ok).toBe(false);
    expect(result.suspectClaims.length).toBeGreaterThan(0);
  });
});

describe("SYSTEM_PROMPT", () => {
  it("locks the refusal and citation policy", () => {
    expect(SYSTEM_PROMPT).toContain("bracket citation");
    expect(SYSTEM_PROMPT).toContain("Never invent chart facts");
    expect(SYSTEM_PROMPT).toContain("Refuse");
    expect(SYSTEM_PROMPT).toContain("Advisory guidance only");
    expect(SYSTEM_PROMPT).toContain("get_life_story");
    expect(SYSTEM_PROMPT).toContain("search_classical");
  });
});

describe("normalizeCitations", () => {
  it("rewrites model citation variants to plain [n]", async () => {
    const { normalizeCitations } = await import("./assistant-service");
    expect(normalizeCitations("fact【1†L40-L41】 and【2†screen】")).toBe(
      "fact[1] and[2]",
    );
    expect(normalizeCitations("both [1, 2] apply")).toBe("both [1][2] apply");
    expect(normalizeCitations("plain [3] stays")).toBe("plain [3] stays");
  });

  it("replaces em and en dashes with plain hyphens", async () => {
    const { normalizeCitations } = await import("./assistant-service");
    expect(normalizeCitations("Saturn years — heavy work")).toBe(
      "Saturn years - heavy work",
    );
    expect(normalizeCitations("ages 20–38")).toBe("ages 20-38");
  });
});
