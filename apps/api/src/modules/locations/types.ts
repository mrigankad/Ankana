import type { LocationSearchResult } from "@astro/shared-types";

export interface ResolveLocationOptions {
  query: string;
  preferredCountryCode?: string;
}

export interface LocationProvider {
  search(
    query: string,
    preferredCountryCode?: string,
  ): Promise<LocationSearchResult[]>;
}
