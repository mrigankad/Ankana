import { describe, expect, it } from "vitest";

import { StaticLocationProvider } from "./provider";
import { LocationResolutionService } from "./service";

describe("LocationResolutionService", () => {
  it("returns ranked normalized location matches", async () => {
    const service = new LocationResolutionService(new StaticLocationProvider());

    const results = await service.resolveLocation({
      query: "Banaras, UP, India",
      preferredCountryCode: "IN",
    });

    expect(results[0]?.displayName).toBe("Varanasi, Uttar Pradesh, India");
    expect(results[0]?.timezoneName).toBe("Asia/Kolkata");
  });
});
