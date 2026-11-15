import { beforeEach, describe, expect, it } from "vitest";

import { buildApp } from "../../app";
import { resetDatabaseClient } from "../../db/client";

process.env.OLLAMA_MOCK = "1";

describe("audit trail", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("records events across the chart lifecycle", async () => {
    const app = buildApp();

    const client = await app.inject({
      method: "POST",
      url: "/api/v1/clients",
      payload: { workspaceId: "ws_1", fullName: "Audit Client" },
    });
    const clientId = client.json().id as string;

    const birth = await app.inject({
      method: "POST",
      url: `/api/v1/clients/${clientId}/birth-records`,
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
        clientId,
        birthRecordId: birth.json().id,
        astrologySystem: "vedic",
        requestedOutputs: ["birthChart"],
      },
    });
    const jobId = generate.json().jobId as string;

    await app.inject({
      method: "POST",
      url: `/api/v1/charts/jobs/${jobId}/assistant`,
      payload: { question: "What is my lagna?" },
    });

    // Audit writes are fire-and-forget; give them a beat to land.
    await new Promise((resolve) => setTimeout(resolve, 150));

    const audit = await app.inject({ method: "GET", url: "/api/v1/audit-events" });
    expect(audit.statusCode).toBe(200);
    const actions = audit.json().events.map((e: { action: string }) => e.action);

    expect(actions).toContain("client.created");
    expect(actions).toContain("birth_record.created");
    expect(actions).toContain("chart.generated");
    expect(actions).toContain("assistant.asked");
  });

  it("rate limits the assistant per IP", async () => {
    const app = buildApp();

    let limited = false;
    for (let i = 0; i < 12; i += 1) {
      const response = await app.inject({
        method: "POST",
        url: "/api/v1/charts/jobs/job_x/assistant",
        payload: { question: "spam question" },
      });
      if (response.statusCode === 429) {
        limited = true;
        break;
      }
    }
    expect(limited).toBe(true);
  });
});
