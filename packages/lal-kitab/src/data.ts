import aspectsJson from "../data/aspects.json";
import cycle35Json from "../data/cycle35.json";
import dormantJson from "../data/dormant.json";
import friendshipJson from "../data/friendship.json";
import masnuiJson from "../data/masnui.json";
import pakkaGharJson from "../data/pakka_ghar.json";
import planetHouseJson from "../data/planet_house.json";
import moonJson from "../data/planet_house/moon.json";
import marsJson from "../data/planet_house/mars.json";
import mercuryJson from "../data/planet_house/mercury.json";
import jupiterJson from "../data/planet_house/jupiter.json";
import venusJson from "../data/planet_house/venus.json";
import saturnJson from "../data/planet_house/saturn.json";
import rahuJson from "../data/planet_house/rahu.json";
import ketuJson from "../data/planet_house/ketu.json";
import remedyDeliveryJson from "../data/remedy_delivery.json";
import rinJson from "../data/rin.json";
import varshphalJson from "../data/varshphal.json";

import type { Cite, Planet } from "./types";

export interface PakkaGharRow {
  planet: Planet;
  houses: number[];
  shared_houses: number[];
  cite: Cite;
  needs_review: boolean;
  note?: string;
}
export interface AspectRow {
  from: number;
  to: number[];
  strength: number;
  cite: Cite;
  needs_review: boolean;
  derived: boolean;
  note?: string;
}
export interface DormantRule {
  id: string;
  text: string;
  cite: Cite;
  needs_review: boolean;
  note?: string;
}
export interface DormantData {
  awakeners: Array<{ house: number; planet: Planet; cite: Cite; needs_review: boolean }>;
  self_awakening: Array<{
    planet: Planet;
    age: number;
    trigger: string;
    malefic_year_raw: string;
    cite: Cite;
    needs_review: boolean;
  }>;
  rules: DormantRule[];
}
export interface RinRow {
  id: string;
  planet: Planet;
  kind: string;
  placement_houses: number[];
  enemy_planets_with: Planet[];
  cause: string;
  symptoms: string;
  remedy: string;
  remedy_cite: Cite;
  cite: Cite;
  needs_review: boolean;
  note?: string;
}
export interface RinData {
  rows: RinRow[];
  first_degree_father: {
    rows: Array<{ planet: Planet; mercury_house: number[] }>;
    cite: Cite;
    needs_review: boolean;
  };
  general_indicator: {
    planets: Planet[];
    houses: number[];
    cite: Cite;
    needs_review: boolean;
  };
}
export interface MasnuiRow {
  id: string;
  formed_planet: Planet;
  variant: string | null;
  components: [Planet, Planet];
  note: string | null;
  cite: Cite;
  needs_review: boolean;
}
export interface MasnuiData {
  rows: MasnuiRow[];
  remedy_principle: { text: string; cite: Cite; cite2: Cite; needs_review: boolean };
}
export interface VarshphalData {
  rows: Array<{ age: number; houses: number[] }>;
  matrix_cite: Record<string, unknown>;
  semantics_cite: Record<string, unknown>;
  months: { rows: Array<{ house: number; month: string }>; cite: Cite; needs_review: boolean };
  coverage_note: string;
  needs_review: boolean;
}
export interface CycleRow {
  planet: Planet;
  years: number;
  parts: Array<{ part: "beginning" | "middle" | "last"; ruler: Planet; months: number }>;
  cite: Cite;
  needs_review: boolean;
}
export interface DeliveryRow {
  house: number;
  method: string | null;
  no_remedy: boolean;
  cite: Cite;
  needs_review: boolean;
}
export interface RemedyDeliveryData {
  rows: DeliveryRow[];
  one_at_a_time: {
    rule: string;
    duration_days: number[];
    gap: string;
    cite: Cite;
    needs_review: boolean;
  };
}
export type Clause =
  | { in: { planets: Planet[]; houses: number[] } }
  | { together: [Planet, Planet] }
  | { empty: number[] }
  | { alone: true };
export interface EntryCondition {
  when: Clause[] | null;
  effect: string;
  tone: "benefic" | "malefic" | "neutral";
  needs_review: boolean;
}
export interface PlanetHouseEntry {
  id: string;
  planet: Planet;
  house: number;
  status: "done" | "todo";
  theme: string | null;
  conditions: EntryCondition[];
  remedies: Array<{
    text: string;
    delivery: string | null;
    action?: string | null;
    item?: string | null;
    venue?: string | null;
    duration?: string | null;
  }>;
  note?: string;
  cite: Cite;
  needs_review: boolean;
}
export interface FriendshipTable {
  id: string;
  caption: string;
  matrix: Record<string, Record<string, string>>;
  cite: Cite;
  needs_review: boolean;
}

export const pakkaGhar = pakkaGharJson.rows as unknown as PakkaGharRow[];
export const aspectRows = aspectsJson.rows as unknown as AspectRow[];
export const dormantData = dormantJson as unknown as DormantData;
export const rinData = rinJson as unknown as RinData;
export const masnuiData = masnuiJson as unknown as MasnuiData;
export const varshphalData = varshphalJson as unknown as VarshphalData;
export const cycle35 = cycle35Json.rows as unknown as CycleRow[];
export const remedyDelivery = remedyDeliveryJson as unknown as RemedyDeliveryData;
const perPlanetRows = ([moonJson, marsJson, mercuryJson, jupiterJson, venusJson, saturnJson, rahuJson, ketuJson] as unknown as Array<{ rows: unknown[] }>).flatMap(
  (j) => j.rows,
) as unknown as PlanetHouseEntry[];
const overridden = new Set(perPlanetRows.map((e) => e.id));
export const planetHouseEntries = [
  ...(planetHouseJson.rows as unknown as PlanetHouseEntry[]).filter((e) => !overridden.has(e.id)),
  ...perPlanetRows,
];
export const friendshipTables = friendshipJson.tables as unknown as FriendshipTable[];

/** Short, citation-bearing summary of table coverage (used by tests and the report). */
export function dataCoverage() {
  const count = (rows: Array<{ needs_review?: boolean }>) => ({
    rows: rows.length,
    needs_review: rows.filter((r) => r.needs_review).length,
  });
  return {
    pakka_ghar: count(pakkaGhar),
    aspects: count(aspectRows),
    dormant_awakeners: count(dormantData.awakeners),
    self_awakening: count(dormantData.self_awakening),
    rin: count(rinData.rows),
    masnui: count(masnuiData.rows),
    varshphal_matrix: { rows: varshphalData.rows.length, needs_review: varshphalData.needs_review ? varshphalData.rows.length : 0 },
    cycle35: count(cycle35),
    remedy_delivery: count(remedyDelivery.rows),
    friendship: count(friendshipTables),
    planet_house: {
      total: planetHouseEntries.length,
      done: planetHouseEntries.filter((e) => e.status === "done").length,
      todo: planetHouseEntries.filter((e) => e.status === "todo").length,
    },
  };
}
