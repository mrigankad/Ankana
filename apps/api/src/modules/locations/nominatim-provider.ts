import type { LocationSearchResult } from "@astro/shared-types";
import tzLookup from "tz-lookup";

import type { LocationProvider } from "./types";

interface NominatimPlace {
  place_id: number;
  display_name: string;
  lat: string;
  lon: string;
  importance?: number;
  address?: { country_code?: string };
}

const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";

/**
 * OpenStreetMap Nominatim geocoder. Free, no API key; usage policy
 * requires a descriptive User-Agent and at most one request per second,
 * which interactive practitioner searches stay well under.
 */
export class NominatimLocationProvider implements LocationProvider {
  constructor(private readonly fetchImpl: typeof fetch = fetch) {}

  async search(
    query: string,
    preferredCountryCode?: string,
  ): Promise<LocationSearchResult[]> {
    const params = new URLSearchParams({
      q: query,
      format: "jsonv2",
      addressdetails: "1",
      limit: "6",
    });
    if (preferredCountryCode) {
      params.set("countrycodes", preferredCountryCode.toLowerCase());
    }

    const response = await this.fetchImpl(`${NOMINATIM_URL}?${params}`, {
      headers: {
        "User-Agent": "Nakshatra-Astrology-Platform/0.1 (practitioner geocoding)",
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Nominatim search failed with status ${response.status}`);
    }

    const places = (await response.json()) as NominatimPlace[];

    return places.map((place) => {
      const latitude = Number(place.lat);
      const longitude = Number(place.lon);

      return {
        providerPlaceId: `osm_${place.place_id}`,
        displayName: place.display_name,
        latitude,
        longitude,
        timezoneName: tzLookup(latitude, longitude),
        confidence:
          (place.importance ?? 0) > 0.5
            ? "high"
            : (place.importance ?? 0) > 0.3
              ? "medium"
              : "low",
        countryCode: place.address?.country_code?.toUpperCase(),
      };
    });
  }
}
