import { expect, test } from "@playwright/test";

/**
 * Create client -> consent -> chart -> ask (MockProvider) -> report, all against the live /v1 API.
 * Serial: each step builds on the client created in the first.
 */
test.describe.serial("live practitioner flow", () => {
  const name = `E2E Client ${Date.now()}`;
  let chartUrl = "";

  async function fillIntake(page: import("@playwright/test").Page) {
    await page.goto("/clients/new");
    await page.getByLabel("Client", { exact: true }).fill(name);
    await page.getByLabel("Day").fill("15");
    await page.getByLabel("Month").fill("03");
    await page.getByLabel("Year").fill("1995");
    await page.getByLabel("Hour").fill("06");
    await page.getByLabel("Minute").fill("42");
    await expect(page.getByText("Wednesday")).toBeVisible();
    await page.getByLabel("Place of birth").fill("Varanasi, India");
    await page.getByRole("button", { name: /confirm varanasi/i }).first().click({ timeout: 15_000 });
  }

  test("intake: consent captured inline, lagna preview from the API, chart generated", async ({ page }) => {
    await fillIntake(page);
    // Live lagna preview, not the fixture.
    await expect(page.getByText(/Pisces lagna 10/)).toBeVisible();
    // No consent yet: generating is blocked until the notice is acknowledged.
    const generate = page.getByRole("button", { name: /generate chart/i });
    await expect(page.getByRole("region", { name: "Client consent" })).toBeVisible();
    await expect(generate).toBeDisabled();
    await page.getByRole("checkbox", { name: /heard or read this notice/i }).click();
    await generate.click();
    await expect(page).toHaveURL(/\/charts\/[^/?]+$/, { timeout: 30_000 });
    chartUrl = new URL(page.url()).pathname;
    await expect(page.getByRole("heading", { name }).first()).toBeVisible();
    await page.getByRole("tab", { name: "Planets" }).click();
    await expect(page.getByRole("heading", { name: "Planet positions" })).toBeVisible();
  });

  test("regenerating the same details reuses the existing chart", async ({ page }) => {
    await fillIntake(page);
    await expect(page.getByText("Existing client")).toBeVisible();
    await expect(page.getByRole("region", { name: "Client consent" })).toHaveCount(0);
    await page.getByRole("button", { name: /generate chart/i }).click();
    await expect(page).toHaveURL(`${new URL(page.url()).origin}${chartUrl}?reused=1`, { timeout: 30_000 });
    await expect(page.getByText(/Existing chart reused/)).toBeVisible();
  });

  test("reading and remedies tabs render from live data", async ({ page }) => {
    await page.goto(chartUrl);
    await page.getByRole("tab", { name: "Reading" }).click();
    await expect(page.getByRole("navigation", { name: "Life chapters" })).toBeVisible();
    await page.getByRole("tab", { name: "Remedies" }).click();
    await expect(page.getByText("Remedy plan builder")).toBeVisible();
  });

  test("ask streams a cited answer; AI consent is recorded inline", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(chartUrl);
    const ask = page.getByRole("complementary", { name: "Ask about this chart" });
    await ask.getByRole("textbox", { name: "Ask about this chart" }).fill("What does the Moon dasha mean for career?");
    await ask.getByRole("button", { name: "Send question" }).click();
    // ai_assistant consent was never given: the API answers 403 consent_required.
    await expect(ask.getByRole("alert")).toContainText(/not agreed to ai assistant/i);
    await ask.getByRole("button", { name: /record consent and ask again/i }).click();
    await expect(ask.getByText("Verifier · all claims match")).toBeVisible();
    await expect(ask.getByRole("button", { name: /Lagna Pisces/ }).first()).toBeVisible();
  });

  test("report: queued, rendered, signed download", async ({ page }) => {
    await page.goto(`${chartUrl}/report`);
    await page.getByRole("button", { name: /export pdf/i }).click();
    const link = page.getByRole("link", { name: "Download PDF" });
    await expect(link).toBeVisible({ timeout: 60_000 });
    const href = await link.getAttribute("href");
    const res = await page.request.get(href!);
    expect(res.status()).toBe(200);
    expect(res.headers()["content-type"]).toContain("pdf");
  });

  test("branding settings round trip", async ({ page }) => {
    await page.goto("/settings/branding");
    await page.getByLabel("Report footer").fill("Pune, advisory only");
    await page.getByRole("button", { name: "Save branding" }).click();
    await expect(page.getByText("Branding saved")).toBeVisible();
  });
});
