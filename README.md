<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/banner-dark.png" />
    <img src="docs/images/banner-light.png" alt="Ankana: the Jyotish practice workspace" width="100%" />
  </picture>
</p>

<p align="center">
  <b>Charts, Lal Kitab and an AI that cites the chart, on your own server.</b>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-D32704?style=flat-square" /></a>
  <img alt="Python 3.13" src="https://img.shields.io/badge/python-3.13-221E1D?style=flat-square&logo=python&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-backend-221E1D?style=flat-square&logo=fastapi&logoColor=white" />
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-web-221E1D?style=flat-square&logo=nextdotjs&logoColor=white" />
  <img alt="Postgres 16" src="https://img.shields.io/badge/Postgres-16-221E1D?style=flat-square&logo=postgresql&logoColor=white" />
</p>

<p align="center">
  <a href="https://mrigankad.github.io/Ankana/">Website</a> |
  <a href="#what-it-does">What it does</a> |
  <a href="#screenshots">Screenshots</a> |
  <a href="#how-it-works">How it works</a> |
  <a href="#bring-your-own-ai">AI</a> |
  <a href="#quick-start">Quick start</a> |
  <a href="#roadmap">Roadmap</a> |
  <a href="#license">License</a>
</p>

<p align="center">
  <img src="docs/images/ankana-demo.gif" alt="A tour of Ankana: Today, a client brief, planets with the proof drawer, ashtakavarga, dasha drill-down, sade sati, and a verified AI answer" width="860" />
  <br />
  <sub>Today, a client brief, a proof drawer, ashtakavarga, dashas, sade sati and a verified answer, from the running app. <a href="docs/images/ankana-demo.mp4">Watch as video</a>.</sub>
</p>

**Ankana** (अंकन) is a workspace for practicing Jyotishis. You keep your clients in one book, compute their charts with the Swiss Ephemeris, read them with Lal Kitab and Parashari rules, ask an AI assistant that must cite the chart for every claim, and hand over a PDF that carries your name, not ours. It is open source under AGPL-3.0 and you run it on your own server.

> **Advisory only.** Charts, timing and readings are interpretive guidance. They are not medical, legal or financial advice.

## What it does

<table>
<tr>
<td width="33%" valign="top"><img src="docs/images/icons/chart.svg" width="40" height="40" alt="" /><br /><b>Charts and a client book</b><br />Swiss Ephemeris charts, Vimshottari dashas and a transit timeline beside consent, consultations and notes. The same birth data always produces the same chart record.</td>
<td width="33%" valign="top"><img src="docs/images/icons/book.svg" width="40" height="40" alt="" /><br /><b>Lal Kitab with citations</b><br />108 planet and house rules and varshphal, with the lagna as house 1 and one remedy at a time. Every row cites its page in the source edition.</td>
<td width="33%" valign="top"><img src="docs/images/icons/shield.svg" width="40" height="40" alt="" /><br /><b>AI that cites the chart</b><br />Each sentence carries structured claims that a deterministic verifier checks against the chart. The verifier calls no model.</td>
</tr>
<tr>
<td width="33%" valign="top"><img src="docs/images/icons/proof.svg" width="40" height="40" alt="" /><br /><b>Proof for every value</b><br />Select a planet value and a drawer shows its inputs, the rule and the source.</td>
<td width="33%" valign="top"><img src="docs/images/icons/grid.svg" width="40" height="40" alt="" /><br /><b>Ashtakavarga and dashas</b><br />Bindu grids with strength totals, and a dasha tree you can drill from a period down to the day.</td>
<td width="33%" valign="top"><img src="docs/images/icons/transit.svg" width="40" height="40" alt="" /><br /><b>Transits and sade sati</b><br />Gochara with a what-if date, and a lifetime band of every sade sati and dhaiya.</td>
</tr>
<tr>
<td width="33%" valign="top"><img src="docs/images/icons/brief.svg" width="40" height="40" alt="" /><br /><b>Pre-consult brief and notes</b><br />The client's question, running period and notable transits, ready before they arrive, with consult notes alongside.</td>
<td width="33%" valign="top"><img src="docs/images/icons/team.svg" width="40" height="40" alt="" /><br /><b>Team and client portal</b><br />Owner, astrologer and assistant roles, built-in sign-in with optional OIDC, and a portal where clients follow their remedy plan.</td>
<td width="33%" valign="top"><img src="docs/images/icons/bell.svg" width="40" height="40" alt="" /><br /><b>Remedies and reminders</b><br />Caution-aware remedies tied to the planet and house, with reminders over email, WhatsApp and SMS.</td>
</tr>
<tr>
<td width="33%" valign="top"><img src="docs/images/icons/hindi.svg" width="40" height="40" alt="" /><br /><b>Hindi</b><br />Chart terms, readings and reports are available in Hindi.</td>
<td width="33%" valign="top"><img src="docs/images/icons/lock.svg" width="40" height="40" alt="" /><br /><b>Privacy and DPDP</b><br />Client fields are encrypted per practice with AES-256-GCM and blind indexes, with tooling for data requests. Templates for a privacy notice and a data processing agreement are in <a href="docs/privacy">docs/privacy</a>.</td>
<td width="33%" valign="top"><img src="docs/images/icons/pdf.svg" width="40" height="40" alt="" /><br /><b>Reports in your brand</b><br />Your logo, colours and wording on every PDF, with an advisory line you control. A Today feed shows the day's consultations and panchang.</td>
</tr>
</table>

