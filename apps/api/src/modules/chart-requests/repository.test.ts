import { beforeEach, describe, expect, it } from "vitest";

import { resetDatabaseClient } from "../../db/client";
import { ChartRequestsRepository } from "./repository";

describe("ChartRequestsRepository", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("persists chart request inputs with queued status", async () => {
    const repository = new ChartRequestsRepository();

    const chartRequest = await repository.createChartRequest({
      workspaceId: "ws_1",
      clientId: "cli_1",
      birthRecordId: "br_1",
      astrologySystem: "vedic",
      requestedOutputs: ["birthChart", "transits"],
    });

    expect(chartRequest.workspaceId).toBe("ws_1");
    expect(chartRequest.status).toBe("queued");
    expect(chartRequest.requestedOutputs).toBe('["birthChart","transits"]');
  });

  it("finds a queued chart request by id", async () => {
    const repository = new ChartRequestsRepository();

    const chartRequest = await repository.createChartRequest({
      workspaceId: "ws_1",
      clientId: "cli_1",
      birthRecordId: "br_1",
      astrologySystem: "vedic",
      requestedOutputs: ["birthChart"],
    });

    await expect(repository.findChartRequest(chartRequest.id)).resolves.toMatchObject({
      id: chartRequest.id,
      status: "queued",
    });
  });
});
