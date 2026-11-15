import { beforeEach, describe, expect, it } from "vitest";

import { buildApp } from "../../app";
import { resetDatabaseClient } from "../../db/client";

async function createClientWithBirthRecord(app: ReturnType<typeof buildApp>) {
  const clientResponse = await app.inject({
    method: "POST",
    url: "/api/v1/clients",
    payload: { workspaceId: "ws_1", fullName: "Artifact Test Client" },
  });
  expect(clientResponse.statusCode).toBe(201);
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
  expect(birthResponse.statusCode).toBe(201);

  return { clientId, birthRecordId: birthResponse.json().id as string };
}

describe("chart artifact pipeline", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("computes and serves a full Vedic artifact for a queued request", async () => {
    const app = buildApp();
    const { clientId, birthRecordId } = await createClientWithBirthRecord(app);

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

    expect(generateResponse.statusCode).toBe(202);
    const { jobId, status, artifactUrl } = generateResponse.json();
    expect(status).toBe("completed");

    const artifactResponse = await app.inject({ method: "GET", url: artifactUrl });
    expect(artifactResponse.statusCode).toBe(200);

    const { artifact } = artifactResponse.json();
    expect(artifact.calculationMetadata.utcDateTime).toBe("1990-01-01T05:00:00.000Z");
    expect(artifact.planets).toHaveLength(9);
    expect(artifact.houses).toHaveLength(12);
    expect(artifact.vimshottari.mahadashas).toHaveLength(9);
    expect(artifact.yogas.length).toBeGreaterThan(0);

    const statusResponse = await app.inject({
      method: "GET",
      url: `/api/v1/charts/jobs/${jobId}`,
    });
    expect(statusResponse.json().status).toBe("completed");
  });

  it("fails the request when the birth record does not exist", async () => {
    const app = buildApp();

    const generateResponse = await app.inject({
      method: "POST",
      url: "/api/v1/charts/generate",
      payload: {
        workspaceId: "ws_1",
        clientId: "cli_missing",
        birthRecordId: "br_missing",
        astrologySystem: "vedic",
        requestedOutputs: ["birthChart"],
      },
    });

    expect(generateResponse.statusCode).toBe(202);
    expect(generateResponse.json().status).toBe("failed");

    const artifactResponse = await app.inject({
      method: "GET",
      url: generateResponse.json().artifactUrl,
    });
    expect(artifactResponse.statusCode).toBe(409);
  });

  it("returns 404 for an unknown job artifact", async () => {
    const app = buildApp();
    const response = await app.inject({
      method: "GET",
      url: "/api/v1/charts/jobs/job_unknown/artifact",
    });
    expect(response.statusCode).toBe(404);
  });
});

describe("legacy artifact self-healing", () => {
  it("recomputes stored artifacts that predate strengthMetrics", async () => {
    const { getPrisma } = await import("../../db/prisma");
    const { resetDatabaseClient } = await import("../../db/client");
    await resetDatabaseClient();
    const app = buildApp();
    const { clientId, birthRecordId } = await createClientWithBirthRecord(app);

    const generate = await app.inject({
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
    const jobId = generate.json().jobId as string;

    // Strip the newer sections to simulate a legacy artifact.
    const prisma = getPrisma();
    const stored = await prisma.chartArtifact.findUnique({
      where: { chartRequestId: jobId },
    });
    const legacy = JSON.parse(stored!.artifactJson);
    delete legacy.strengthMetrics;
    delete legacy.yoginiDasha;
    await prisma.chartArtifact.update({
      where: { chartRequestId: jobId },
      data: { artifactJson: JSON.stringify(legacy) },
    });

    const response = await app.inject({
      method: "GET",
      url: `/api/v1/charts/jobs/${jobId}/artifact`,
    });
    expect(response.statusCode).toBe(200);
    const { artifact } = response.json();
    expect(artifact.strengthMetrics.shadbala).toHaveLength(7);
    expect(artifact.yoginiDasha.mahadashas.length).toBeGreaterThan(0);
  });
});
