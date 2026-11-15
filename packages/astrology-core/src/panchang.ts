import { normalizeDegrees } from "./ephemeris";
import { nakshatraOf } from "./zodiac";

export const TITHI_NAMES = [
  "Pratipada",
  "Dwitiya",
  "Tritiya",
  "Chaturthi",
  "Panchami",
  "Shashthi",
  "Saptami",
  "Ashtami",
  "Navami",
  "Dashami",
  "Ekadashi",
  "Dwadashi",
  "Trayodashi",
  "Chaturdashi",
] as const;

export const YOGA_NAMES = [
  "Vishkumbha",
  "Priti",
  "Ayushman",
  "Saubhagya",
  "Shobhana",
  "Atiganda",
  "Sukarma",
  "Dhriti",
  "Shula",
  "Ganda",
  "Vriddhi",
  "Dhruva",
  "Vyaghata",
  "Harshana",
  "Vajra",
  "Siddhi",
  "Vyatipata",
  "Variyana",
  "Parigha",
  "Shiva",
  "Siddha",
  "Sadhya",
  "Shubha",
  "Shukla",
  "Brahma",
  "Indra",
  "Vaidhriti",
] as const;

const MOVABLE_KARANAS = [
  "Bava",
  "Balava",
  "Kaulava",
  "Taitila",
  "Garaja",
  "Vanija",
  "Vishti",
] as const;

const FIXED_KARANAS = ["Shakuni", "Chatushpada", "Naga", "Kimstughna"] as const;

export const VARA_NAMES = [
  "Ravivara",
  "Somavara",
  "Mangalavara",
  "Budhavara",
  "Guruvara",
  "Shukravara",
  "Shanivara",
] as const;

export interface Panchang {
  tithi: { index: number; name: string; paksha: "shukla" | "krishna" };
  karana: { index: number; name: string };
  yoga: { index: number; name: string };
  vara: { index: number; name: string };
  moonNakshatra: { index: number; name: string; pada: number };
}

export function computePanchang(
  sunSiderealLongitude: number,
  moonSiderealLongitude: number,
  localWeekday: number,
): Panchang {
  const elongation = normalizeDegrees(
    moonSiderealLongitude - sunSiderealLongitude,
  );

  const tithiIndex = Math.floor(elongation / 12); // 0-29
  const paksha = tithiIndex < 15 ? "shukla" : "krishna";
  const tithiWithinPaksha = tithiIndex % 15;
  const tithiName =
    tithiWithinPaksha === 14
      ? paksha === "shukla"
        ? "Purnima"
        : "Amavasya"
      : TITHI_NAMES[tithiWithinPaksha];

  // 60 half-tithi karanas: Kimstughna leads, 7 movable karanas repeat
  // eight times, and the final three are the remaining fixed karanas.
  const karanaIndex = Math.floor(elongation / 6); // 0-59
  let karanaName: string;
  if (karanaIndex === 0) {
    karanaName = FIXED_KARANAS[3]; // Kimstughna
  } else if (karanaIndex >= 57) {
    karanaName = FIXED_KARANAS[karanaIndex - 57]; // Shakuni, Chatushpada, Naga
  } else {
    karanaName = MOVABLE_KARANAS[(karanaIndex - 1) % 7];
  }

  const yogaIndex = Math.floor(
    normalizeDegrees(sunSiderealLongitude + moonSiderealLongitude) / (360 / 27),
  );

  const moonNakshatra = nakshatraOf(moonSiderealLongitude);

  return {
    tithi: { index: tithiIndex + 1, name: tithiName, paksha },
    karana: { index: karanaIndex + 1, name: karanaName },
    yoga: { index: yogaIndex + 1, name: YOGA_NAMES[yogaIndex] },
    vara: { index: localWeekday, name: VARA_NAMES[localWeekday] },
    moonNakshatra: {
      index: moonNakshatra.index + 1,
      name: moonNakshatra.name,
      pada: moonNakshatra.pada,
    },
  };
}
