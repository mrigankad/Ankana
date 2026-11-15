import { describe, expect, it } from "vitest";

import { api } from "./client";

describe("api layer (fixtures fallback)", () => {
  it("falls back to fixtures when the backend is unreachable", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:9";
    const rows = await api.listClients();
    expect(rows[0]?.name).toBe("Ananya Sharma");
  });

  it("returns the computed Ananya chart with Pisces lagna", async () => {
    const bundle = await api.getChart("chart-ananya-sharma");
    expect(bundle.artifact.ascendant.signName).toBe("Pisces");
  });
});