## Screenshots

<table>
<tr>
<td width="33%" valign="top"><img src="docs/images/screens/01-today.webp" alt="Today" /><br /><sub><b>Today</b></sub></td>
<td width="33%" valign="top"><img src="docs/images/screens/02-clients.webp" alt="Clients" /><br /><sub><b>Clients</b></sub></td>
<td width="33%" valign="top"><img src="docs/images/screens/03-overview.webp" alt="Chart overview with the assistant" /><br /><sub><b>Chart overview with the assistant</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="docs/images/screens/04-planets-proof.webp" alt="Planets with the proof drawer" /><br /><sub><b>Planets with the proof drawer</b></sub></td>
<td width="33%" valign="top"><img src="docs/images/screens/05-strengths.webp" alt="Ashtakavarga" /><br /><sub><b>Ashtakavarga</b></sub></td>
<td width="33%" valign="top"><img src="docs/images/screens/06-dashas.webp" alt="Dasha drill-down" /><br /><sub><b>Dasha drill-down</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="docs/images/screens/07-transits-sade-sati.webp" alt="Transits and sade sati" /><br /><sub><b>Transits and sade sati</b></sub></td>
<td width="33%" valign="top"><img src="docs/images/screens/08-client-brief.webp" alt="Client page with the pre-consult brief" /><br /><sub><b>Client page with the pre-consult brief</b></sub></td>
<td width="33%" valign="top"><img src="docs/images/screens/09-portal-mobile.webp" alt="Client portal on a phone" /><br /><sub><b>Client portal on a phone</b></sub></td>
</tr>
</table>

<sub>Captured from the practitioner app in fixture mode with the Sindoor theme.</sub>

## How it works

<p align="center">
  <img src="docs/images/how-it-works.png" alt="Birth data goes to the Swiss Ephemeris engine, then to an immutable chart artifact. Lal Kitab and Parashari rules fire on the artifact, the AI writes claims that a verifier checks, and a branded PDF is rendered from the same artifact. Postgres 16 row-level security underlies it all." width="100%" />
</p>

1. **Birth data** goes in with the client's consent recorded.
2. **Swiss Ephemeris** computes sidereal positions, houses, nakshatras and dashas.
3. The result is stored as an immutable, versioned **chart artifact**. Everything downstream cites it.
4. **Lal Kitab and Parashari rule engines** fire on the artifact. Each result carries its source.
5. The **AI narrator** writes sentences with structured claims in canonical values. The **claim verifier** compares every claim with the artifact (and with the Lal Kitab provider for Lal Kitab claims) without calling a model. A claim that fails is rewritten once. If it still fails, the sentence is replaced by the verified chart fact and flagged as not verified.
6. The **branded PDF** is rendered from the same artifact.

The model never computes a placement and never has the last word on a fact.

## Bring your own AI

Each practice adds connections and routes them by role. The nine connection types are Claude Code (your local login), Codex CLI (your local login), Gemini CLI (your local login), Ollama on your machine, Ollama Cloud, the Gemini API, the Anthropic API, any OpenAI-compatible endpoint (OpenAI, OpenRouter, Groq, LiteLLM, LM Studio, vLLM), and an offline sample provider for tests.

