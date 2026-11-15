# Operations runbook

Backup and restore (with erasure replay), monitoring and alerts, rate limiting. Deployment itself is
`docs/deploy.md`; privacy design is `docs/privacy.md`; load results are `docs/performance.md`.

## 1. Backup and restore

### What is backed up

| Data | Where | Backup |
|---|---|---|
| All application data (practices, clients, charts, consents, audit, jobs) | Azure Database for PostgreSQL Flexible Server | Automatic, point-in-time restore (PITR) to any second inside the retention window: `pgBackupDays` (7 staging, 35 prod, `parameters/*.bicepparam`). Geo-redundant backup is off on purpose (data stays in India). |
| Report PDFs, export ZIPs, the erasure log | Blob container behind `STORAGE_BACKEND=azure` | Turn on blob soft delete and versioning (30 days) on the storage account. Not restored with the database. |
| Encryption keys | Key Vault: `ankana-master-key`, `ankana-secret-key`, `auth-signing-key-pem` | Copy of each in the operator's password manager (deploy.md section 5, step 7). Without `ankana-master-key` a restored database is unreadable. |

Per-practice data keys live in the database (`practice_key`, wrapped by the master key), so a PITR
restore brings back keys and data together.

### Erasures and backups

A backup cannot be edited, so a restore resurrects people erased after the restore point. The
application therefore keeps a durable erasure log (ids only, no names or reasons) outside the
database, and a restore is not finished until it has been replayed (step 6 below).

* Every client erasure (request, retention sweep, practice deletion) and every account deletion
  writes an event **before it deletes anything**: one small immutable JSON blob under
  `_erasure_log/<UTC timestamp>-<event id>.json` in object storage, plus a row in the append-only
  `erasure_log` table. If the blob cannot be written, the erasure does not start and the job retries.
* Event: `event_id`, `kind` (`client` or `practice`), `practice_id`, `client_id`, `via`, `at`.
* Replay re-applies the same delete-and-overwrite cascade. It overrides a legal hold because the
  original erasure was already lawful; it skips clients that are already erased (idempotent) and
  reports clients that did not exist in the backup as `unknown`.
* Protect the log: soft delete plus versioning on the account, and a read-only role assignment for
  everyone except the API and worker identities. (A dedicated container with a time-based
  immutability policy would be stronger; the log lives under a prefix of the app container today,
  so that is a follow-up, not something the code does yet.)
* Seeded by migration `0008_erasure_log` from the existing `client.erased` and `practice.deleted`
  audit events, so the log is complete from the day it ships.

### Restore runbook (Azure PostgreSQL PITR)

Time budget: restore itself 10 to 60 minutes depending on size; plan an hour of read-only or down time.
Do this in staging first once a quarter and record the date here.

1. **Declare and freeze.** Pick the restore point T (UTC, before the incident). Scale the api and
   worker to zero (`az containerapp update --min-replicas 0 --max-replicas 0` on both, or stop
   the revisions) so nothing writes while you work. Note the current time T_now.
2. **Save the erasure events from the live server** (belt and braces; the blob log is the source of
   truth and survives anyway):
   ```
   python -m app.privacy.cli export-erasure-log --since <T minus 10 minutes> --out erasures.jsonl
   ```
   (run from any container or machine with `API_DATABASE_URL` pointing at the live database).
3. **Restore to a new server** (PITR cannot restore in place). Use the same resource group and
   network settings as the original, the same major version, and the same private DNS zone:
   ```
   az postgres flexible-server restore \
     --resource-group rg-ankana-prod-cin \
     --name psql-ankana-prod-cin-restore \
     --source-server psql-ankana-prod-cin \
     --restore-time "2026-11-14T10:15:00Z" \
     --subnet <pg subnet id> --private-dns-zone <privatelink.postgres.database.azure.com id>
   ```
   Firewall rules, server parameters (`require_secure_transport`, extensions) and HA settings are
   not carried over: re-apply them (`infra/azure/modules/data.bicep` is the reference). Roles
   (`ankana`, `ankana_app`) and their passwords come with the data.
4. **Verify the restored data** before pointing anything at it: connect as the owner and check that
   `alembic_version` equals the head you expect, that `select count(*) from practice` is plausible,
   and that `ankana_app` can log in (`python scripts/set_app_role_password.py` resets its password
   from `APP_ROLE_PASSWORD` if it cannot).
