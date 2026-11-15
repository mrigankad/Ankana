import type { FastifyInstance } from "fastify";

import { NominatimLocationProvider } from "./nominatim-provider";
import { StaticLocationProvider } from "./provider";
import { LocationResolutionService } from "./service";
import type { LocationProvider } from "./types";

/** Live geocoding first; offline fixture fallback keeps dev and CI working. */
class FallbackLocationProvider implements LocationProvider {
  constructor(
    private readonly primary: LocationProvider,
    private readonly fallback: LocationProvider,
  ) {}

  async search(query: string, preferredCountryCode?: string) {
    try {
      const results = await this.primary.search(query, preferredCountryCode);
      if (results.length > 0) {
        return results;
      }
    } catch {
      // Network or provider failure: fall through to the offline provider.
    }
    return this.fallback.search(query, preferredCountryCode);
  }
}

export async function registerLocationRoutes(app: FastifyInstance): Promise<void> {
  const provider =
    process.env.LOCATION_PROVIDER === "static"
      ? new StaticLocationProvider()
      : new FallbackLocationProvider(
          new NominatimLocationProvider(),
          new StaticLocationProvider(),
        );
  const service = new LocationResolutionService(provider);

  app.get("/api/v1/locations/search", async (request, reply) => {
    const { q, preferredCountryCode } = request.query as {
      q?: string;
      preferredCountryCode?: string;
    };

    if (!q) {
      return reply.code(400).send({
        error: {
          code: "location_query_missing",
          message: "A location search query is required.",
        },
      });
    }

    const results = await service.searchLocations(q, preferredCountryCode);
    return reply.send({ results });
  });
}
