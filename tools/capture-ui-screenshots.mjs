/**
 * One-shot UI screenshot capture for docs.
 * Requires local web (:3000) + API (:3001) already running.
 *
 * Usage:
 *   node tools/capture-ui-screenshots.mjs [jobId] [clientId]
 */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, "..", "docs", "images", "ui");
const BASE = process.env.WEB_BASE_URL ?? "http://127.0.0.1:3000";
const JOB_ID = process.argv[2] ?? "cmsbcy8zj0004ewhki5km68qx";
const CLIENT_ID = process.argv[3] ?? "cmsbcy8wq0000ewhkg2xcnngh";

mkdirSync(OUT, { recursive: true });

async function shot(page, name, options = {}) {
  const path = join(OUT, `${name}.png`);
  await page.screenshot({
    path,
    fullPage: options.fullPage ?? false,
    animations: "disabled",
  });
  console.log("wrote", path);
}

async function waitSettled(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(600);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });

  // 01 Dashboard
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.getByText("Charts computed").waitFor({ timeout: 20000 });
  await waitSettled(page);
  await shot(page, "01-dashboard");

  // 02 Clients board
  await page.goto(`${BASE}/clients`, { waitUntil: "networkidle" });
  await page.getByText("Ananya Sharma").first().waitFor({ timeout: 20000 });
  await waitSettled(page);
  await shot(page, "02-clients-board");

  // 03 New client intake
  await page.goto(`${BASE}/clients/new`, { waitUntil: "networkidle" });
  await page.getByLabel("Full name").waitFor({ timeout: 15000 });
  await page.getByLabel("Full name").fill("Ananya Sharma");
  await page.getByLabel("Birth date").fill("1995-03-15");
  await page.getByLabel("Birth time").fill("06:42");
  const place = page.getByLabel(/birth place|place/i).first();
  if (await place.count()) {
    await place.fill("Varanasi, India");
  }
  await waitSettled(page);
  await shot(page, "03-client-intake");

  // 04 Client detail
  await page.goto(`${BASE}/clients/${CLIENT_ID}`, { waitUntil: "networkidle" });
  await page.getByText("Ananya Sharma").first().waitFor({ timeout: 20000 });
  await waitSettled(page);
  await shot(page, "04-client-detail");

  // Chart helpers
  async function openChart(tab) {
    const url = tab
      ? `${BASE}/charts/${JOB_ID}?tab=${tab}`
      : `${BASE}/charts/${JOB_ID}`;
    await page.goto(url, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: /birth chart/i }).waitFor({
      timeout: 30000,
    });
    if (tab) {
      const label =
        {
          overview: "Overview",
          reading: "Reading",
          planets: "Planets",
          dashas: "Dashas",
          yogas: "Yogas",
          strengths: "Strengths",
          vargas: "Vargas",
          predictions: "Predictions",
          remedies: "Remedies",
          transits: "Transits",
        }[tab] ?? tab;
      await page.getByRole("tab", { name: label }).click();
      await waitSettled(page);
    } else {
      await waitSettled(page);
    }
  }

  // Prefer clicking tabs if ?tab= isn't wired
  async function chartTab(label, file) {
    await page.goto(`${BASE}/charts/${JOB_ID}`, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: /birth chart/i }).waitFor({
      timeout: 30000,
    });
    // Wait for artifact tabs
    await page.getByRole("tab", { name: "Overview" }).waitFor({ timeout: 30000 });
    await page.getByRole("tab", { name: label }).click();
    await waitSettled(page);
    await page.waitForTimeout(800);
    await shot(page, file, { fullPage: false });
  }

  await chartTab("Overview", "05-chart-overview");
  await chartTab("Planets", "06-chart-planets");
  await chartTab("Dashas", "07-chart-dashas");
  await chartTab("Yogas", "08-chart-yogas");
  await chartTab("Strengths", "09-chart-strengths");
  await chartTab("Predictions", "10-chart-predictions");
  await chartTab("Remedies", "11-chart-remedies");
  await chartTab("Reading", "12-chart-reading-your-life");

  // Assistant open with suggestions (Ananya)
  await page.goto(`${BASE}/charts/${JOB_ID}?assistant=open`, {
    waitUntil: "networkidle",
  });
  await page.getByRole("heading", { name: /birth chart/i }).waitFor({
    timeout: 30000,
  });
  await page
    .getByText(/Ask about Ananya/i)
    .first()
    .waitFor({ timeout: 20000 });
  await waitSettled(page);
  await shot(page, "13-chart-assistant");

  // Print / PDF preview
  await page.goto(`${BASE}/charts/${JOB_ID}/print`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await waitSettled(page);
  await shot(page, "14-report-print", { fullPage: true });

  // Transits as bonus detail
  await chartTab("Transits", "15-chart-transits");

  await browser.close();
  console.log("done");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
