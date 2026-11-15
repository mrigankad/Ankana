// Seed a client + chart through the live API, then screenshot the main screens.
// Usage: API=http://127.0.0.1:3101 WEB=http://127.0.0.1:3110 OUT=./shots node scripts/live-shots.mjs
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { bootstrap } from "./dev-bootstrap.mjs";

const API = process.env.API ?? "http://127.0.0.1:3101";
const WEB = process.env.WEB ?? "http://127.0.0.1:3110";
const OUT = process.env.OUT ?? "./shots";
mkdirSync(OUT, { recursive: true });

const { token, practice } = await bootstrap(API);
const H = { "content-type": "application/json", authorization: `Bearer ${token}`, "x-practice-id": practice };
const call = async (method, path, body) => {
  const r = await fetch(`${API}/v1${path}`, { method, headers: H, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error(`${path} ${r.status} ${await r.text()}`);
  return r.json();
};
const { client } = await call("POST", "/clients", { display_name: "Ananya Sharma", contact_email: "ananya@example.com", timezone: "Asia/Kolkata", preferred_language: "en" });
for (const purpose of ["chart_compute", "ai_assistant", "report_sharing"]) await call("POST", `/clients/${client.id}/consents`, { purpose, notice_version: "2026-11", notice_text: "Shown in person", channel: "in_person" });
const { birth_record: rec } = await call("POST", `/clients/${client.id}/birth-records`, { birth_date: "1995-03-15", birth_time: "06:42:00", time_source: "certificate", place_label: "Varanasi, Uttar Pradesh, India", latitude: 25.3176, longitude: 82.9739, timezone_name: "Asia/Kolkata" });
const { chart } = await call("POST", `/clients/${client.id}/charts`, { birth_record_id: rec.id });
await call("POST", `/clients/${client.id}/consultations`, { topic: "Career question, 2nd visit", note: "Chart prepared. Open with Jupiter in the 9th.", chart_artifact_id: chart.id });
console.log(JSON.stringify({ client: client.id, chart: chart.id }));

const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const shots = [
  ["clients", "/clients"],
  ["client", `/clients/${client.id}`],
  ["new", "/clients/new"],
  ["chart-overview", `/charts/${chart.id}`],
  ["chart-reading", `/charts/${chart.id}?tab=reading`],
  ["chart-planets", `/charts/${chart.id}?tab=planets`],
  ["chart-yogas", `/charts/${chart.id}?tab=yogas`],
  ["chart-strengths", `/charts/${chart.id}?tab=strengths`],
  ["chart-vargas", `/charts/${chart.id}?tab=vargas`],
  ["chart-transits", `/charts/${chart.id}?tab=transits`],
  ["chart-remedies", `/charts/${chart.id}?tab=remedies`],
  ["report", `/charts/${chart.id}/report`],
  ["branding", "/settings/branding"],
];
for (const [name, path] of shots) {
  await page.goto(`${WEB}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false });
  console.log("shot", name);
}
// Ask with a streamed answer on the Reading tab.
await page.goto(`${WEB}/charts/${chart.id}?tab=reading`, { waitUntil: "networkidle" });
const ask = page.getByRole("complementary", { name: "Ask about this chart" });
await ask.getByRole("textbox", { name: "Ask about this chart" }).fill("What does the Moon dasha mean for career?");
await ask.getByRole("button", { name: "Send question" }).click();
await ask.getByText("Verifier").first().waitFor();
await page.waitForTimeout(600);
await page.screenshot({ path: `${OUT}/chart-reading-ask.png` });
// Intake with a located place and the live preview.
await page.goto(`${WEB}/clients/new`, { waitUntil: "networkidle" });
await page.getByLabel("Client", { exact: true }).fill("Meera Iyer");
await page.getByLabel("Day").fill("11");
await page.getByLabel("Month").fill("11");
await page.getByLabel("Year").fill("1991");
await page.getByLabel("Hour").fill("05");
await page.getByLabel("Minute").fill("20");
await page.getByLabel("Place of birth").fill("Varanasi, India");
await page.getByRole("button", { name: /confirm varanasi/i }).first().click();
await page.getByText(/lagna \d/).first().waitFor();
await page.waitForTimeout(600);
await page.screenshot({ path: `${OUT}/new-filled.png` });
await browser.close();
