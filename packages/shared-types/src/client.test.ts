import { describe, expect, it } from "vitest";

import { createBirthRecordInputSchema, createClientInputSchema } from "./client";

describe("createClientInputSchema", () => {
  it("accepts a minimal client payload", () => {
    const result = createClientInputSchema.safeParse({
      workspaceId: "ws_123",
      fullName: "Jane Doe",
    });

    expect(result.success).toBe(true);
  });
});

describe("createBirthRecordInputSchema", () => {
  it("requires either coordinates or a resolved provider place id", () => {
    const result = createBirthRecordInputSchema.safeParse({
      birthDate: "1990-01-01",
      birthTime: "10:30",
      timezoneName: "Asia/Kolkata",
      placeLabel: "Varanasi, India",
    });

    expect(result.success).toBe(false);
  });

  it("accepts a resolved provider place id without explicit coordinates", () => {
    const result = createBirthRecordInputSchema.safeParse({
      birthDate: "1990-01-01",
      birthTime: "10:30",
      timezoneName: "Asia/Kolkata",
      placeLabel: "Varanasi, India",
      providerPlaceId: "geo_123",
    });

    expect(result.success).toBe(true);
  });

  it("accepts direct coordinates", () => {
    const result = createBirthRecordInputSchema.safeParse({
      birthDate: "1990-01-01",
      birthTime: "10:30",
      timezoneName: "Asia/Kolkata",
      placeLabel: "Varanasi, India",
      latitude: 25.3176,
      longitude: 82.9739,
    });

    expect(result.success).toBe(true);
  });
});
