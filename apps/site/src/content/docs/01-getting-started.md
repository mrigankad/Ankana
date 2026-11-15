---
title: Getting started
order: 1
summary: What Ankana is, what you need, and the shortest path to a running workspace.
---

Ankana (अंकन) is a workspace for practicing Jyotishis. You keep clients in one book, compute charts with the Swiss Ephemeris, read them with Lal Kitab and Parashari rules, ask an assistant that must cite the chart for every claim, and export a PDF that carries your name.

> **Advisory only.** Charts, timing and readings are interpretive guidance. They are not medical, legal or financial advice.

## What you need

- Docker, for Postgres 16, Redis and the API.
- Node.js 22 or later and pnpm 10, for the web app.
- Python 3.13, only if you run the API outside Docker.

## Shortest path

```
git clone https://github.com/mrigankad/Ankana.git
cd Ankana
docker compose up -d --build migrate api worker
pnpm install
pnpm --filter @astro/web-practitioner dev
```

The API listens on port 8000. The web app listens on port 3000.

## First request

The development stack uses a stub token issuer, which the API refuses when `API_ENV=production`. Get a dev token with `POST /v1/dev/token`, send it as `Authorization: Bearer <token>`, and create a practice with `POST /v1/practices` before using `/v1/clients`.

## What is in the repository

- `services/api-py` is the FastAPI service with Postgres row-level security. It holds the chart engine, the Lal Kitab provider, the assistant with its claim verifier, and the rule engine.
- `packages/lal-kitab` holds the paraphrased rule tables with page citations.
- `apps/web-practitioner` is the Next.js practitioner app.
- `infra` holds Azure Bicep files and Dockerfiles.
- `docs` holds the specifications, engine accuracy notes and a UI tour.

The Python service is the future of the backend. Parts of the TypeScript stack remain while the web app moves across.
