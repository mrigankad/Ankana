import {
  computeTransitSnapshot,
  type VedicChartArtifact,
} from "@astro/astrology-core";
import {
  detectMasnui,
  detectRin,
  lalKitabReport,
  lkChart,
  remedies as lkRemedies,
  sleepingHouses,
  sleepingPlanets,
  varshphal as lkVarshphal,
  VARSHPHAL_MAX_AGE,
  yearOfLife,
  type LkOrigin,
} from "@astro/lal-kitab";
import {
  evaluatePredictions,
  evaluateRemedies,
} from "@astro/rule-engine";

import { searchClassical } from "./classical/retrieve";
import {
  isLifeStoryLens,
  type ChartReadingContext,
  type LifeStoryLens,
} from "./reading-context";

export interface ToolDefinition {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: {
      type: "object";
      properties: Record<string, unknown>;
      required?: string[];
    };
  };
}

/** DOM / tab anchors for citation jump-to-evidence. */
export const TOOL_ANCHORS: Record<string, string> = {
  get_birth_chart: "planets",
  get_dashas: "dashas",
  get_yogas: "yogas",
  get_strengths: "strengths",
  get_transits: "transits",
  get_predictions: "predictions",
  get_remedies: "remedies",
  get_reading_summary: "reading",
  get_life_story: "your-life",
  // Future "lal-kitab" tab (not built yet); anchors are stable ids.
  lk_chart: "lal-kitab",
  lk_sleeping: "lal-kitab-sleeping",
  lk_rin: "lal-kitab-rin",
  lk_masnui: "lal-kitab-masnui",
  lk_varshphal: "lal-kitab-varshphal",
  lk_upay: "lal-kitab-upay",
};

