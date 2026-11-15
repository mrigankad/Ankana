import { beforeEach, describe, expect, it } from "vitest";

import { buildApp } from "../../app";
import { resetDatabaseClient } from "../../db/client";

describe("clients workspace endpoints", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("lists clients with birth record counts and latest chart status", async () => {
    const app = buildApp();

    const created = await app.inject({
      method: "POST",
      url: "/api/v1/clients",
      payload: { workspaceId: "ws_1", fullName: "List Client" },
    });
    const clientId = created.json().id as string;

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
    const birthRecordId = birth.json().id as string;

    await app.inject({
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

    const list = await app.inject({ method: "GET", url: "/api/v1/clients" });
    expect(list.statusCode).toBe(200);
    const { clients } = list.json();
    const summary = clients.find((c: { id: string }) => c.id === clientId);
    expect(summary.fullName).toBe("List Client");
    expect(summary.birthRecordCount).toBe(1);
    expect(summary.latestChartRequest.status).toBe("completed");
  });

  it("returns client detail with birth records and chart history", async () => {
    const app = buildApp();

    const created = await app.inject({
      method: "POST",
      url: "/api/v1/clients",
      payload: { workspaceId: "ws_1", fullName: "Detail Client" },
    });
    const clientId = created.json().id as string;

    const detail = await app.inject({
      method: "GET",
      url: `/api/v1/clients/${clientId}`,
    });
    expect(detail.statusCode).toBe(200);
    expect(detail.json().fullName).toBe("Detail Client");
    expect(Array.isArray(detail.json().birthRecords)).toBe(true);
    expect(Array.isArray(detail.json().chartRequests)).toBe(true);
  });

  it("404s for a missing client", async () => {
    const app = buildApp();
    const detail = await app.inject({
      method: "GET",
      url: "/api/v1/clients/cli_missing",
    });
    expect(detail.statusCode).toBe(404);
  });
});

describe("client summary enrichment", () => {
  it("carries lagna sign and current mahadasha from the latest artifact", async () => {
    const { buildApp } = await import("../../app");
    const { resetDatabaseClient } = await import("../../db/client");
    await resetDatabaseClient();
    const app = buildApp();

    const created = await app.inject({
      method: "POST",
      url: "/api/v1/clients",
      payload: { workspaceId: "ws_1", fullName: "Enriched Client" },
    });
    const clientId = created.json().id as string;
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
    await app.inject({
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

    const list = await app.inject({ method: "GET", url: "/api/v1/clients" });
    const summary = list
      .json()
      .clients.find((c: { id: string }) => c.id === clientId);
    expect(summary.lagnaSign).toBe("Aquarius");
    expect(summary.currentMahadasha).toBe("saturn");
  });
});
