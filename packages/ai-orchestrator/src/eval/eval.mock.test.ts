import { describe, expect, it } from "vitest";

import { EVAL_CASES } from "./cases";
import { EVAL_FIXTURES } from "./fixtures";
import { createEvalClient, runEvalCase } from "./harness";

describe("assistant eval suite (mock)", () => {
  it("covers Raiganj plus two other fixtures with 30+ cases", () => {
    expect(EVAL_FIXTURES.map((f) => f.id).sort()).toEqual([
      "newyork-1985",
      "raiganj-2003",
      "varanasi-1990",
    ]);
    expect(EVAL_CASES.length).toBeGreaterThanOrEqual(30);
    expect(EVAL_CASES.filter((c) => c.expect === "refuse").length).toBeGreaterThanOrEqual(
      5,
    );
    expect(EVAL_CASES.filter((c) => c.expect === "cited").length).toBeGreaterThanOrEqual(
      20,
    );
  });

  it("passes every golden case under the deterministic eval mock", async () => {
    const client = createEvalClient("mock");
    const failures: string[] = [];

    for (const evalCase of EVAL_CASES) {
      const result = await runEvalCase(evalCase, client);
      if (!result.ok) {
        failures.push(
          `${result.caseId}: ${result.failures.join("; ")} | answer=${result.answer.answer.slice(0, 160)}`,
        );
      }
    }

    expect(failures, failures.join("\n")).toEqual([]);
  }, 120_000);
});
