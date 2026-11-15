import { SIGN_LORDS, SIGN_NAMES, signOf, type SignName } from "./zodiac";

export interface House {
  number: number;
  signIndex: number;
  signName: SignName;
  lord: string;
}

/** Whole-sign houses: house 1 is the ascendant's entire sign. */
export function wholeSignHouses(ascendantSiderealLongitude: number): House[] {
  const ascSign = signOf(ascendantSiderealLongitude).index;

  return Array.from({ length: 12 }, (_, offset) => {
    const signIndex = (ascSign + offset) % 12;
    return {
      number: offset + 1,
      signIndex,
      signName: SIGN_NAMES[signIndex],
      lord: SIGN_LORDS[signIndex],
    };
  });
}

/** House number (1-12) occupied by a sidereal longitude, whole-sign. */
export function houseOf(
  siderealLongitude: number,
  ascendantSiderealLongitude: number,
): number {
  const ascSign = signOf(ascendantSiderealLongitude).index;
  const bodySign = signOf(siderealLongitude).index;
  return ((bodySign - ascSign + 12) % 12) + 1;
}
