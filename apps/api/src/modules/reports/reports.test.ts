import { readFileSync } from "node:fs";

import { beforeEach, describe, expect, it } from "vitest";

import { buildApp } from "../../app";
import { resetDatabaseClient } from "../../db/client";

process.env.REPORT_RENDERER = "stub";

async function createChartJob(app: ReturnType<typeof buildApp>) {
  const client = await app.inject({
    method: "POST",
    url: "/api/v1/clients",
    payload: { workspaceId: "ws_1", fullName: "Report Client" },
  });
  const birth = await app.inject({
    method: "POST",
    url: `/api/v1/clients/${client.json().id}/birth-records`,
    payload: {
      birthDate: "1990-01-01",
      birthTime: "10:30",
      timezoneName: "Asia/Kolkata",
      placeLabel: "Varanasi, India",
      latitude: 25.3176,
      longitude: 82.9739,
    },
  });
  const generate = await app.inject({
    method: "POST",
    url: "/api/v1/charts/generate",
    payload: {
      workspaceId: "ws_1",
      clientId: client.json().id,
      birthRecordId: birth.json().id,
      astrologySystem: "vedic",
      requestedOutputs: ["birthChart"],
    },
  });
  return generate.json().jobId as string;
}

describe("report endpoints (stub renderer)", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("generates and serves a PDF report", async () => {
    const app = buildApp();
    const jobId = await createChartJob(app);

    const created = await app.inject({
      method: "POST",
      url: `/api/v1/reports/${jobId}`,
    });
    expect(created.statusCode).toBe(201);
    expect(created.json().reportUrl).toBe(`/api/v1/reports/${jobId}`);

    const served = await app.inject({
      method: "GET",
      url: `/api/v1/reports/${jobId}`,
    });
    expect(served.statusCode).toBe(200);
    expect(served.headers["content-type"]).toBe("application/pdf");
    expect(served.body.startsWith("%PDF")).toBe(true);
  });

  it("404s for unknown jobs and ungenerated reports", async () => {
    const app = buildApp();

    const missing = await app.inject({
      method: "POST",
      url: "/api/v1/reports/job_missing",
    });
    expect(missing.statusCode).toBe(404);

    const notGenerated = await app.inject({
      method: "GET",
      url: "/api/v1/reports/job_never_rendered",
    });
    expect(notGenerated.statusCode).toBe(404);
  });
});
