import { NAKSHATRA_SPAN } from "./zodiac";

/** 0.1° ≈ ~4 minutes birth-time error near a boundary. */
export const BOUNDARY_THRESHOLD_DEG = 0.1;

const PADA_SPAN = NAKSHATRA_SPAN / 4;

export type BoundaryKind = "sign" | "nakshatra" | "pada";

export interface BoundaryWarning {
  body: string;
  kind: BoundaryKind;
  distanceDeg: number;
}

function distanceToMultiple(longitude: number, span: number): number {
  const within = ((longitude % span) + span) % span;
  return Math.min(within, span - within);
}

/**
 * Flags bodies within THRESHOLD of a sign / nakshatra / pada cusp so the UI
 * can mark the chart as birth-time sensitive.
 */
export function boundaryWarnings(
  longitudes: Record<string, number>,
  ascendantLongitude: number,
): BoundaryWarning[] {
  const warnings: BoundaryWarning[] = [];
  const bodies: Record<string, number> = {
    ...longitudes,
    ascendant: ascendantLongitude,
  };

  for (const [body, longitude] of Object.entries(bodies)) {
    for (const [kind, span] of [
      ["sign", 30] as const,
      ["nakshatra", NAKSHATRA_SPAN] as const,
      ["pada", PADA_SPAN] as const,
    ]) {
      const distance = distanceToMultiple(longitude, span);
      if (distance <= BOUNDARY_THRESHOLD_DEG) {
        warnings.push({
          body,
          kind,
          distanceDeg: Math.round(distance * 10000) / 10000,
        });
      }
    }
  }

  return warnings;
}
