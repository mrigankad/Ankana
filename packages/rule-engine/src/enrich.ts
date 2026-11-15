import type { VedicChartArtifact } from "@astro/astrology-core";

import { evaluatePredictions, type EvaluationOptions } from "./evaluator";
import { evaluateRemedies } from "./remedies";
import type { Prediction } from "./types";

export type ConfidenceBand = "low" | "medium" | "high";

export interface EnrichedPrediction extends Prediction {
  confidenceBand: ConfidenceBand;
  confidenceDrivers?: string[];
  tension?: boolean;
  linkedRemedyPlanets?: string[];
}

function band(confidence: number): ConfidenceBand {
  if (confidence >= 0.7) return "high";
  if (confidence >= 0.4) return "medium";
  return "low";
}

function windowLords(headline: string): string[] {
  const words = headline.split(/\s+/);
  const lords: string[] = [];
  for (let i = 0; i < words.length; i += 1) {
    if (
      (words[i] === "mahadasha" || words[i] === "antardasha") &&
      i > 0 &&
      words[i - 1]
    ) {
      lords.push(words[i - 1]!);
    }
  }
  return lords;
}

/**
 * Additive enrichment over golden-parity predictions: confidence bands with
 * numeric drivers, tension flag for mixed windows, and remedy links for weak
 * window lords.
 */
export function evaluatePredictionsEnriched(
  artifact: VedicChartArtifact,
  options: EvaluationOptions = {},
): EnrichedPrediction[] {
  const predictions = evaluatePredictions(artifact, options);
  const ratioOf = new Map(
    artifact.strengthMetrics.shadbala.map((row) => [
      row.planet as string,
      row.ratio,
    ]),
  );
  const remedyPlanets = new Set(evaluateRemedies(artifact).map((r) => r.planet));

  return predictions.map((prediction) => {
    const enriched: EnrichedPrediction = {
      ...prediction,
      confidenceBand: band(prediction.confidence),
    };

    const lords = windowLords(prediction.headline);
    const drivers = lords
      .filter((lord) => ratioOf.has(lord))
      .map((lord) => `${lord} Shadbala ratio ${ratioOf.get(lord)!.toFixed(2)}`);
    if (drivers.length > 0) {
      enriched.confidenceDrivers = drivers;
    }

    if (prediction.effect === "mixed") {
      enriched.tension = true;
      enriched.narrative =
        "This window carries both supportive and challenging indications - read them together rather than choosing one: " +
        prediction.narrative;
    }

    const linked = [
      ...new Set(
        lords.filter(
          (lord) =>
            remedyPlanets.has(lord) &&
            (!ratioOf.has(lord) || ratioOf.get(lord)! < 1),
        ),
      ),
    ];
    if (linked.length > 0) {
      enriched.linkedRemedyPlanets = linked;
    }

    return enriched;
  });
}