export const TOOL_DEFINITIONS: ToolDefinition[] = [
  {
    type: "function",
    function: {
      name: "get_birth_chart",
      description:
        "Natal chart facts: lagna, planet placements with signs, houses, nakshatras, dignities, retrograde and combustion flags.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "get_dashas",
      description:
        "Vimshottari dasha timeline with the currently running mahadasha and antardasha.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "get_yogas",
      description: "Detected yogas and doshas with their supporting evidence.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "get_strengths",
      description:
        "Shadbala ratios, Vimshopaka scores, and Sarvashtakavarga bindus per sign.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "get_transits",
      description:
        "Current transit snapshot against the natal chart, including sade sati status.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "get_predictions",
      description:
        "Rule-engine prediction windows (dated, with confidence and evidence) for the next five years.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "get_remedies",
      description:
        "Rule-gated remedy suggestions with rationales and cautions.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "get_reading_summary",
      description:
        "Deterministic Deep reading: lagna, planets, houses, yogas, dasha, vargas, and panchang narrative sections with evidence lines.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "get_life_story",
      description:
        "Your Life chapters (childhood through later life) from the deterministic life-story engine. Optional lens: hybrid (default), ageBands, or dashaChapters.",
      parameters: {
        type: "object",
        properties: {
          lens: {
            type: "string",
            enum: ["hybrid", "ageBands", "dashaChapters"],
            description:
              "Which chapter layout to return. hybrid blends age bands with dasha context.",
          },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "lk_chart",
      description:
        "Lal Kitab chart: planets by house with the ascendant as house 1 (book convention), plus matched planet-in-house notes and aspects. Optional origin: lagna_h1 (default) or aries_h1.",
      parameters: {
        type: "object",
        properties: {
          origin: {
            type: "string",
            enum: ["lagna_h1", "aries_h1"],
            description: "How houses are numbered. Default lagna_h1.",
          },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "lk_sleeping",
      description:
        "Lal Kitab dormant (sleeping) planets and houses, which planet awakens each, and the age each planet awakens by itself.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "lk_rin",
      description:
        "Lal Kitab rin (karmic debts): which of the nine debts the chart shows, with cause, symptoms and the family remedy. Rows flagged needs_review are uncertain.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "lk_masnui",
      description:
        "Lal Kitab masnui (artificial) planets formed when two planets share a house.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "lk_varshphal",
      description:
        "Lal Kitab annual chart (varshphal) from the book age matrix (years 1-100), the Vikram month of each house, and the 35-year cycle position. Optional age = year of life; defaults to the current one.",
      parameters: {
        type: "object",
        properties: {
          age: {
            type: "number",
            description:
              "Year of life 1-100 (1 = first year). Defaults to the current year of life.",
          },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "lk_upay",
      description:
        "Ranked Lal Kitab remedies (upay) with citations. The book says to run one remedy at a time for 40-43 days, pause a few days, then start the next.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "search_classical",
      description:
        "Retrieve curated classical / pedagogical Jyotish snippets (houses, graha karakas, yoga themes, dasha tone, remedy principles). Use to color meaning only - never as a source of this chart's placements or numbers. Returns passages with stable source ids.",
      parameters: {
        type: "object",
        properties: {
          query: {
            type: "string",
            description:
              "Short topical query, e.g. '10th house career', 'Saturn mahadasha', 'Gajakesari meaning'.",
          },
          topK: {
            type: "number",
            description: "Max passages to return (1-5). Default 3.",
          },
        },
        required: ["query"],
      },
    },
  },
];

export interface ExecuteToolOptions {
  reading?: ChartReadingContext | null;
  args?: Record<string, unknown>;
}

function parseToolArgs(raw: unknown): Record<string, unknown> {
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw) as unknown;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      return {};
    }
    return {};
  }
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    return raw as Record<string, unknown>;
  }
  return {};
}

/** Executes a tool read-only against already-computed data. */
export function executeTool(
  name: string,
  artifact: VedicChartArtifact,
  now: Date,
  options?: ExecuteToolOptions,
): { summary: string; data: unknown; anchor?: string } {
  const args = options?.args ?? {};
  const reading = options?.reading ?? null;
  const anchor = TOOL_ANCHORS[name];

  switch (name) {
    case "get_birth_chart":
      return {
        summary: `Lagna ${artifact.ascendant.signName} ${artifact.ascendant.degreesInSign.toFixed(1)}°; house lords: ${artifact.houses.map((h) => `H${h.number}:${h.lord}`).join(" ")}; ${artifact.planets
          .map((p) => `${p.planet} ${p.signName} H${p.house}${p.retrograde ? " R" : ""}${p.combust ? " combust" : ""}`)
          .join(", ")}`,
        data: {
          ascendant: artifact.ascendant,
          planets: artifact.planets,
          houses: artifact.houses,
        },
        anchor,
      };
    case "get_dashas": {
      const nowMs = now.getTime();
      const md = artifact.vimshottari.mahadashas.find(
        (m) =>
          new Date(m.start).getTime() <= nowMs &&
          nowMs < new Date(m.end).getTime(),
      );
      const ad = md?.children?.find(
        (a) =>
          new Date(a.start).getTime() <= nowMs &&
          nowMs < new Date(a.end).getTime(),
      );
      return {
        summary: `Current mahadasha ${md?.planet ?? "unknown"} (${md?.start.slice(0, 10)}–${md?.end.slice(0, 10)}), antardasha ${ad?.planet ?? "unknown"} (${ad?.start.slice(0, 10)}–${ad?.end.slice(0, 10)})`,
        data: {
          current: { mahadasha: md, antardasha: ad },
          timeline: artifact.vimshottari,
        },
        anchor,
      };
    }
    case "get_yogas": {
      const present = artifact.yogas.filter((y) => y.present);
      return {
        summary: `Present yogas: ${present.map((y) => y.name).join(", ") || "none detected"}`,
        data: present,
        anchor,
      };
    }
    case "get_strengths":
      return {
        summary: `Shadbala ratios: ${artifact.strengthMetrics.shadbala
          .map((s) => `${s.planet} ${s.ratio.toFixed(2)}`)
          .join(", ")}`,
        data: artifact.strengthMetrics,
        anchor,
      };
    case "get_transits": {
      const snapshot = computeTransitSnapshot(artifact, now);
      return {
        summary: `Transits ${snapshot.date.slice(0, 10)}: ${snapshot.planets
          .map((p) => `${p.planet} ${p.signName}`)
          .join(", ")}; sade sati ${snapshot.sadeSati.active ? `active (${snapshot.sadeSati.phase})` : "inactive"}`,
        data: snapshot,
        anchor,
      };
    }
    case "get_predictions": {
      const predictions = evaluatePredictions(artifact, {
        from: now,
        horizonYears: 5,
      });
      return {
        summary: `${predictions.length} prediction windows in the next 5 years`,
        data: predictions,
        anchor,
      };
    }
    case "get_remedies": {
      const remedies = evaluateRemedies(artifact);
      return {
        summary: `${remedies.length} remedies suggested`,
        data: remedies,
        anchor,
      };
    }
    case "get_reading_summary": {
      if (!reading?.sections?.length) {
        return {
          summary: "Deep reading is unavailable for this session",
          data: { available: false },
          anchor,
        };
      }
      const condensed = reading.sections.map((section) => ({
        key: section.key,
        title: section.title,
        highlights: section.items.slice(0, 3).map((item) => ({
          title: item.title,
          text: item.text,
          evidence: item.evidence.slice(0, 4),
        })),
      }));
      return {
        summary: `Deep reading (${reading.sections.length} sections): ${reading.sections
          .map((s) => s.title)
          .join("; ")}`,
        data: {
          available: true,
          engineVersion: reading.engineVersion,
          generatedAt: reading.generatedAt,
          sections: condensed,
        },
        anchor,
      };
    }
    case "get_life_story": {
      const lens: LifeStoryLens = isLifeStoryLens(args.lens)
        ? args.lens
        : "hybrid";
      const lifeStory = reading?.lifeStory;
      if (!lifeStory?.lenses?.[lens]?.length) {
        return {
          summary: `Your Life (${lens}) is unavailable for this session`,
          data: { available: false, lens },
          anchor,
        };
      }
      const chapters = lifeStory.lenses[lens].map((chapter) => ({
        key: chapter.key,
        title: chapter.title,
        ageRange: chapter.ageRange,
        years: chapter.years,
        isCurrent: chapter.isCurrent ?? false,
        summary: chapter.summary,
        dashas: chapter.dashas,
        items: chapter.items.slice(0, 3).map((item) => ({
          title: item.title,
          text: item.text,
          evidence: item.evidence.slice(0, 4),
        })),
      }));
      const current = chapters.find((c) => c.isCurrent);
      return {
        summary: `Your Life (${lens}): ${chapters.length} chapters${
          current ? `; current "${current.title}"` : ""
        }; age ${lifeStory.currentAgeYears}`,
        data: {
          available: true,
          lens,
          birthDate: lifeStory.birthDate,
          currentAgeYears: lifeStory.currentAgeYears,
          chapters,
        },
        anchor,
      };
    }
    case "lk_chart": {
      const origin: LkOrigin =
        args.origin === "aries_h1" ? "aries_h1" : "lagna_h1";
      const report = lalKitabReport(artifact, { origin, now });
      return {
        summary: `Lal Kitab chart (${origin}): ${report.chart.houses
          .slice(1)
          .map((ps, i) => (ps.length ? `H${i + 1}:${ps.join("+")}` : ""))
          .filter(Boolean)
          .join(" ")}`,
        data: {
          origin,
          houses: report.chart.houses
            .slice(1)
            .map((planets, i) => ({ house: i + 1, planets })),
          aspects: report.aspects,
          planetHouse: report.planetHouse,
          coverage: report.coverage,
        },
        anchor,
      };
    }
    case "lk_sleeping": {
      const chart = lkChart(artifact);
      const planets = sleepingPlanets(chart);
      const houses = sleepingHouses(chart).filter(
        (h) => h.status === "dormant",
      );
      return {
        summary: `Dormant planets: ${planets
          .filter((p) => p.status === "dormant")
          .map((p) => `${p.planet} H${p.house}`)
          .join(", ") || "none"}; dormant houses: ${houses
          .map((h) => `H${h.house}`)
          .join(", ") || "none"}`,
        data: { planets, dormantHouses: houses },
        anchor,
      };
    }
    case "lk_rin": {
      const rin = detectRin(lkChart(artifact));
      return {
        summary: rin.length
          ? `Lal Kitab debts: ${rin.map((r) => `${r.kind} (${r.basis})`).join("; ")}`
          : "No Lal Kitab debt pattern detected",
        data: rin,
        anchor,
      };
    }
    case "lk_masnui": {
      const masnui = detectMasnui(lkChart(artifact));
      return {
        summary: masnui.length
          ? `Artificial planets: ${masnui
              .map(
                (m) =>
                  `${m.formedPlanet}${m.variant ? ` (${m.variant})` : ""} from ${m.components.join("+")} in H${m.house}`,
              )
              .join("; ")}`
          : "No artificial planets formed",
        data: masnui,
        anchor,
      };
    }
    case "lk_varshphal": {
      const chart = lkChart(artifact);
      const requested =
        typeof args.age === "number" && Number.isFinite(args.age)
          ? Math.floor(args.age)
          : yearOfLife(artifact.calculationMetadata.input.birthDate, now);
      if (requested < 1 || requested > VARSHPHAL_MAX_AGE) {
        return {
          summary: `Varshphal is available for years 1-${VARSHPHAL_MAX_AGE}; requested ${requested}`,
          data: { available: false, requested, max: VARSHPHAL_MAX_AGE },
          anchor,
        };
      }
      const v = lkVarshphal(chart, requested);
      return {
        summary: `Varshphal year ${v.age}: ${v.planets
          .map((p) => `${p.planet} H${p.natalHouse}->H${p.annualHouse}`)
          .join(", ")}; 35-year cycle ${v.cycle35.cyclePlanet} (${v.cycle35.part})`,
        data: {
          age: v.age,
          planets: v.planets,
          row: v.row,
          cycle35: v.cycle35,
          semantics: v.semantics,
        },
        anchor,
      };
    }
    case "lk_upay": {
      const plan = lkRemedies(lkChart(artifact));
      return {
        summary: `${plan.upay.length} Lal Kitab upay ranked; run one at a time (${plan.oneAtATime.durationDays.join("/")} days each)`,
        data: plan,
        anchor,
      };
    }
    case "search_classical": {
      const query =
        typeof args.query === "string" ? args.query.trim() : "";
      const topKRaw = typeof args.topK === "number" ? args.topK : 3;
      const topK = Number.isFinite(topKRaw)
        ? Math.max(1, Math.min(5, Math.floor(topKRaw)))
        : 3;
      if (query.length < 2) {
        return {
          summary: "Classical search requires a query of at least 2 characters",
          data: { available: false, hits: [] },
        };
      }
      const hits = searchClassical(query, topK);
      if (hits.length === 0) {
        return {
          summary: `No classical notes matched "${query.slice(0, 60)}"`,
          data: { available: true, query, hits: [] },
        };
      }
      return {
        summary: `Classical notes (${hits.length}): ${hits
          .map((h) => `${h.id} ${h.title}`)
          .join("; ")}`,
        data: {
          available: true,
          query,
          hits: hits.map((h) => ({
            id: h.id,
            source: h.source,
            title: h.title,
            text: h.text,
            score: h.score,
          })),
        },
        // No chart DOM anchor - interpretive library only.
      };
    }
    default:
      return { summary: `Unknown tool ${name}`, data: null };
  }
}

export { parseToolArgs };
