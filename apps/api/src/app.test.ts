import { beforeEach, describe, expect, it } from "vitest";

import { resetDatabaseClient } from "./db/client";
import { buildApp } from "./app";

describe("API app", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("creates a chart request after a birth record exists", async () => {
    const app = buildApp();

    const clientResponse = await app.inject({
      method: "POST",
      url: "/api/v1/clients",
      payload: {
        workspaceId: "ws_1",
        fullName: "Test Client",
      },
    });

    const client = clientResponse.json() as { id: string };

    const birthRecordResponse = await app.inject({
      method: "POST",
      url: `/api/v1/clients/${client.id}/birth-records`,
      payload: {
        birthDate: "1990-01-01",
        birthTime: "10:30",
        timezoneName: "Asia/Kolkata",
        placeLabel: "Varanasi, Uttar Pradesh, India",
        locationQueryText: "Banaras, India",
        canonicalLocationName: "Varanasi, Uttar Pradesh, India",
        latitude: 25.3176,
        longitude: 82.9739,
        providerPlaceId: "geo_varanasi_in",
      },
    });

    const birthRecord = birthRecordResponse.json() as { id: string };

    const response = await app.inject({
      method: "POST",
      url: "/api/v1/charts/generate",
      payload: {
        workspaceId: "ws_1",
        clientId: client.id,
        birthRecordId: birthRecord.id,
        astrologySystem: "vedic",
        requestedOutputs: ["birthChart"],
      },
    });

    expect(response.statusCode).toBe(202);
    expect(response.json()).toMatchObject({
      status: "completed",
    });
  });

  it("returns chart request status from the generated status URL", async () => {
    const app = buildApp();

    const response = await app.inject({
      method: "POST",
      url: "/api/v1/charts/generate",
      payload: {
        workspaceId: "ws_1",
        clientId: "cli_1",
        birthRecordId: "br_1",
        astrologySystem: "vedic",
        requestedOutputs: ["birthChart"],
      },
    });

    const chartRequest = response.json() as { jobId: string; statusUrl: string };
    const statusResponse = await app.inject({
      method: "GET",
      url: chartRequest.statusUrl,
    });

    expect(statusResponse.statusCode).toBe(200);
    expect(statusResponse.json()).toMatchObject({
      id: chartRequest.jobId,
      requestedOutputs: ["birthChart"],
      // Processed inline; a request without a stored birth record fails.
      status: "failed",
    });
  });

  it("returns not found for an unknown chart job", async () => {
    const app = buildApp();

    const response = await app.inject({
      method: "GET",
      url: "/api/v1/charts/jobs/job_missing",
    });

    expect(response.statusCode).toBe(404);
  });
});
