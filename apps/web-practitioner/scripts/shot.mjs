// Usage: node scripts/shot.mjs <path> <outfile> [width] [height] [fullPage]
import { chromium } from "@playwright/test";
const [, , path, out, w = "1440", h = "900", full = "0"] = process.argv;
const browser = await chromium.launch({ channel: process.env.PW_CHANNEL ?? "chrome" });
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
await page.goto(`http://localhost:${process.env.PORT ?? 3100}${path}`, { waitUntil: "networkidle" });
await page.waitForTimeout(600);
await page.screenshot({ path: out, fullPage: full === "1" });
await browser.close();
