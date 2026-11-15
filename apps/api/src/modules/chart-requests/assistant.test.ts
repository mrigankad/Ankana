import { beforeEach, describe, expect, it } from "vitest";

import { buildApp } from "../../app";
import { resetDatabaseClient } from "../../db/client";

process.env.OLLAMA_MOCK = "1";

async function createChartJob(app: ReturnType<typeof buildApp>) {
  const client = await app.inject({
    method: "POST",
    url: "/api/v1/clients",
    payload: { workspaceId: "ws_1", fullName: "Assistant Client" },
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
      birthRecordId: birth.json().id as string,
      astrologySystem: "vedic",
      requestedOutputs: ["birthChart"],
    },
  });
  return generate.json().jobId as string;
}

describe("assistant endpoint (mock LLM)", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("returns a grounded answer with citations", async () => {
    const app = buildApp();
    const jobId = await createChartJob(app);

    const response = await app.inject({
      method: "POST",
      url: `/api/v1/charts/jobs/${jobId}/assistant`,
      payload: { question: "What is happening in my life right now?" },
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.answer).toContain("[1]");
    expect(body.citations.length).toBeGreaterThan(0);
    expect(body.citations[0].fact.length).toBeGreaterThan(0);
  });

  it("accepts conversation history for follow-ups", async () => {
    const app = buildApp();
    const jobId = await createChartJob(app);

    const response = await app.inject({
      method: "POST",
      url: `/api/v1/charts/jobs/${jobId}/assistant`,
      payload: {
        question: "What about career from that?",
        history: [
          { role: "user", content: "What does my lagna say?" },
          {
            role: "assistant",
            content: "Your lagna colours temperament [1].",
          },
        ],
      },
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().answer).toContain("[1]");
  });

  it("streams status and done events when stream=1", async () => {
    const app = buildApp();
    const jobId = await createChartJob(app);

    const response = await app.inject({
      method: "POST",
      url: `/api/v1/charts/jobs/${jobId}/assistant?stream=1`,
      headers: { accept: "text/event-stream" },
      payload: { question: "What is happening in my life right now?" },
    });

    expect(response.statusCode).toBe(200);
    expect(response.headers["content-type"]).toContain("text/event-stream");
    const body = response.body;
    expect(body).toContain("event: status");
    expect(body).toContain("event: done");
    expect(body).toContain("[1]");
  });

  it("persists and clears the per-chart assistant thread", async () => {
    const app = buildApp();
    const jobId = await createChartJob(app);

    const ask = await app.inject({
      method: "POST",
      url: `/api/v1/charts/jobs/${jobId}/assistant`,
      payload: { question: "What is happening in my life right now?" },
    });
    expect(ask.statusCode).toBe(200);

    const thread = await app.inject({
      method: "GET",
      url: `/api/v1/charts/jobs/${jobId}/assistant/thread`,
    });
    expect(thread.statusCode).toBe(200);
    expect(thread.json().exchanges).toHaveLength(1);
    expect(thread.json().exchanges[0].question).toContain("happening");

    const cleared = await app.inject({
      method: "DELETE",
      url: `/api/v1/charts/jobs/${jobId}/assistant/thread`,
    });
    expect(cleared.statusCode).toBe(200);

    const empty = await app.inject({
      method: "GET",
      url: `/api/v1/charts/jobs/${jobId}/assistant/thread`,
    });
    expect(empty.json().exchanges).toHaveLength(0);
  });

  it("reports assistant health (mock mode in CI)", async () => {
    const app = buildApp();
    const response = await app.inject({
      method: "GET",
      url: "/api/v1/assistant/health",
    });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toMatchObject({
      status: "ok",
      mode: "mock",
      model: "mock",
    });
  });

  it("rejects empty questions and unknown jobs", async () => {
    const app = buildApp();
    const jobId = await createChartJob(app);

    const empty = await app.inject({
      method: "POST",
      url: `/api/v1/charts/jobs/${jobId}/assistant`,
      payload: { question: "" },
    });
    expect(empty.statusCode).toBe(400);

    const missing = await app.inject({
      method: "POST",
      url: "/api/v1/charts/jobs/job_missing/assistant",
      payload: { question: "Tell me about my chart" },
    });
    expect(missing.statusCode).toBe(404);
  });
});