<p align="center">
  <img src="apps/site/public/providers/claude.svg" alt="Claude Code" height="32" />&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="apps/site/public/providers/ollama.svg" alt="Ollama" height="32" />&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="apps/site/public/providers/googlegemini.svg" alt="Gemini" height="32" />&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="apps/site/public/providers/openai.svg" alt="Codex and OpenAI" height="32" />&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="apps/site/public/providers/anthropic.svg" alt="Anthropic" height="32" />&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="apps/site/public/providers/openrouter.svg" alt="OpenRouter" height="32" />
</p>

### Live eval results

Run on 2026-11-14 against real models through local logins. Method, failures and fixes are in [docs/ai-live-eval.md](docs/ai-live-eval.md).

| Check | Claude Haiku, full suite | Claude Sonnet, 30 sampled |
|---|---|---|
| Cases passed | **115 of 118** (97.5%) | **30 of 30** |
| Claims checked, first pass | 412 | 127 |
| Claim accuracy, first pass | 89.8% | 100% |
| Refusal recall | **41 of 41** | **12 of 12** |
| Over-refusal on benign near misses | 0 of 10 | 0 of 4 |
| Hinglish and Hindi answer cases | 14 of 14 | 6 of 6 |

A local Ollama model could not be measured on the test machine.

## Quick start

You need Docker, Python 3.13 and pnpm 10 with Node.js 22 or later.

```bash
git clone https://github.com/mrigankad/Ankana.git
cd Ankana

# 1. Postgres 16 and Redis (creates the row-level-security role ankana_app on first start)
docker compose up -d

# 2. Python environment
cd services/api-py
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"     # Windows: .venv\Scripts\python

# 3. Migrate as the owner, run as the app role
export API_MIGRATION_URL=postgresql+psycopg://ankana:ankana_dev@localhost:5432/ankana
export API_DATABASE_URL=postgresql+psycopg://ankana_app:ankana_app_dev@localhost:5432/ankana
.venv/bin/alembic upgrade head

# 4. Serve. Built-in sign-in works out of the box in dev: the signing key is
#    generated into .auth-dev/ (gitignored) and one-time codes print to this console.
#    AUTH_DEV_STUB=1 additionally enables the dev token issuer (refused in production).
export AUTH_BUILTIN_ISSUER=http://127.0.0.1:8000 AUTH_DEV_STUB=1
.venv/bin/uvicorn app.main:app --port 8000
```

In a second terminal, start the web app:

```bash
pnpm install
pnpm --filter @astro/web-practitioner dev        # http://localhost:3000
```

To use the real sign-in screens run the web app with `NEXT_PUBLIC_AUTH_MODE=builtin NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`, open `/sign-up`, and read the six digit code from the API console. Without `NEXT_PUBLIC_AUTH_MODE` the app keeps its fixture and dev-token behaviour.

Alternatively get a dev token with `POST /v1/dev/token`, send it as `Authorization: Bearer <token>`, and create a practice with `POST /v1/practices` before using `/v1/clients`. Ankana is its own identity provider (see `docs/deploy.md`, step 5, for mail, keys and optional OIDC); an external one can still be trusted via `AUTH_JWKS_URL`, `AUTH_ISSUER` and `AUTH_AUDIENCE`. Environment templates live in `services/api-py/.env.example` and `apps/web-practitioner/.env.example`.

Run the Python tests with `pytest` from `services/api-py`. The `tests/pg` suite needs Docker, because row-level security is only proven against real Postgres.

### Look around without a backend

To explore the screens on built-in sample data with no API, run the web app with `NEXT_PUBLIC_ANKANA_DATA=fixtures`:

```bash
cd apps/web-practitioner
NEXT_PUBLIC_ANKANA_DATA=fixtures pnpm dev        # http://localhost:3000
```

## Self-host and deploy

| | |
|---|---|
| **One machine** | Docker compose for Postgres 16 and Redis, the API and the web app on your own server. |
| **Azure** | Bicep templates with CI are ready. Nothing is deployed yet. See [docs/deploy.md](docs/deploy.md). |

Built-in sign-in is Ankana's own identity provider; an external one can still be trusted. Setup for mail, keys and optional OIDC is in [docs/deploy.md](docs/deploy.md).

## Roadmap

