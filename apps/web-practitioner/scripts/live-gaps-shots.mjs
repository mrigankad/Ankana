// Seed a practice with several clients (tags, visits, follow-ups, a report) through the live API,
// then screenshot Today, Clients, Client and the chart Transits tab in system Chrome.
// Usage: API=http://127.0.0.1:3141 WEB=http://127.0.0.1:3142 OUT=./shots node scripts/live-gaps-shots.mjs
// The web server must be started with the token this script prints (see the first line of output),
// or pass TOKEN and PRACTICE to reuse one.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { bootstrap } from "./dev-bootstrap.mjs";

const API = process.env.API ?? "http://127.0.0.1:3141";
const WEB = process.env.WEB ?? "http://127.0.0.1:3142";
const OUT = process.env.OUT ?? "./shots";
mkdirSync(OUT, { recursive: true });

const { token, practice } = await bootstrap(API);
const H = { "content-type": "application/json", authorization: `Bearer ${token}`, "x-practice-id": practice };
const call = async (method, path, body) => {
  const r = await fetch(`${API}/v1${path}`, { method, headers: H, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error(`${path} ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
};
const day = (n) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);
const at = (h, m) => {
  const d = new Date();
  const ist = new Date(d.getTime() + 5.5 * 3600000);
  return new Date(Date.UTC(ist.getUTCFullYear(), ist.getUTCMonth(), ist.getUTCDate(), h, m) - 5.5 * 3600000).toISOString();
};

const people = [
  ["Ananya Sharma", "1995-03-15", "06:42", "certificate", "Varanasi, Uttar Pradesh, India", 25.3176, 82.9739, ["Lal Kitab"], 11.5],
  ["Vikram Rao", "1988-08-02", "14:10", "memory", "Hyderabad, Telangana, India", 17.385, 78.4867, ["Lal Kitab", "Matching"], 14],
  ["Meera Iyer", "1991-11-11", "09:30", "approximate", "Chennai, Tamil Nadu, India", 13.0827, 80.2707, ["Rectify"], 16.25],
  ["Sana Qureshi", "1993-06-27", "20:05", "certificate", "Lucknow, Uttar Pradesh, India", 26.8467, 80.9462, ["Lal Kitab"], null],
  ["Rajesh Kulkarni", "1979-01-19", "05:15", "certificate", "Nashik, Maharashtra, India", 19.9975, 73.7898, ["Matching"], null],
  ["Pooja Deshmukh", "1998-05-08", "11:45", "memory", "Pune, Maharashtra, India", 18.5204, 73.8567, [], null],
];
const ids = {};
if (process.env.SKIP_SEED) {
  const { clients } = await call("GET", "/clients?limit=50");
  for (const c of clients) ids[c.display_name] = { client: c.id, chart: c.latest_chart_id };
}
for (const [name, date, time, src, place, lat, lon, tags, slot] of process.env.SKIP_SEED ? [] : people) {
  const { client } = await call("POST", "/clients", { display_name: name, contact_email: `${name.split(" ")[0].toLowerCase()}@example.com`, timezone: "Asia/Kolkata", preferred_language: "en" });
  for (const purpose of ["chart_compute", "ai_assistant", "report_sharing"]) await call("POST", `/clients/${client.id}/consents`, { purpose, notice_version: "2026-11", notice_text: "Shown in person", channel: "in_person" });
  const { birth_record: rec } = await call("POST", `/clients/${client.id}/birth-records`, { birth_date: date, birth_time: `${time}:00`, time_source: src, place_label: place, latitude: lat, longitude: lon, timezone_name: "Asia/Kolkata" });
  const { chart } = await call("POST", `/clients/${client.id}/charts`, { birth_record_id: rec.id });
  if (tags.length) await call("PUT", `/clients/${client.id}/tags`, { tags });
  ids[name] = { client: client.id, chart: chart.id };
  if (slot !== null) await call("POST", `/clients/${client.id}/consultations`, { scheduled_at: at(Math.floor(slot), (slot % 1) * 60), topic: name === "Ananya Sharma" ? "Career question, 2nd visit" : name === "Vikram Rao" ? "Business, first visit" : "Birth time check", chart_artifact_id: chart.id, mode: "in_person" });
}
const past = (n) => new Date(Date.now() - n * 86400000).toISOString();
if (!process.env.SKIP_SEED) {
await call("POST", `/clients/${ids["Sana Qureshi"].client}/consultations`, { consulted_at: past(41), topic: "Remedy review", follow_up_date: day(4) });
await call("POST", `/clients/${ids["Rajesh Kulkarni"].client}/consultations`, { consulted_at: past(15), topic: "Marriage matching", follow_up_date: day(-2) });
await call("POST", `/clients/${ids["Pooja Deshmukh"].client}/consultations`, { consulted_at: past(33), topic: "First visit", follow_up_date: day(19) });
await call("POST", `/clients/${ids["Ananya Sharma"].client}/consultations`, { consulted_at: past(21), topic: "First consultation", note: "Hospital certificate seen. Lagna stable." });
const rep = await call("POST", "/reports", { chart_id: ids["Ananya Sharma"].chart, language: "en" });
console.log("report", rep.id, rep.status);
}
console.log(JSON.stringify({ token: token.slice(0, 12), practice }));

const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await ctx.addInitScript(() => undefined);
const page = await ctx.newPage();
const shots = [
  ["today", "/"],
  ["clients", "/clients"],
  ["client", `/clients/${ids["Ananya Sharma"].client}`],
  ["transits", `/charts/${ids["Ananya Sharma"].chart}?tab=transits`],
];
for (const [name, path] of shots) {
  await page.goto(`${WEB}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  if (name === "transits") {
    await page.evaluate(() => document.querySelectorAll(".nk-scroll").forEach((el) => (el.scrollTop = el.scrollHeight)));
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${OUT}/transits-upcoming.png` });
    await page.evaluate(() => document.querySelectorAll(".nk-scroll").forEach((el) => (el.scrollTop = 560)));
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${OUT}/transits-timeline.png` });
  }
  console.log("shot", name);
}
// Clients with a tag filter applied.
await page.goto(`${WEB}/clients`, { waitUntil: "networkidle" });
await page.getByRole("button", { name: /^Lal Kitab/ }).click();
await page.waitForTimeout(900);
await page.screenshot({ path: `${OUT}/clients-lal-kitab.png` });
await browser.close();
