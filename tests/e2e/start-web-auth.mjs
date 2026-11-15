/**
 * Starts the Next dev server for the team and portal e2e with built-in sign-in turned on
 * (NEXT_PUBLIC_AUTH_MODE=builtin). The API must run with AUTH_MAILER=console, and
 * AUTH_ALLOWED_ORIGINS / AUTH_WEB_BASE_URL set to this web origin.
 *
 *   E2E_API_URL   default http://127.0.0.1:3151
 *   E2E_WEB_PORT  default 3150
 */
import { spawn } from "node:child_process";

const api = process.env.E2E_API_URL ?? "http://127.0.0.1:3151";
const port = process.env.E2E_WEB_PORT ?? "3150";

const child = spawn("pnpm", ["--filter", "@astro/web-practitioner", "exec", "next", "dev", "-p", port, "-H", "127.0.0.1"], {
  stdio: "inherit",
  shell: true,
  env: {
    ...process.env,
    NEXT_PUBLIC_ANKANA_DATA: "live",
    NEXT_PUBLIC_AUTH_MODE: "builtin",
    NEXT_PUBLIC_API_BASE_URL: api,
  },
});
child.on("exit", (code) => process.exit(code ?? 0));
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
