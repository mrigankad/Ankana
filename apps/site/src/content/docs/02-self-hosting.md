---
title: Self-hosting
order: 2
summary: Run the stack with docker compose, or run the API directly for development.
---

## With docker compose

The repository ships a `docker-compose.yml` with these services:

| Service | What it does | Port |
|---|---|---|
| `postgres` | Postgres 16. Creates the owner role `ankana` and the row-level-security role `ankana_app` on first start. | 5432 |
| `redis` | Redis 7. | 6379 |
| `migrate` | Runs `alembic upgrade head` as the owner role, then exits. | none |
| `api` | The FastAPI service, started after `migrate` completes. | 8000 |
| `worker` | The same image with the `python -m app.worker` entrypoint, for report rendering with Chromium. | none |

Start everything:

```
docker compose up -d --build migrate api worker
```

Start only the databases, if you prefer to run the API from source:

```
docker compose up -d
```

The compose file is a development setup. It uses the stub token issuer (`AUTH_DEV_STUB=1`), local file storage and placeholder passwords. Do not expose it to the internet as it stands.

## Running the API from source

```
cd services/api-py
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"      # Windows: .venv\Scripts\python

export API_MIGRATION_URL=postgresql+psycopg://ankana:ankana_dev@localhost:5432/ankana
export API_DATABASE_URL=postgresql+psycopg://ankana_app:ankana_app_dev@localhost:5432/ankana
.venv/bin/alembic upgrade head

export AUTH_DEV_STUB=1
.venv/bin/uvicorn app.main:app --port 8000
```

Migrate as the owner, run as the app role. The app role has no superuser or BYPASSRLS rights, so tenant isolation is enforced by Postgres.

## Production

Production needs a real identity provider and real secrets. Set `API_ENV=production`, `AUTH_JWKS_URL`, `AUTH_ISSUER` and `AUTH_AUDIENCE`, and a private `STORAGE_SIGNING_KEY`. The repository includes Azure Bicep files and a deploy guide in `docs/deploy.md`. Nothing has been deployed by the project itself.

## Keep the source public

Ankana is AGPL-3.0-only. If you run a modified version for other people, the source of that exact version must be available to them. Set `ANKANA_SOURCE_URL` and `ANKANA_GIT_SHA` so the app can show a Source code link. See the licence section below.

## Swiss Ephemeris data files

Production images must include the Swiss Ephemeris data files. Without them, pyswisseph falls back to the built-in Moshier ephemeris, which is less precise. The files are fetched by `scripts/fetch_ephe.py` and point to `ANKANA_SE_EPHE_PATH`.
