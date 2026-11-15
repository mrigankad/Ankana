import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { VedicChartArtifact } from "@astro/astrology-core";
import type { ChartReadingContext } from "@astro/ai-orchestrator";

const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../../..",
);

const VENV_HINT =
  "Create it with: cd services/api-py && python -m venv .venv && .venv/Scripts/pip install -e . (Unix: .venv/bin/pip install -e .)";

function resolvePython(): { python: string; fromVenv: boolean } {
  const win = path.join(REPO_ROOT, "services/api-py/.venv/Scripts/python.exe");
  const unix = path.join(REPO_ROOT, "services/api-py/.venv/bin/python");
  if (existsSync(win)) return { python: win, fromVenv: true };
  if (existsSync(unix)) return { python: unix, fromVenv: true };
  return {
    python: process.platform === "win32" ? "python" : "python3",
    fromVenv: false,
  };
}

export type ChartReading = ChartReadingContext;

/**
 * Runs the Python interpretation engine against a stored artifact.
 * Bridge until the web app cuts over fully to FastAPI.
 */
export function buildChartReading(
  artifact: VedicChartArtifact,
): Promise<ChartReading> {
  const script = path.join(REPO_ROOT, "tools/build-reading.py");
  if (!existsSync(script)) {
    return Promise.reject(
      new Error(
        `Reading script missing at tools/build-reading.py (repo root: ${REPO_ROOT}).`,
      ),
    );
  }

  const { python, fromVenv } = resolvePython();
  if (!fromVenv) {
    return Promise.reject(
      new Error(
        `Reading engine requires services/api-py/.venv (not found). ${VENV_HINT}`,
      ),
    );
  }

  return new Promise((resolve, reject) => {
    const child = spawn(python, [script], {
      cwd: REPO_ROOT,
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env, PYTHONUTF8: "1" },
    });

    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk: string) => {
      stderr += chunk;
    });
    child.on("error", (error) => {
      reject(
        new Error(
          `Reading engine failed to start (${python}): ${error.message}. ${VENV_HINT}`,
        ),
      );
    });
    child.on("close", (code) => {
      if (code !== 0) {
        reject(
          new Error(
            `Reading engine exited ${code}: ${stderr.trim() || stdout.trim() || "no output"}`,
          ),
        );
        return;
      }
      try {
        resolve(JSON.parse(stdout) as ChartReading);
      } catch (error) {
        reject(
          new Error(
            `Reading engine returned invalid JSON: ${
              error instanceof Error ? error.message : String(error)
            }`,
          ),
        );
      }
    });

    child.stdin.write(JSON.stringify(artifact));
    child.stdin.end();
  });
}
