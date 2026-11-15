import { beforeEach, describe, expect, it } from "vitest";

import { buildApp } from "../../app";
import { resetDatabaseClient } from "../../db/client";

describe("transit endpoint", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("serves a transit snapshot and timeline for a computed chart", async () => {
    const app = buildApp();

    const clientResponse = await app.inject({
      method: "POST",
      url: "/api/v1/clients",
      payload: { workspaceId: "ws_1", fullName: "Transit Client" },
    });
    const clientId = clientResponse.json().id as string;

    const birthResponse = await app.inject({
      method: "POST",
      url: `/api/v1/clients/${clientId}/birth-records`,
      payload: {
        birthDate: "1990-01-01",
        birthTime: "10:30",
        timezoneName: "Asia/Kolkata",
        placeLabel: "Varanasi, Uttar Pradesh, India",
        latitude: 25.3176,
        longitude: 82.9739,
      },
    });
    const birthRecordId = birthResponse.json().id as string;

    const generateResponse = await app.inject({
      method: "POST",
      url: "/api/v1/charts/generate",
      payload: {
        workspaceId: "ws_1",
        clientId,
        birthRecordId,
        astrologySystem: "vedic",
        requestedOutputs: ["birthChart"],
      },
    });
    const jobId = generateResponse.json().jobId as string;

    const transitResponse = await app.inject({
      method: "GET",
      url: `/api/v1/charts/jobs/${jobId}/transits?date=2026-07-09&years=0.5`,
    });

    expect(transitResponse.statusCode).toBe(200);
    const { snapshot, timeline } = transitResponse.json();
    expect(snapshot.planets).toHaveLength(9);
    expect(snapshot.sadeSati).toHaveProperty("active");
    expect(Array.isArray(timeline)).toBe(true);
    expect(timeline.length).toBeGreaterThan(0);
  });

  it("returns 404 for a missing artifact and 400 for a bad date", async () => {
    const app = buildApp();

    const missing = await app.inject({
      method: "GET",
      url: "/api/v1/charts/jobs/job_missing/transits",
    });
    expect(missing.statusCode).toBe(404);
  });
});
