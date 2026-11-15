import {
  computeVedicChartArtifact,
  type BirthDataInput,
  type VedicChartArtifact,
} from "@astro/astrology-core";

export type FixtureId = "raiganj-2003" | "varanasi-1990" | "newyork-1985";

export interface EvalFixture {
  id: FixtureId;
  label: string;
  input: BirthDataInput;
  artifact: VedicChartArtifact;
}

const INPUTS: Record<FixtureId, BirthDataInput> = {
  "raiganj-2003": {
    birthDate: "2003-08-29",
    birthTime: "12:22",
    timezoneName: "Asia/Kolkata",
    latitude: 25.6167,
    longitude: 88.1233,
    placeLabel: "Raiganj, Uttar Dinajpur, West Bengal, India",
  },
  "varanasi-1990": {
    birthDate: "1990-01-01",
    birthTime: "10:30",
    timezoneName: "Asia/Kolkata",
    latitude: 25.3176,
    longitude: 82.9739,
    placeLabel: "Varanasi, India",
  },
  "newyork-1985": {
    birthDate: "1985-06-15",
    birthTime: "23:45",
    timezoneName: "America/New_York",
    latitude: 40.7128,
    longitude: -74.006,
    placeLabel: "New York, USA",
  },
};

const LABELS: Record<FixtureId, string> = {
  "raiganj-2003": "Raiganj 2003 (Scorpio lagna)",
  "varanasi-1990": "Varanasi 1990",
  "newyork-1985": "New York 1985",
};

export const EVAL_FIXTURES: EvalFixture[] = (
  Object.keys(INPUTS) as FixtureId[]
).map((id) => ({
  id,
  label: LABELS[id],
  input: INPUTS[id],
  artifact: computeVedicChartArtifact(INPUTS[id]),
}));

export function fixtureById(id: FixtureId): EvalFixture {
  const found = EVAL_FIXTURES.find((f) => f.id === id);
  if (!found) throw new Error(`Unknown eval fixture: ${id}`);
  return found;
}
