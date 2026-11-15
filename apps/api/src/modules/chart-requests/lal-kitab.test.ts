import { beforeEach, describe, expect, it } from "vitest";

import { buildApp } from "../../app";
import { resetDatabaseClient } from "../../db/client";

describe("lal-kitab endpoint", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("serves the Lal Kitab report for a computed chart", async () => {
    const app = buildApp();

    const clientResponse = await app.inject({
      method: "POST",
      url: "/api/v1/clients",
      payload: { workspaceId: "ws_1", fullName: "Ananya Sharma" },
    });
    const clientId = clientResponse.json().id as string;

    const birthResponse = await app.inject({
      method: "POST",
      url: `/api/v1/clients/${clientId}/birth-records`,
      payload: {
        birthDate: "1995-03-15",
        birthTime: "06:42",
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

    const response = await app.inject({
      method: "GET",
      url: `/api/v1/charts/jobs/${jobId}/lal-kitab?age=33`,
    });
    expect(response.statusCode).toBe(200);
    const { lalKitab } = response.json();
    expect(lalKitab.origin).toBe("lagna_h1");
    expect(lalKitab.chart.planetHouse.sun).toBe(1);
    expect(lalKitab.varshphal.age).toBe(33);
    expect(lalKitab.varshphal.row).toEqual([12, 2, 6, 10, 8, 3, 9, 1, 5, 7, 4, 11]);
    expect(lalKitab.remedies.oneAtATime.durationDays).toEqual([40, 43]);

    const bad = await app.inject({
      method: "GET",
      url: `/api/v1/charts/jobs/${jobId}/lal-kitab?age=101`,
    });
    expect(bad.statusCode).toBe(400);
    const badOrigin = await app.inject({
      method: "GET",
      url: `/api/v1/charts/jobs/${jobId}/lal-kitab?origin=bogus`,
    });
    expect(badOrigin.statusCode).toBe(400);
  });

  it("returns 404 for a missing artifact", async () => {
    const app = buildApp();
    const missing = await app.inject({
      method: "GET",
      url: "/api/v1/charts/jobs/job_missing/lal-kitab",
    });
    expect(missing.statusCode).toBe(404);
  });
});