5. **Point the apps at the restored server.** Update the Key Vault secrets `db-app-url` and
   `db-migration-url` (`infra/azure/scripts/set-secret.sh`), keep the api and worker at zero.
   If the restore point is older than the deployed schema, deploy the matching image or run the
   migrate job (forward only).
6. **Replay erasures** (the step that keeps erased people erased). With the api still stopped, from
   a one-off container using the api image and the app database URL:
   ```
   python -m app.privacy.cli replay-erasures --since <T minus 10 minutes> --dry-run
   python -m app.privacy.cli replay-erasures --since <T minus 10 minutes>
   ```
   Default source is the blob log (`--source storage`); `--source db` reads the table, and
   `--source erasures.jsonl` the file from step 2. The command prints one JSON line
   (`applied`, `already_erased`, `unknown`, `errors`, `failed_events`) and exits 1 if any event
   failed; fix and re-run, it is idempotent. Subtract ten minutes from T so clock skew cannot hide
   an event; events before T are simply reported as already erased.
7. **Check** that each erased client is a tombstone: `select display_name, erased_at from client
   where erased_at is not null` shows "Erased client", and for an id from the log
   `select count(*) from birth_record where client_id = '<id>'` is 0.
8. **Bring services back**: scale api and worker up, wait for `/health/ready`, run the smoke test,
   watch the Grafana or workbook error panel for 15 minutes. Job rows from after T are gone: a
   report requested between T and the incident simply has to be requested again; reminders are
   recomputed by the scheduler.
9. **Afterwards**: keep the old server for the incident review (it is the only copy of data between
   T and the incident), then delete it. If the old server held data of a practice that was deleted
   after T, that deletion is in the replay, so deleting the old server is also what erases the old
   copy: do it within your backup retention window and say so in the notice.

Anything written between T and the incident (new clients, notes, consents) is lost by design;
export what you can from the old server before deleting it. Consent receipts are append-only and
signed, so a restored database still verifies them.

Tested: `tests/pg/test_erasure_replay.py` (restore simulated with a database copy at time T, then
erasures, then replay: erased client erased even though the backup held it under legal hold, other
client untouched, practice deletion replayed with key destruction, idempotent, CLI from file and
storage) and a manual `pg_dump -Fc` / `pg_restore` round trip on the docker-compose database:
restore 8.5 s for a 10 MB dump of the load-test data, replay applied the one logged erasure, a
second replay reported it as already erased.

## 2. Monitoring

Metrics are OpenTelemetry (`services/api-py/src/app/metrics.py`), exported by the api and the
worker. Nothing leaves the process unless an exporter is configured:

* `APPLICATIONINSIGHTS_CONNECTION_STRING` (Azure, set by Bicep): metrics go to the `AppMetrics`
  table of the Log Analytics workspace, requests to `AppRequests`.
* `OTEL_EXPORTER_OTLP_ENDPOINT` (any collector, Grafana Alloy, Prometheus via the collector).
* `ANKANA_METRICS=0` turns metrics off; `ANKANA_METRICS_INTERVAL_SECONDS` (default 30).

| Metric | Type | Attributes | Why |
|---|---|---|---|
| `ankana.http.request.duration` | histogram, ms | method, route template, status class | latency and error rate; no ids in labels |
| `ankana.jobs.queue_depth` | gauge | kind | ready jobs waiting |
| `ankana.jobs.oldest_queued_age` | gauge, s | kind | stuck or saturated workers |
| `ankana.jobs.failed_recent` | gauge | kind | terminal failures in 24 h |
| `ankana.jobs.duration` | histogram, s | kind, outcome | handler run time |
| `ankana.report.render.duration` | histogram, s | outcome | PDF render time |
| `ankana.ai.tokens`, `ankana.ai.cost_usd`, `ankana.ai.requests` | counters | provider, model, type | AI use and estimated cost per provider |
| `ankana.notifications.failures` | counter | channel, final | reminder delivery |
| `ankana.auth.events` | counter | action | sign-in failures, blocks, refresh-token reuse |
| `ankana.ratelimit.decisions`, `ankana.ratelimit.fallbacks` | counters | scope, result | limiter behaviour |

