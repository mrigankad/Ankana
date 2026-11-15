#!/usr/bin/env node
/**
 * Mint a dev token and a practice against a local API started with AUTH_DEV_STUB=1.
 *
 *   node scripts/dev-bootstrap.mjs [--api http://127.0.0.1:3001] [--write .env.local]
 *
 * Prints NEXT_PUBLIC_V1_TOKEN / NEXT_PUBLIC_PRACTICE_ID lines (and writes them to --write).
 * The stub token lives for one hour; run again when it expires. Not for production.
 */
import { writeFileSync } from "node:fs";

export async function bootstrap(api = "http://127.0.0.1:3001", subject = "dev-owner") {
  const post = async (path, body, headers = {}) => {
    const res = await fetch(`${api}${path}`, { method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error(`${path} -> ${res.status} ${await res.text()}`);
    return res.json();
  };
  const { access_token: token } = await post("/v1/dev/token", { subject, email: `${subject}@ankana.test`, name: "Dev Owner" });
  const me = await (await fetch(`${api}/v1/me`, { headers: { authorization: `Bearer ${token}` } })).json();
  let practice = me.memberships?.[0]?.practice_id;
  if (!practice) practice = (await post("/v1/practices", { name: "Dev Practice" }, { authorization: `Bearer ${token}` })).practice_id;
  return { token, practice };
}

if (process.argv[1]?.endsWith("dev-bootstrap.mjs")) {
  const arg = (n, d) => (process.argv.includes(n) ? process.argv[process.argv.indexOf(n) + 1] : d);
  const api = arg("--api", process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:3001");
  const { token, practice } = await bootstrap(api, arg("--subject", "dev-owner"));
  const lines = `NEXT_PUBLIC_API_BASE_URL=${api}\nNEXT_PUBLIC_V1_TOKEN=${token}\nNEXT_PUBLIC_PRACTICE_ID=${practice}\nNEXT_PUBLIC_ANKANA_DATA=live\n`;
  const file = arg("--write", "");
  if (file) writeFileSync(file, lines);
  else process.stdout.write(lines);
}
