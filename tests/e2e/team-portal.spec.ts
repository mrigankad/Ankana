import { readFileSync } from "node:fs";

import { expect, test, type Browser, type Page } from "@playwright/test";

/**
 * Owner invites an astrologer and a client; the client accepts and checks in a remedy.
 * Runs against the real stack with built-in sign-in: the API prints mail to a log (AUTH_MAILER=console)
 * and this spec reads sign-in codes and invite links from it (E2E_API_LOG).
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:3151";
const WEB = `http://127.0.0.1:${process.env.E2E_WEB_PORT ?? "3150"}`;
const LOG = process.env.E2E_API_LOG ?? "api.log";
const stamp = Date.now();
const ownerEmail = `owner.${stamp}@example.test`;
const astroEmail = `astro.${stamp}@example.test`;
const clientEmail = `client.${stamp}@example.test`;

function readLog(): string {
  try {
    return readFileSync(LOG, "utf8");
  } catch {
    return "";
  }
}

async function mailMatch(re: RegExp): Promise<string> {
  for (let i = 0; i < 40; i++) {
    const all = [...readLog().matchAll(re)];
    if (all.length) return all[all.length - 1]![1]!;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`mail not found: ${re}`);
}

const codeFor = (email: string) => mailMatch(new RegExp(`mail to ${email.replace(/[.+]/g, "\\$&")}: Your Ankana sign-in code: (\\d{6})`, "g"));
const inviteFor = (email: string) =>
  mailMatch(new RegExp(`mail to ${email.replace(/[.+]/g, "\\$&")}: You are invited[\\s\\S]*?/invite/([\\w-]+)`, "g"));

async function ownerHeaders(page: Page) {
  const r = await page.request.post(`${API}/v1/auth/refresh`, { headers: { Origin: WEB, "X-Ankana-Csrf": "1" } });
  expect(r.status()).toBe(200);
  const s = await r.json();
  return { Authorization: `Bearer ${s.access_token}`, "X-Practice-Id": s.active_practice_id } as Record<string, string>;
}

async function joinViaInvite(browser: Browser, email: string, name: string) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(`/invite/${await inviteFor(email)}`);
  await page.getByLabel("Your name").fill(name);
  await page.getByRole("button", { name: "Email me a code" }).click();
  await page.getByLabel("Six digit code").fill(await codeFor(email));
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Accept invitation" }).click();
  return { ctx, page };
}

test("owner invites an astrologer and a client; the client accepts and checks in a remedy", async ({ page, browser }) => {
  // Owner creates the practice through the sign-up screen.
  await page.goto("/sign-up");
  await page.getByLabel("Your name").fill("Rohan Shastri");
  await page.getByLabel("Practice name").fill("Shastri Jyotish");
  await page.getByLabel("Email").fill(ownerEmail);
  await page.getByRole("button", { name: "Email me a code" }).click();
  await page.getByLabel("Six digit code").fill(await codeFor(ownerEmail));
  await page.getByRole("button", { name: "Create my practice" }).click();
  await expect(page.getByRole("link", { name: "Team" })).toBeVisible({ timeout: 30_000 });

  // A client with a started 43 day remedy plan, set up through the API.
  const h = await ownerHeaders(page);
  const created = await page.request.post(`${API}/v1/clients`, { headers: h, data: { display_name: "Ananya Sharma" } });
  const clientId = (await created.json()).client.id as string;
  const plan = await page.request.post(`${API}/v1/clients/${clientId}/remedy-plans`, {
    headers: h,
    data: { title: "Saturn, 43 days", cycle_days: 43, items: [{ title: "Light a sesame oil lamp", instructions: "At sunset", planet: "Saturn" }] },
  });
  const planId = (await plan.json()).remedy_plan.id as string;
  expect((await page.request.post(`${API}/v1/remedy-plans/${planId}/start`, { headers: h, data: {} })).status()).toBe(200);

  // Team screen: invite an astrologer.
  await page.goto("/settings/team");
  await expect(page.getByRole("heading", { name: "Team" })).toBeVisible();
  await expect(page.getByText("The only owner")).toBeVisible();
  await page.getByRole("button", { name: "Invite someone" }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Email").fill(astroEmail);
  await dialog.getByRole("button", { name: "Send invite" }).click();
  await expect(page.getByText(`Invitation sent to ${astroEmail}`)).toBeVisible();
  await expect(page.getByText(astroEmail, { exact: true })).toBeVisible();

  // Invite the client, pinned to Ananya.
  await page.getByRole("button", { name: "Invite someone" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Email").fill(clientEmail);
  await dialog.getByRole("combobox", { name: "Role" }).click();
  await page.getByRole("option", { name: "Client portal" }).click();
  await dialog.getByRole("combobox", { name: "Client" }).click();
  await page.getByRole("option", { name: "Ananya Sharma" }).click();
  await dialog.getByRole("button", { name: "Send invite" }).click();
  await expect(page.getByText(`Invitation sent to ${clientEmail}`)).toBeVisible();

  // The astrologer accepts and lands in the practitioner app, but not on owner-only settings.
  const astro = await joinViaInvite(browser, astroEmail, "Meenal Kulkarni");
  await expect(astro.page.getByRole("link", { name: "Clients" }).first()).toBeVisible({ timeout: 30_000 });
  await astro.page.goto("/settings/team");
  await expect(astro.page).not.toHaveURL(/\/settings\/team/);
  await astro.ctx.close();

  // The client accepts, lands on the portal only, and checks in today.
  const client = await joinViaInvite(browser, clientEmail, "Ananya Sharma");
  await expect(client.page).toHaveURL(/\/portal$/, { timeout: 30_000 });
  await expect(client.page.getByRole("heading", { name: "Namaste, Ananya" })).toBeVisible();
  await expect(client.page.getByText("Saturn, 43 days")).toBeVisible();
  await expect(client.page.getByText(/Guidance is advisory/)).toBeVisible();
  await client.page.goto("/clients");
  await expect(client.page).toHaveURL(/\/portal$/);
  await client.page.getByRole("button", { name: "Mark today as done" }).click();
  await expect(client.page.getByText("Done for today")).toBeVisible();
  await client.page.reload();
  await expect(client.page.getByText("Done for today")).toBeVisible();
  await expect(client.page.getByText("1 done")).toBeVisible();
  await client.ctx.close();

  // Back on the team screen the owner now sees three people and no pending invites.
  await page.goto("/settings/team");
  await expect(page.getByText("Meenal Kulkarni")).toBeVisible();
  await expect(page.getByText("Client portal").first()).toBeVisible();
  await expect(page.getByText("No invitations are waiting.")).toBeVisible();
});
