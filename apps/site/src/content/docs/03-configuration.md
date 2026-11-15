---
title: Configuration
order: 3
summary: The environment variables you are most likely to set.
---

Templates live in `services/api-py/.env.example` and `apps/web-practitioner/.env.example`. Never commit real secrets.

## API and database

| Variable | Purpose |
|---|---|
| `API_DATABASE_URL` | Connection for the running API. Use the non-superuser role `ankana_app`, which is subject to row-level security. |
| `API_MIGRATION_URL` | Owner connection, used only by `alembic upgrade head`. |
| `API_ENV` | `dev`, `test` or `production`. |
| `LOG_LEVEL` | Log level. Logs are JSON and carry `practice_id`. |

## Authentication

| Variable | Purpose |
|---|---|
| `AUTH_DEV_STUB` | Set to `1` for local login without a provider. Refused when `API_ENV=production`. |
| `AUTH_JWKS_URL` | JWKS endpoint of any OIDC issuer. |
| `AUTH_ISSUER` | Expected token issuer. |
| `AUTH_AUDIENCE` | Expected audience, for example `ankana-api`. |

## Reports, storage and worker

| Variable | Purpose |
|---|---|
| `STORAGE_BACKEND` | `local` or `azure`. |
| `STORAGE_LOCAL_DIR` | Directory for local storage. |
| `STORAGE_SIGNING_KEY` | Required when `API_ENV=production`. |
| `STORAGE_PUBLIC_BASE_URL` | Base URL used in signed links. |
| `WORKER_CONCURRENCY` | Caps concurrent Chromium instances for PDF rendering. |

## Engine

| Variable | Purpose |
|---|---|
| `ANKANA_SE_EPHE_PATH` | Directory with the Swiss Ephemeris `.se1` files. |
| `ANKANA_EPHEMERIS` | Set to `astronomy` to use astronomy-engine as a cross-check. It fails the reference tolerances and is not for production. |

## Observability

All optional: `OTEL_EXPORTER_OTLP_ENDPOINT`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, `SENTRY_DSN`. No request bodies, names or birth data are sent. See the AI providers section for the assistant settings.