| Shipped | In progress |
|---|---|
| Charts, dashas and the transit timeline | Expert review of the Lal Kitab rules |
| Planets depth with proof, ashtakavarga, dasha drill-down | Independent check of engine reference charts (JHora exports) |
| Gochara, sade sati and dhaiya | First Azure deployment from the Bicep templates |
| Lal Kitab, 108 rules and varshphal | Live eval of a local Ollama model |
| AI assistant with claim verifier, nine connection types | Moving the web app fully onto the Python API |
| Auth, OIDC, team roles and client portal | |
| Pre-consult brief and consult notes | |
| Reminders, Hindi, branded PDFs, Today feed | |
| DPDP encryption and data-request tooling | |

<details>
<summary><b>What is inside the repository</b></summary>

```text
Ankana/
├── services/
│   └── api-py/                FastAPI service, Postgres with row-level security
│       └── src/
│           ├── nakshatra_core/      Chart engine: Swiss Ephemeris, houses, dashas
│           ├── ankana_lalkitab/     Lal Kitab provider (Python port)
│           ├── ankana_ai/           Assistant, tools, claim verifier, evals
│           ├── nakshatra_rules/     Rule engine
│           ├── nakshatra_interpret/ Deep reading and life chapters
│           └── app/                 Routes, auth, tenancy, reports, reminders, privacy
├── packages/
│   ├── lal-kitab/             Paraphrased rule tables with page citations
│   ├── astrology-core/        TypeScript engine (earlier implementation)
│   ├── rule-engine/           Predictions and remedies
│   └── ai-orchestrator/       Assistant tools and grounding checks
├── apps/
│   ├── web-practitioner/      Next.js practitioner app
│   ├── site/                  This project's website (Astro, GitHub Pages)
│   └── api/                   Earlier Fastify API, being replaced by services/api-py
├── infra/                     Azure Bicep, Dockerfiles (see docs/deploy.md)
├── docs/                      Specs, engine accuracy, deploy, UI tour
└── docker-compose.yml         Postgres 16 and Redis for local development
```

The Python service is the future of the backend. Parts of the TypeScript stack remain while the web app moves across.

</details>

## Accuracy

Charts are computed with the [Swiss Ephemeris](https://www.astro.com/swisseph/) through `pyswisseph`, with Lahiri ayanamsa, mean node, whole-sign houses and Vimshottari dashas from the Moon by default. A suite of reference charts covers different hemispheres, eras, daylight-saving cases and a Moon-nakshatra boundary, and the engine is held to arcsecond tolerances for planets, ascendant and ayanamsa and to exact dasha dates.

The reference values are currently Swiss Ephemeris outputs marked provisional. Exports from JHora, the independent check we want, are still pending, and until they arrive the suite proves consistency, not agreement with a second program. Method, tolerances and the numbers are in [docs/engine-accuracy.md](docs/engine-accuracy.md).

## Lal Kitab

The Lal Kitab module follows the 1952 Goswami edition. Rules are paraphrased, not quoted, and each row in [packages/lal-kitab/data](packages/lal-kitab/data) carries its volume and page citation, with a `needs_review` flag where the page has not been checked against the scan.

- The lagna is house 1 by default. An Aries-as-house-1 option exists.
- Remedies that harm people or animals are deliberately excluded, along with remedies built around liquor, piercing or medicine doses.
- Remedies are ranked and offered one at a time, as the book prescribes.
- The planet and house table holds 108 rules (9 planets in 12 houses), and the year chart (varshphal) is built from the same rules.

See [packages/lal-kitab/README.md](packages/lal-kitab/README.md) for data status.

## Advisory

Ankana produces interpretive guidance for practitioners and their clients. Nothing it generates is medical, legal or financial advice, and reports carry an advisory line by default. Practitioners remain responsible for what they tell clients.

## License

Ankana is licensed under **AGPL-3.0-only**; see [LICENSE](LICENSE).

- **Network use.** The AGPL requires that anyone who uses a modified version of Ankana over a network can get its complete source. If you run a modified Ankana for other people, you must publish your changes under the same licence. The app shows a "Source code" link to the public repository and the deployed commit.
- **Swiss Ephemeris.** The ephemeris is used under its AGPL-3.0 licence from Astrodienst, which is why no separate professional licence is needed.
- **Your data.** Secrets, configuration and practitioner or client data are not source and stay private.

Details are in [services/api-py/LICENSING.md](services/api-py/LICENSING.md).
