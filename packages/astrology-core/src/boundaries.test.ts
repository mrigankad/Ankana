import { describe, expect, it } from "vitest";

import { boundaryWarnings } from "./boundaries";

describe("boundaryWarnings", () => {
  it("flags a body exactly on a sign cusp", () => {
    const warnings = boundaryWarnings({ sun: 30 }, 100);
    expect(warnings.some((w) => w.body === "sun" && w.kind === "sign")).toBe(
      true,
    );
  });

  it("ignores bodies well inside a sign", () => {
    const warnings = boundaryWarnings({ sun: 15 }, 100);
    expect(warnings.some((w) => w.body === "sun" && w.kind === "sign")).toBe(
      false,
    );
  });

  it("includes the ascendant when near a boundary", () => {
    const warnings = boundaryWarnings({}, 0.05);
    expect(
      warnings.some((w) => w.body === "ascendant" && w.kind === "sign"),
    ).toBe(true);
  });
});
