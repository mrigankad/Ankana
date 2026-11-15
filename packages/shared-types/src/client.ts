import { z } from "zod";

const isoDateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, {
  message: "birthDate must use YYYY-MM-DD format",
});

const timeSchema = z.string().regex(/^\d{2}:\d{2}$/, {
  message: "birthTime must use HH:MM format",
});

export const createClientInputSchema = z.object({
  workspaceId: z.string().min(1),
  fullName: z.string().min(1),
  preferredName: z.string().min(1).optional(),
  email: z.email().optional(),
  phone: z.string().min(1).optional(),
  timezone: z.string().min(1).optional(),
});

export const createBirthRecordInputSchema = z
  .object({
    clientId: z.string().min(1).optional(),
    birthDate: isoDateSchema,
    birthTime: timeSchema,
    timezoneName: z.string().min(1),
    placeLabel: z.string().min(1),
    locationQueryText: z.string().min(1).optional(),
    canonicalLocationName: z.string().min(1).optional(),
    latitude: z.number().min(-90).max(90).optional(),
    longitude: z.number().min(-180).max(180).optional(),
    providerPlaceId: z.string().min(1).optional(),
    geocodeProvider: z.string().min(1).optional(),
    geocodeConfidence: z.enum(["low", "medium", "high"]).optional(),
  })
  .refine(
    (value) =>
      (typeof value.latitude === "number" &&
        typeof value.longitude === "number") ||
      typeof value.providerPlaceId === "string",
    {
      message: "Coordinates or providerPlaceId is required",
      path: ["providerPlaceId"],
    },
  );

export type CreateClientInput = z.infer<typeof createClientInputSchema>;
export type CreateBirthRecordInput = z.infer<typeof createBirthRecordInputSchema>;
