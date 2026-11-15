/**
 * Starts the Next dev server for e2e against a live API (AUTH_DEV_STUB=1).
 * Mints a dev token and a practice first, then hands them to the web app as
 * NEXT_PUBLIC_V1_TOKEN / NEXT_PUBLIC_PRACTICE_ID (inlined at server start).
 *
 *   E2E_API_URL   default http://127.0.0.1:3001
 *   E2E_WEB_PORT  default 3000
 */
import { spawn } from "node:child_process";
import { bootstrap } from "../../apps/web-practitioner/scripts/dev-bootstrap.mjs";

const api = process.env.E2E_API_URL ?? "http://127.0.0.1:3001";
const port = process.env.E2E_WEB_PORT ?? "3000";
const { token, practice } = await bootstrap(api, `e2e-${Date.now()}`);

const child = spawn("pnpm", ["--filter", "@astro/web-practitioner", "exec", "next", "dev", "-p", port, "-H", "127.0.0.1"], {
  stdio: "inherit",
  shell: true,
  env: {
    ...process.env,
    NEXT_PUBLIC_ANKANA_DATA: "live",
    NEXT_PUBLIC_API_BASE_URL: api,
    NEXT_PUBLIC_V1_TOKEN: token,
    NEXT_PUBLIC_PRACTICE_ID: practice,
  },
});
child.on("exit", (code) => process.exit(code ?? 0));
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
