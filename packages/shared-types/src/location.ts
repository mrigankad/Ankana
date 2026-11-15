import { z } from "zod";

export const locationSearchResultSchema = z.object({
  providerPlaceId: z.string().min(1),
  displayName: z.string().min(1),
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
  timezoneName: z.string().min(1),
  confidence: z.enum(["low", "medium", "high"]),
  countryCode: z.string().length(2).optional(),
});

export const resolveLocationInputSchema = z.object({
  query: z.string().min(1),
  preferredCountryCode: z.string().length(2).optional(),
});

export type LocationSearchResult = z.infer<typeof locationSearchResultSchema>;
export type ResolveLocationInput = z.infer<typeof resolveLocationInputSchema>;
