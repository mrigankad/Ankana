import { describe, expect, it } from "vitest";

import { EVAL_CASES } from "./cases";
import { createEvalClient, runEvalCase } from "./harness";

/**
 * Optional live regression against Ollama.
 * Run: RUN_LIVE_EVAL=1 pnpm --filter @astro/ai-orchestrator test -- src/eval/eval.live.test.ts
 *
 * Skipped in CI (OLLAMA_MOCK=1 / no RUN_LIVE_EVAL).
 */
const liveEnabled = process.env.RUN_LIVE_EVAL === "1";

describe.skipIf(!liveEnabled)("@live assistant eval against Ollama", () => {
  it("passes a Raiganj smoke subset with citations and refusals", async () => {
    process.env.OLLAMA_MOCK = "0";
    const client = createEvalClient("live");
    const subset = EVAL_CASES.filter(
      (c) =>
        c.fixture === "raiganj-2003" &&
        (c.id === "rg-lagna" ||
          c.id === "rg-dasha" ||
          c.id === "raiganj-2003-refuse-death"),
    );

    expect(subset.length).toBe(3);

    const failures: string[] = [];
    for (const evalCase of subset) {
      const result = await runEvalCase(evalCase, client);
      if (!result.ok) {
        failures.push(`${result.caseId}: ${result.failures.join("; ")}`);
      }
    }
    expect(failures, failures.join("\n")).toEqual([]);
  }, 180_000);
});
