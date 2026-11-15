export const SIGN_NAMES = [
  "Aries",
  "Taurus",
  "Gemini",
  "Cancer",
  "Leo",
  "Virgo",
  "Libra",
  "Scorpio",
  "Sagittarius",
  "Capricorn",
  "Aquarius",
  "Pisces",
] as const;

export type SignName = (typeof SIGN_NAMES)[number];

export const SIGN_LORDS = [
  "mars",
  "venus",
  "mercury",
  "moon",
  "sun",
  "mercury",
  "venus",
  "mars",
  "jupiter",
  "saturn",
  "saturn",
  "jupiter",
] as const;

export const NAKSHATRA_NAMES = [
  "Ashwini",
  "Bharani",
  "Krittika",
  "Rohini",
  "Mrigashira",
  "Ardra",
  "Punarvasu",
  "Pushya",
  "Ashlesha",
  "Magha",
  "Purva Phalguni",
  "Uttara Phalguni",
  "Hasta",
  "Chitra",
  "Swati",
  "Vishakha",
  "Anuradha",
  "Jyeshtha",
  "Mula",
  "Purva Ashadha",
  "Uttara Ashadha",
  "Shravana",
  "Dhanishta",
  "Shatabhisha",
  "Purva Bhadrapada",
  "Uttara Bhadrapada",
  "Revati",
] as const;

/** Vimshottari lord cycle: repeats three times across the 27 nakshatras. */
export const NAKSHATRA_LORD_CYCLE = [
  "ketu",
  "venus",
  "sun",
  "moon",
  "mars",
  "rahu",
  "jupiter",
  "saturn",
  "mercury",
] as const;

export const NAKSHATRA_SPAN = 360 / 27; // 13deg 20min

export interface SignPosition {
  index: number;
  name: SignName;
  lord: string;
  degreesInSign: number;
}

export interface NakshatraPosition {
  index: number;
  name: (typeof NAKSHATRA_NAMES)[number];
  lord: (typeof NAKSHATRA_LORD_CYCLE)[number];
  pada: number;
  fractionTraversed: number;
}

export function signOf(siderealLongitude: number): SignPosition {
  const index = Math.floor(siderealLongitude / 30) % 12;
  return {
    index,
    name: SIGN_NAMES[index],
    lord: SIGN_LORDS[index],
    degreesInSign: siderealLongitude - index * 30,
  };
}

export function nakshatraOf(siderealLongitude: number): NakshatraPosition {
  const index = Math.floor(siderealLongitude / NAKSHATRA_SPAN) % 27;
  const withinNakshatra = siderealLongitude - index * NAKSHATRA_SPAN;
  return {
    index,
    name: NAKSHATRA_NAMES[index],
    lord: NAKSHATRA_LORD_CYCLE[index % 9],
    pada: Math.floor(withinNakshatra / (NAKSHATRA_SPAN / 4)) + 1,
    fractionTraversed: withinNakshatra / NAKSHATRA_SPAN,
  };
}

export function isOddSign(signIndex: number): boolean {
  return signIndex % 2 === 0; // Aries (0) is the first odd sign.
}

export type SignModality = "movable" | "fixed" | "dual";

export function signModality(signIndex: number): SignModality {
  const modalities: SignModality[] = ["movable", "fixed", "dual"];
  return modalities[signIndex % 3];
}
