import { defineConfig } from "@playwright/test";

// Team and portal e2e: needs the API with AUTH_MAILER=console (its output captured in E2E_API_LOG),
// AUTH_ALLOWED_ORIGINS and AUTH_WEB_BASE_URL set to the web origin below, and the report worker.
// Run:  E2E_API_LOG=api.log pnpm exec playwright test -c playwright.team.config.ts
const port = process.env.E2E_WEB_PORT ?? "3150";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: /team-portal\.spec\.ts/,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 20_000 },
  webServer: {
    command: "node tests/e2e/start-web-auth.mjs",
    url: `http://127.0.0.1:${port}/sign-in`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    headless: true,
    channel: process.env.PW_CHANNEL || undefined,
    trace: "retain-on-failure",
  },
});
