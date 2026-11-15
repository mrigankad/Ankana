import { beforeEach, describe, expect, it } from "vitest";

import { buildApp } from "../../app";
import { resetDatabaseClient } from "../../db/client";

describe("dashboard endpoints", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("summarizes workspace counts including sade sati clients", async () => {
    const app = buildApp();

    const client = await app.inject({
      method: "POST",
      url: "/api/v1/clients",
      payload: { workspaceId: "ws_1", fullName: "Dashboard Client" },
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

    const summary = await app.inject({
      method: "GET",
      url: "/api/v1/dashboard/summary",
    });

    expect(summary.statusCode).toBe(200);
    const body = summary.json();
    expect(body.clients).toBe(1);
    expect(body.chartsCompleted).toBe(1);
    expect(body.sadeSatiClients).toBeGreaterThanOrEqual(0);
    expect(body.sadeSatiClients).toBeLessThanOrEqual(1);
    expect(body.reportsRendered).toBe(0);
  });

  it("serves today's panchang with upcoming transit events", async () => {
    const app = buildApp();

    const response = await app.inject({
      method: "GET",
      url: "/api/v1/panchang/today?tz=Asia/Kolkata",
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.panchang.tithi.name).toBeTruthy();
    expect(body.panchang.moonNakshatra.name).toBeTruthy();
    expect(body.panchang.vara.name).toBeTruthy();
    expect(Array.isArray(body.upcomingEvents)).toBe(true);
    expect(body.upcomingEvents.length).toBeGreaterThan(0);
    expect(body.upcomingEvents[0]).toHaveProperty("detail");
  });
});
