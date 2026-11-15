import { describe, expect, it, beforeEach } from "vitest";

import { resetDatabaseClient } from "../../db/client";
import { ClientsRepository } from "./repository";

describe("ClientsRepository", () => {
  beforeEach(async () => {
    await resetDatabaseClient();
  });

  it("creates a client record", async () => {
    const repository = new ClientsRepository();

    const client = await repository.createClient({
      workspaceId: "ws_1",
      fullName: "Jane Doe",
    });

    expect(client.id).toBeTruthy();
    expect(client.fullName).toBe("Jane Doe");
  });

  it("persists original location query and resolved coordinates", async () => {
    const repository = new ClientsRepository();

    const client = await repository.createClient({
      workspaceId: "ws_1",
      fullName: "Test Client",
    });

    const birthRecord = await repository.createBirthRecord({
      clientId: client.id,
      birthDate: "1990-01-01",
      birthTime: "10:30",
      timezoneName: "Asia/Kolkata",
      placeLabel: "Varanasi, Uttar Pradesh, India",
      locationQueryText: "Banaras, India",
      canonicalLocationName: "Varanasi, Uttar Pradesh, India",
      latitude: 25.3176,
      longitude: 82.9739,
      providerPlaceId: "geo_123",
    });

    expect(birthRecord.locationQueryText).toBe("Banaras, India");
    expect(birthRecord.latitude).toBe(25.3176);
    expect(birthRecord.longitude).toBe(82.9739);
  });
});
