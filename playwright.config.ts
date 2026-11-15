import { defineConfig } from "@playwright/test";

// e2e runs against the real stack: FastAPI + Postgres (AUTH_DEV_STUB=1, MockProvider AI,
// stub PDF renderer) and the Next dev server in live mode. See .github/workflows/ci.yml.
const port = process.env.E2E_WEB_PORT ?? "3000";

export default defineConfig({
  testDir: "./tests/e2e",
  testIgnore: /team-portal.spec.ts/,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  webServer: {
    command: "node tests/e2e/start-web.mjs",
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    headless: true,
    // Locally set PW_CHANNEL=chrome to use the installed Chrome instead of the bundled chromium.
    channel: process.env.PW_CHANNEL || undefined,
    trace: "retain-on-failure",
  },
});
