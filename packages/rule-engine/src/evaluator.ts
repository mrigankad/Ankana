import {
  computeTransitSnapshot,
  type VedicChartArtifact,
} from "@astro/astrology-core";

import { VEDIC_PREDICTION_RULES } from "./packs/vedic-predictions";
import type { Domain, Prediction, Rule, RuleCondition } from "./types";

export interface EvaluationOptions {
  /** Evaluation start; defaults to now. */
  from?: Date;
  horizonYears?: number;
  domains?: Domain[];
  rules?: Rule[];
}

interface WindowContext {
  start: Date;
  end: Date;
  level: "mahadasha" | "antardasha";
  lord: string;
  sadeSatiActive: boolean;
}

interface ChartFacts {
  ownedHouses: Map<string, number[]>;
  houseOf: Map<string, number>;
  dignityOf: Map<string, string>;
  combust: Set<string>;
  strengthRatio: Map<string, number>;
  presentYogas: Set<string>;
}

function buildFacts(artifact: VedicChartArtifact): ChartFacts {
  const ownedHouses = new Map<string, number[]>();
  for (const house of artifact.houses) {
    const list = ownedHouses.get(house.lord) ?? [];
    list.push(house.number);
    ownedHouses.set(house.lord, list);
  }

  return {
    ownedHouses,
    houseOf: new Map(artifact.planets.map((p) => [p.planet, p.house])),
    dignityOf: new Map(artifact.planets.map((p) => [p.planet, p.dignity])),
    combust: new Set(
      artifact.planets.filter((p) => p.combust).map((p) => p.planet),
    ),
    strengthRatio: new Map(
      artifact.strengthMetrics.shadbala.map((r) => [r.planet as string, r.ratio]),
    ),
    presentYogas: new Set(
      artifact.yogas.filter((y) => y.present).map((y) => y.key),
    ),
  };
}

function conditionHolds(
  condition: RuleCondition,
  lord: string,
  facts: ChartFacts,
  window: WindowContext,
): { holds: boolean; evidence?: string } {
  switch (condition.kind) {
    case "dashaLordOwnsHouse": {
      const owned = facts.ownedHouses.get(lord) ?? [];
      const hits = owned.filter((h) => condition.houses.includes(h));
      return hits.length > 0
        ? { holds: true, evidence: `${lord} rules house ${hits.join(" and ")}` }
        : { holds: false };
    }
    case "dashaLordInHouse": {
      const house = facts.houseOf.get(lord);
      return house !== undefined && condition.houses.includes(house)
        ? { holds: true, evidence: `${lord} occupies house ${house}` }
        : { holds: false };
    }
    case "dashaLordDignity": {
      const dignity = facts.dignityOf.get(lord);
      return dignity !== undefined && condition.dignities.includes(dignity)
        ? { holds: true, evidence: `${lord} is ${dignity}` }
        : { holds: false };
    }
    case "dashaLordStrengthRatioAtLeast": {
      const ratio = facts.strengthRatio.get(lord);
      return ratio !== undefined && ratio >= condition.ratio
        ? {
            holds: true,
            evidence: `${lord} Shadbala ratio ${ratio.toFixed(2)} ≥ ${condition.ratio}`,
          }
        : { holds: false };
    }
    case "dashaLordStrengthRatioBelow": {
      const ratio = facts.strengthRatio.get(lord);
      return ratio !== undefined && ratio < condition.ratio
        ? {
            holds: true,
            evidence: `${lord} Shadbala ratio ${ratio.toFixed(2)} < ${condition.ratio}`,
          }
        : { holds: false };
    }
    case "dashaLordIs":
      return condition.planets.includes(lord)
        ? { holds: true, evidence: `${window.level} lord is ${lord}` }
        : { holds: false };
    case "dashaLordCombust":
      return facts.combust.has(lord)
        ? { holds: true, evidence: `${lord} is combust in the natal chart` }
        : { holds: false };
    case "yogaPresent": {
      const hits = condition.keys.filter((k) => facts.presentYogas.has(k));
      return hits.length > 0
        ? { holds: true, evidence: `natal yoga present: ${hits.join(", ")}` }
        : { holds: false };
    }
    case "sadeSatiActiveAtWindow":
      return window.sadeSatiActive
        ? { holds: true, evidence: "sade sati is active at the window midpoint" }
        : { holds: false };
  }
}

function windowLabel(window: WindowContext): string {
  return `${window.start.toISOString().slice(0, 10)} to ${window.end.toISOString().slice(0, 10)}`;
}

