import type { LocationSearchResult } from "@astro/shared-types";

import type { LocationProvider, ResolveLocationOptions } from "./types";

export class LocationResolutionService {
  constructor(private readonly provider: LocationProvider) {}

  async searchLocations(
    query: string,
    preferredCountryCode?: string,
  ): Promise<LocationSearchResult[]> {
    return this.provider.search(query, preferredCountryCode);
  }

  async resolveLocation(
    input: ResolveLocationOptions,
  ): Promise<LocationSearchResult[]> {
    return this.searchLocations(input.query, input.preferredCountryCode);
  }
}
