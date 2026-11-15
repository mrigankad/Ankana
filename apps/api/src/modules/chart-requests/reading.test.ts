import { beforeEach, describe, expect, it } from "vitest";

import { buildApp } from "../../app";
import { resetDatabaseClient } from "../../db/client";

async function createChartJob(app: ReturnType<typeof buildApp>) {
  const clientResponse = await app.inject({
    method: "POST",
    url: "/api/v1/clients",
    payload: { workspaceId: "ws_1", fullName: "Reading Client" },
  });
  const clientId = clientResponse.json().id as string;

  const birthResponse = await app.inject({
    method: "POST",
    url: `/api/v1/clients/${clientId}/birth-records`,
    payload: {
      birthDate: "2003-08-29",
      birthTime: "12:22",
      timezoneName: "Asia/Kolkata",
      placeLabel: "Raiganj, West Bengal",
      latitude: 25.6167,
      longitude: 88.1233,
    },
  });

  const generate = await app.inject({
    method: "POST",
    url: "/api/v1/charts/generate",
    payload: {
      workspaceId: "ws_1",
      clientId,
      birthRecordId: birthResponse.json().id as string,
      astrologySystem: "vedic",
      requestedOutputs: ["birthChart"],
    },
  });
  return generate.json().jobId as string;
}

describe("chart reading endpoint", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("returns a 7-section evidence-cited reading", async () => {
    const app = buildApp();
    const jobId = await createChartJob(app);

    const response = await app.inject({
      method: "GET",
      url: `/api/v1/charts/jobs/${jobId}/reading`,
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.jobId).toBe(jobId);
    expect(body.reading.sections).toHaveLength(7);
    const keys = body.reading.sections.map(
      (section: { key: string }) => section.key,
    );
    expect(keys).toEqual([
      "lagna",
      "planets",
      "houses",
      "yogas",
      "dasha",
      "vargas",
      "panchang",
    ]);
    const lagna = body.reading.sections[0].items[0];
    expect(lagna.text).toContain("Scorpio");
    expect(lagna.evidence.length).toBeGreaterThan(0);
    expect(body.reading.lifeStory).toBeTruthy();
    expect(Object.keys(body.reading.lifeStory.lenses).sort()).toEqual([
      "ageBands",
      "dashaChapters",
      "hybrid",
    ]);
    expect(body.reading.lifeStory.lenses.hybrid).toHaveLength(5);
  }, 60_000);

  it("404s for unknown jobs", async () => {
    const app = buildApp();
    const response = await app.inject({
      method: "GET",
      url: "/api/v1/charts/jobs/job_missing/reading",
    });
    expect(response.statusCode).toBe(404);
  });
});
