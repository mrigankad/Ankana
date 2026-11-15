import type { LocationSearchResult } from "@astro/shared-types";

import type { LocationProvider } from "./types";

const LOCATION_FIXTURES: LocationSearchResult[] = [
  {
    providerPlaceId: "geo_varanasi_in",
    displayName: "Varanasi, Uttar Pradesh, India",
    latitude: 25.3176,
    longitude: 82.9739,
    timezoneName: "Asia/Kolkata",
    confidence: "high",
    countryCode: "IN",
  },
  {
    providerPlaceId: "geo_delhi_in",
    displayName: "Delhi, India",
    latitude: 28.6139,
    longitude: 77.209,
    timezoneName: "Asia/Kolkata",
    confidence: "high",
    countryCode: "IN",
  },
];

const QUERY_ALIASES = new Map<string, string>([
  ["banaras", "varanasi"],
  ["benares", "varanasi"],
  ["kashi", "varanasi"],
  ["up", "uttar pradesh"],
]);

function normalizeQuery(query: string): string {
  return query
    .trim()
    .toLowerCase()
    .split(",")
    .flatMap((part) => part.trim().split(/\s+/))
    .map((token) => QUERY_ALIASES.get(token) ?? token)
    .join(" ");
}

export class StaticLocationProvider implements LocationProvider {
  async search(
    query: string,
    preferredCountryCode?: string,
  ): Promise<LocationSearchResult[]> {
    const normalizedQuery = normalizeQuery(query);

    return LOCATION_FIXTURES.filter((location) => {
      const matchesCountry =
        !preferredCountryCode || location.countryCode === preferredCountryCode;
      const haystack = `${location.displayName.toLowerCase()} ${location.countryCode?.toLowerCase() ?? ""}`;

      return matchesCountry && normalizedQuery.split(" ").every((token) => haystack.includes(token));
    });
  }
}

export { normalizeQuery };