export function evaluatePredictions(
  artifact: VedicChartArtifact,
  options: EvaluationOptions = {},
): Prediction[] {
  const from = options.from ?? new Date();
  const horizonYears = Math.min(options.horizonYears ?? 5, 30);
  const until = new Date(
    from.getTime() + horizonYears * 365.2425 * 86_400_000,
  );
  const rules = options.rules ?? VEDIC_PREDICTION_RULES;
  const facts = buildFacts(artifact);

  // Windows: antardashas overlapping the horizon, carrying both lords.
  const windows: Array<{
    start: Date;
    end: Date;
    mdLord: string;
    adLord: string;
  }> = [];

  for (const mahadasha of artifact.vimshottari.mahadashas) {
    for (const antardasha of mahadasha.children ?? []) {
      const start = new Date(antardasha.start);
      const end = new Date(antardasha.end);
      if (end <= from || start >= until) {
        continue;
      }
      windows.push({ start, end, mdLord: mahadasha.planet, adLord: antardasha.planet });
    }
  }

  const predictions: Prediction[] = [];

  for (const window of windows) {
    const midpoint = new Date(
      (window.start.getTime() + window.end.getTime()) / 2,
    );
    const sadeSatiActive = computeTransitSnapshot(artifact, midpoint).sadeSati
      .active;

    const contexts: WindowContext[] = [
      {
        start: window.start,
        end: window.end,
        level: "mahadasha",
        lord: window.mdLord,
        sadeSatiActive,
      },
      {
        start: window.start,
        end: window.end,
        level: "antardasha",
        lord: window.adLord,
        sadeSatiActive,
      },
    ];

    const byDomain = new Map<
      Domain,
      { rules: Rule[]; evidence: string[]; narratives: string[]; lords: Set<string> }
    >();

    for (const context of contexts) {
      for (const rule of rules) {
        if (options.domains && !options.domains.includes(rule.domain)) {
          continue;
        }

        const evidence: string[] = [];
        let allHold = true;
        for (const condition of rule.when) {
          const result = conditionHolds(condition, context.lord, facts, context);
          if (!result.holds) {
            allHold = false;
            break;
          }
          if (result.evidence) {
            evidence.push(result.evidence);
          }
        }
        if (!allHold) {
          continue;
        }

        const entry = byDomain.get(rule.domain) ?? {
          rules: [],
          evidence: [],
          narratives: [],
          lords: new Set<string>(),
        };
        entry.rules.push(rule);
        entry.lords.add(context.lord);
        entry.evidence.push(
          ...evidence.map((e) => `${e} (${rule.source})`),
        );
        entry.narratives.push(
          rule.text
            .replaceAll("{level}", context.level)
            .replaceAll("{lord}", context.lord),
        );
        byDomain.set(rule.domain, entry);
      }
    }

    for (const [domain, entry] of byDomain) {
      const supportive = entry.rules.filter((r) => r.effect === "supportive");
      const challenging = entry.rules.filter((r) => r.effect === "challenging");
      const effect =
        supportive.length && challenging.length
          ? "mixed"
          : supportive.length
            ? "supportive"
            : "challenging";

      const matchedWeight = entry.rules.reduce((sum, r) => sum + r.weight, 0);
      const ratios = [...entry.lords]
        .map((lord) => facts.strengthRatio.get(lord))
        .filter((r): r is number => r !== undefined);
      const meanRatio = ratios.length
        ? ratios.reduce((a, b) => a + b, 0) / ratios.length
        : 1;
      const strengthFactor = Math.min(Math.max(0.75 + 0.25 * meanRatio, 0.75), 1.25);
      const confidence = Math.min(
        Math.max((matchedWeight / (matchedWeight + 4)) * strengthFactor, 0.05),
        0.95,
      );

      predictions.push({
        domain,
        window: {
          start: window.start.toISOString(),
          end: window.end.toISOString(),
        },
        headline: `${domain} - ${window.mdLord} mahadasha / ${window.adLord} antardasha (${windowLabel(contexts[0])})`,
        narrative: [...new Set(entry.narratives)].join(" "),
        effect,
        confidence: Math.round(confidence * 100) / 100,
        evidence: [...new Set(entry.evidence)],
        ruleIds: [...new Set(entry.rules.map((r) => r.id))],
      });
    }
  }

  return predictions.sort(
    (a, b) => a.window.start.localeCompare(b.window.start) ||
      a.domain.localeCompare(b.domain),
  );
}
