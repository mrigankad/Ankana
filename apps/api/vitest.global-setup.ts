import { execSync } from "node:child_process";
import { rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export default function setup(): void {
  const appRoot = dirname(fileURLToPath(import.meta.url));

  // Start every test run from an empty throwaway database file.
  rmSync(join(appRoot, "test.db"), { force: true });

  execSync("pnpm exec prisma db push", {
    cwd: appRoot,
    stdio: "inherit",
    env: { ...process.env, DATABASE_URL: "file:./test.db" },
  });
}
