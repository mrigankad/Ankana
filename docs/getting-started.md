# Getting started

Run Nakshatra locally: practitioner web UI + Node API + optional Python reading engine.

## Prerequisites

- **Node.js 22+** and **pnpm 10**
- **Python 3.11+** (for Deep reading / Your Life via `services/api-py`)
- Optional: **Ollama** (cloud key or local) for the live chart assistant; otherwise use `OLLAMA_MOCK=1`

## 1. Clone and install

```bash
git clone https://github.com/mrigankad/Nakshatra.git
cd Nakshatra
pnpm install
```

## 2. Environment files

```bash
cp apps/api/.env.example apps/api/.env
cp apps/web-practitioner/.env.example apps/web-practitioner/.env.local
```

Edit `apps/api/.env`:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLite file for clients/charts (default `file:./dev.db`) |
| `OLLAMA_*` | Live assistant; leave blank and set `OLLAMA_MOCK=1` offline |
| `WEB_BASE_URL` | Print URL for PDF rendering (`http://localhost:3000`) |

**Never commit** `.env`, `.env.local`, or `*.db` files. They hold API keys and client data.

## 3. Database (Node API)

```bash
pnpm --filter @astro/api exec prisma generate
pnpm --filter @astro/api exec prisma db push
```

This creates `apps/api/dev.db` locally. It is gitignored.

## 4. Python reading engine (recommended)

Deep reading and Your Life need the venv the API expects:

```bash
cd services/api-py
python -m venv .venv

# Windows
.venv\Scripts\pip install -e .

# macOS / Linux
.venv/bin/pip install -e .

cd ../..
```

## 5. Start the apps

From the repo root:

```bash
# Terminal A — API (http://127.0.0.1:3001)
pnpm --filter @astro/api dev

# Terminal B — Web (http://localhost:3000)
pnpm --filter @astro/web-practitioner dev
```

Or run both:

```bash
pnpm dev
```

Open **http://localhost:3000**.

**What the UI looks like:** see the annotated [UI tour](./ui-tour.md) (demo client **Ananya Sharma**, Varanasi 1995-03-15 06:42). Suggested first pass: Dashboard → New chart → Overview → Reading → Assistant → Download PDF.

### Assistant modes

- **Mock (no key):** set `OLLAMA_MOCK=1` in `apps/api/.env`
- **Live:** set `OLLAMA_BASE_URL`, `OLLAMA_API_KEY`, and a tool-capable `OLLAMA_MODEL`

Health check: `GET http://127.0.0.1:3001/api/v1/assistant/health`

### PDF reports

With both apps running and Playwright Chromium installed:

```bash
pnpm exec playwright install chromium
```

Unset `REPORT_RENDERER` (or leave it unset). Tests use `REPORT_RENDERER=stub`.

## 6. Verify

```bash
pnpm -r lint
pnpm -r test
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Reading 503 / “venv not found” | Create `services/api-py/.venv` and `pip install -e .` |
| Assistant offline | Use `OLLAMA_MOCK=1` or fix Ollama URL/key |
| Empty clients after pull | Expected — your `dev.db` never leaves your machine |
| PDF fails | Ensure web is on `:3000` and Chromium is installed |

## More docs

- UI screenshots & walkthrough: [`ui-tour.md`](./ui-tour.md)
- Root overview: [`../README.md`](../README.md)
- Product / architecture hub: [`README.md`](./README.md)
- Chart AI roadmap: `superpowers/plans/2026-08-02-chart-ai-roadmap.md`