No practice, client or user identifier is ever an attribute (cardinality and DPDP); a unit test
guards this. The queue gauges are read from the `job` table, at most every 5 seconds.

### Dashboards and alerts (`infra/monitoring/`)

* `workbook.json`: Azure Monitor workbook (Application Insights, workspace based). Import:
  Azure portal, Monitor, Workbooks, New, Advanced editor, paste, Apply, Save. SLO table, latency,
  error rate, slowest routes, queue, render, AI tokens and cost, notifications, sign-in watch,
  rate limiter.
* `grafana-dashboard.json`: same panels on Prometheus (import in Grafana, pick the Prometheus data
  source). Metric names assume the default OTel to Prometheus translation
  (`ankana_http_request_duration_milliseconds_bucket`, `ankana_ai_cost_USD_total`, ...); check the
  names your collector emits if a panel is empty. Collector sketch:
  ```
  receivers: { otlp: { protocols: { http: {} } } }
  exporters: { prometheus: { endpoint: 0.0.0.0:9464 } }
  service: { pipelines: { metrics: { receivers: [otlp], exporters: [prometheus] } } }
  ```
* `alerts.bicep`: scheduled query rules on the Log Analytics workspace. Wired into
  `infra/azure/modules/stack.bicep` (`alertEmail` parameter creates an action group; empty creates
  the rules without notifications). Deploy alone with
  `az deployment group create -g <rg> -f infra/monitoring/alerts.bicep -p name=ankana-prod-cin workspaceId=<id> alertEmail=<mail>`.

| Alert | Fires when | Severity |
|---|---|---|
| API 5xx error rate | more than 1 % of 50+ requests in 10 min (SLO 0.5 %) | 1 |
| API p95 latency | p95 over 800 ms, 50+ requests in 10 min (AI answers and downloads excluded) | 2 |
| Job queue backing up | oldest ready job older than 300 s | 2 |
| Jobs failing terminally | 3+ failed in 24 h (per kind) | 2 |
| Sign-in failures spiking | 50+ failed or blocked sign-ins in 5 min, or any refresh-token reuse | 1 |
| Notification sends failing | 10+ failures in 15 min | 3 |
| Rate limiter lost its store | any fallback to the per-process limiter in 10 min | 3 |

Thresholds are parameters of `alerts.bicep`. The Azure exporter reports counters as deltas, so the
rules sum them over the window; with another exporter keep delta temporality for the same effect.
The bicep compiles (`az bicep build`); like the rest of `infra/azure` it has not been deployed.

## 3. Rate limiting

Public and abusable endpoints use one shared limiter, `app/ratelimit.py`, with counters in Postgres
(`rate_limit_bucket`, migration `0007_rate_limit`), so the limit holds across replicas and
restarts (the per-process limiter it replaced gave each replica its own budget).

| Scope | Endpoints | Limit |
|---|---|---|
| `locations_search` | `GET /v1/locations/search` (and the legacy `/api/v1/locations/search`, same budget) | 30 per minute per caller. Closes security review finding D2. |
| `public_read` | legacy `GET /api/v1/panchang/today` | 120 per minute per caller |
| `public_link_ip`, `public_link_token` | reminder links `/v1/public/checkin/*`, `/v1/public/stop/*` | 30 per minute per IP, 6 per minute per token |
| sign-in, OTP | `/v1/auth/*` | unchanged: counted from `auth_event` in Postgres (already shared) |

Sliding-window counter: one statement per request upserts the current window and weights the
previous one. The caller is the client IP; behind the ingress set `AUTH_TRUST_PROXY=1` (the last
`X-Forwarded-For` hop, the one the ingress appended) or every caller is the proxy. Keys are hashed
before storage. If Postgres is unreachable the limiter falls back to an in-process window (not to
"allow all") and counts `ankana.ratelimit.fallbacks`. Rows older than a day are pruned
opportunistically; `ratelimit.prune(engine)` does it on demand. A limited request gets 429 with
`Retry-After`.

## 4. Key rotation and other routines

See `docs/privacy.md` (rotate-master, rotate-data, rotate-ai-keys). `rotate-data` now also covers
the encrypted free-text columns (remedy instructions, check-in notes, consultation topics, consent
notice text, notification subject and body).
