# Deploying Ankana (CI, Azure Central India)

Everything here is code in the repo. Nothing has been deployed and no Azure resource exists until you run the steps in "What you must do manually" (section 5).

## 1. Licence and source obligation (read first)

Ankana is AGPL-3.0-only and computes charts with Swiss Ephemeris. Section 13 means every user of the deployed service must be able to get the source of the exact version running.

- The **deployed source must stay public** at https://github.com/mrigankad/Ankana, including every modification that runs in production (ephemeris handling, Lal Kitab rules, AI assistant code, these infra files). Do not deploy from a private fork or a branch that is not pushed publicly.
- The images and Container Apps carry `ANKANA_GIT_SHA`, `ANKANA_SOURCE_URL`, `NEXT_PUBLIC_GIT_SHA` and `NEXT_PUBLIC_SOURCE_URL`. The deploy workflow sets them to the commit being deployed and the URL above so the app can show a "Source code" link. The commit must exist in the public repo.
- Secrets (API keys, connection strings) and client data are not source and stay private.

## 2. CI (`.github/workflows/ci.yml`)

| Job | What it does |
|---|---|
| `ts` | pnpm install `--frozen-lockfile`, Prisma generate, `pnpm -r lint` (tsc), `pnpm -r test` (vitest). Builds `services/api-py/.venv` with pyswisseph so the Node reading bridge test runs. |
| `python` | uv, ruff, pytest with a `postgres:16` service container (`API_TEST_ADMIN_URL`), so `tests/pg` (RLS, tenancy) run for real. pyswisseph and the Swiss data files (`scripts/fetch_ephe.py`) are installed, and a step fails the job if any swiss or Postgres test is skipped. Also applies alembic as the owner role. |
| `lal-kitab-parity` | `tests/test_lal_kitab_parity.py` and adapter tests against the TS golden fixture. |
| `eval` | `python -m ankana_ai.eval` with the deterministic `MockProvider`; non-zero exit on any shipped error or refusal recall below 1.0. Uploads `eval-summary.json`. |
| `e2e` | Playwright (after `ts`). |

Caching: pnpm store (setup-node), uv cache, and the Swiss data files (`actions/cache`).

Environment: CI needs no secrets. It sets `LOCATION_PROVIDER=static`, `OLLAMA_MOCK=1`, `REPORT_RENDERER=stub` and `ANKANA_SE_EPHE_PATH`. Do not add `ANTHROPIC_API_KEY` to CI; live evals (`--live`) are a manual, budget-capped run.

Lint config: ruff rules are pinned in `services/api-py/pyproject.toml` (`E,F,W,I,UP,B`, with E501, B905 and B008 ignored for stated reasons) so a ruff upgrade cannot suddenly add findings.

## 3. Architecture deployed

```
Internet -> Container Apps env (VNet, Central India)
              web (Next.js, :3000)   api (FastAPI, :8000)   worker (same image)   migrate job
                                        | private endpoints / delegated subnet
        Postgres Flexible Server 16   Azure Cache for Redis   Storage (private 'reports')   Key Vault
Observability: OpenTelemetry -> Application Insights (Log Analytics), Sentry optional
```

Files: `infra/azure/main.bicep` (subscription scope, creates `rg-ankana-<env>-cin`), `modules/` (monitoring, network, security, data, apps), `parameters/staging.bicepparam` and `prod.bicepparam`, `scripts/` (`bootstrap-secrets.sh`, `set-secret.sh`, `run-job.sh`). Images: `infra/docker/api.Dockerfile`, `web.Dockerfile`.

- **Network**: VNet with subnets for Container Apps, Postgres (delegated) and private endpoints. Postgres, Redis, Storage and Key Vault have public access disabled; private DNS zones are linked to the VNet.
- **Identities**: one user-assigned identity per workload. All can pull from ACR (no admin user). api and worker get Blob Data Contributor on the storage account and read access to individual Key Vault secrets only (table in section 4). The storage account has no account key; report downloads are 15 minute read-only user-delegation SAS URLs the browser opens directly, so its blob endpoint is reachable from the internet (anonymous access is off, only Entra-signed SAS works) while the apps use the private endpoint. Only the migration identity can read `db-migration-url` (the owner connection string). The app connection string (`db-app-url`) uses the RLS-bound `ankana_app` role, which has no superuser or BYPASSRLS.
- **Migrations**: Postgres has no public endpoint, so a runner cannot reach it. The workflow starts a Container Apps job (`caj-...-migrate`) that runs `alembic upgrade head` as the owner role and then `scripts/set_app_role_password.py`, which gives `ankana_app` its login password.
- **Ephemeris**: the API image downloads `sepl_18/semo_18/seas_18.se1` at build time to `/opt/ephe` (`ANKANA_SE_EPHE_PATH`) and fails the build if any is missing. Without them pyswisseph silently falls back to lower-accuracy Moshier.
- **Observability** (`services/api-py/src/app/observability.py`): logs are JSON with `practice_id`; traces go to Application Insights when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set (or any OTLP collector via `OTEL_EXPORTER_OTLP_ENDPOINT`). No request bodies, query strings, names or birth data leave the process (span scrubber, deny-list; tested in `tests/test_observability.py`). Sentry turns on only when the `sentry-dsn` Key Vault secret holds a real DSN; `send_default_pii` is off.
- **Worker**: `ca-...-worker` runs `python -m app.worker` from the same image (`workerEnabled: true` in both parameter files, min 1 replica, 1 vCPU and 2 GiB because it runs Chromium). It processes PDF reports, privacy export and erase jobs and reminder sends, and every `NOTIFY_TICK_SECONDS` (300) enqueues the notification tick that finds due reminders.
- **Release gate**: stage 2a deploys only the migrate and preflight jobs; the `Preflight` step must pass before migrations and before the api, worker and web revisions (stage 2b) are created.

## 4. Production environment: what each app needs

`python -m app.preflight --role api|worker|migrate` (`services/api-py/src/app/preflight.py`) is the single source of truth for this table. It checks every variable below, prints all problems at once (names only, never values) and exits 1. It runs in four places: the image entrypoint when `ANKANA_ROLE` is set (the container exits before starting), `GET /health/ready` (the api readiness and startup probe, 503 until complete), the `caj-...-preflight` Container Apps job that `deploy.yml` runs before any revision is rolled out, and by hand.

Legend: **S** = secret (Key Vault, read by that app's managed identity only), **C** = plain config (set in `modules/apps.bicep` from `parameters/*.bicepparam` or derived). Req = preflight fails if missing or invalid; Opt = optional, a warning at most. The `web` app (Next.js) holds no secrets: only build-time `NEXT_PUBLIC_*` values (API base URL, `NEXT_PUBLIC_AUTH_MODE=builtin`, git sha, source URL) baked by `deploy.yml`, plus runtime `WEB_ORIGIN`.

| Variable | Kind | api | worker | migrate | Value and source |
|---|---|---|---|---|---|
| `API_ENV` | C | Req | Req | | `production`. Turns on every production guard (no dev keys, no console mailer, no legacy API, CORS regex off). |
| `ANKANA_ROLE` | C | Req | Req | Req | `api`, `worker`, `migrate`. Makes the entrypoint run the preflight. |
| `API_DATABASE_URL` | S `db-app-url` | Req | Req | | RLS-bound `ankana_app` URL, built by `data.bicep`. |
| `API_MIGRATION_URL` | S `db-migration-url` | | | Req | Owner URL. Only the migrate identity can read it. |
| `APP_ROLE_PASSWORD` | S `db-app-password` | | | Req | Sets the `ankana_app` login password. |
| `REDIS_URL` | S `redis-url` | Opt | Opt | | Wired for the queue and rate limit work; no code reads it yet. |
| `AUTH_SIGNING_KEY_PEM` | S `auth-signing-key-pem` | Req | | | Ed25519 PKCS8 PEM, generated once by `bootstrap-secrets.sh`. Rotation: `AUTH_SIGNING_KEY_PREVIOUS_PEM`. |
| `AUTH_BUILTIN_ISSUER` | C | Req | | | Public api origin (https). Token `iss`, OIDC callback host. Derived from `API_CUSTOM_DOMAIN`, else the default Container Apps host. |
| `AUTH_WEB_BASE_URL` | C | Req | | | Public web origin (https). Invite links and redirects. From `WEB_CUSTOM_DOMAIN` or the default host. |
| `AUTH_ALLOWED_ORIGINS` | C | Req | | | Web origin(s), CORS and CSRF origin check. Must include `AUTH_WEB_BASE_URL`. |
| `AUTH_COOKIE_SECURE` | C | Req | | | `1`. `AUTH_COOKIE_DOMAIN` only if web and api need a shared cookie across subdomains. |
| `AUTH_TRUST_PROXY` | C | Opt | | | `1` behind Container Apps ingress so rate limits use the real client IP. Set by `apps.bicep`; preflight warns on the api when it is missing, because the shared per-IP limiters (public reminder links, `/v1/locations/search`, sign-in) would then treat every caller as the proxy. |
| `AUTH_MAILER` | C | Req | | | `acs` (or `smtp`; `console` is refused). |
| `AUTH_MAIL_FROM` | C | Req | | | `Ankana <address>`; address from `MAIL_FROM_ADDRESS`, a verified ACS sender. |
| `ACS_EMAIL_CONNECTION_STRING` | S `acs-connection-string` | Req | | | Sign-in codes and invites. Same secret as `ACS_CONNECTION_STRING`. Entered by you. |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` `SMTP_STARTTLS` | S/C | Opt | Opt | | Only for `smtp` instead of ACS (not wired in Bicep). |
| `AUTH_SMS` | C | Opt | | | `none`. Only a console sender ships; `console` is ignored in production, so phone codes are off. |
| `AUTH_OIDC_PROVIDERS`, `AUTH_OIDC_<NAME>_ISSUER/_CLIENT_ID/_CLIENT_SECRET/_LABEL/_SCOPES` | S/C | Opt | | | Google, Keycloak, etc. A half-configured provider is hidden (preflight warns). Not wired in Bicep: add env and a secret when you want one. |
| `AUTH_SIGNUP_ENABLED`, `AUTH_PASSWORD_*`, `AUTH_ACCESS_TTL_SECONDS`, `AUTH_REFRESH_*`, `AUTH_INVITE_TTL_DAYS` | C | Opt | | | Defaults are production-safe. `signupEnabled` in `appConfig`. |
| `AUTH_JWKS_URL` `AUTH_ISSUER` `AUTH_AUDIENCE` `AUTH_ALGORITHMS` | C | Opt | | | Only to also accept an external IdP's tokens. `AUTH_DEV_STUB` must stay off (preflight fails if set). |
| `ANKANA_SECRET_KEY` | S `ankana-secret-key` | Req | Req | | 24+ random chars. Encrypts stored AI provider keys (Fernet seed). Never regenerate. Rotation CLI: `ANKANA_SECRET_KEY_OLD`. |
| `ANKANA_MASTER_KEY` | S `ankana-master-key` | Req | Req | Req | base64 of 32 bytes. Wraps per-practice data keys (privacy envelope). Never regenerate. `ANKANA_MASTER_KEY_ID` (`env-1`), `ANKANA_MASTER_KEY_PREVIOUS` (`id:base64,...`) for rotation. |
| `ANKANA_KEYVAULT_KEY_ID` | C | Opt | Opt | | Key Vault RSA key URL instead of `ANKANA_MASTER_KEY`. The image has `azure-keyvault-keys`; grant the identity Key Vault Crypto User and a data-plane route. Not the default. |
| `STORAGE_BACKEND` | C | Req | Req | | `azure`. `local` is refused: the worker writes the PDF, the api serves it, different containers. |
| `AZURE_STORAGE_ACCOUNT_URL` | C | Req | Req | | `https://<account>.blob.core.windows.net`, derived. |
| `AZURE_STORAGE_CONTAINER` | C | Req | Req | | `reports` (private). |
| `AZURE_CLIENT_ID` | C | Req | Req | | The app's user-assigned identity client id, so `DefaultAzureCredential` picks it. Roles: Blob Data Contributor (includes the user-delegation key). |
| `STORAGE_SIGNING_KEY` | S | | | | `local` backend only; not provisioned. |
| `NOTIFY_LINK_SECRET` | S `notify-link-secret` | Req | Req | | 24+ chars, HMAC for one-tap check-in and stop links. Generated once. |
| `NOTIFY_PUBLIC_BASE_URL` | C | Req | Req | | Public api origin (links in reminders). |
| `NOTIFY_EMAIL_BACKEND` | C | Req | Req | | `acs`. `console` only logs, so preflight refuses it. |
| `ACS_CONNECTION_STRING`, `ACS_EMAIL_FROM` | S `acs-connection-string`, C | Req | Req | | Reminder email via the `azure-communication-email` SDK (in the image). |
| `NOTIFY_WHATSAPP_BACKEND`, `NOTIFY_SMS_BACKEND` | C | Opt | Opt | | `console` only; no real adapter ships (preflight warns). |
| `NOTIFY_TICK_SECONDS` | C | | Opt | | Worker enqueues the reminder tick this often (300). |
| `WORKER_CONCURRENCY` `WORKER_POLL_SECONDS` `WORKER_VISIBILITY_SECONDS` | C | | Opt | | 2 (caps Chromium instances), 1.0, 900. |
| `ANKANA_BILLING` | C | Opt | Opt | | `off` (default, unlimited usage, `/v1/billing` is 404) or `on`. |
| `RAZORPAY_KEY_ID` `RAZORPAY_KEY_SECRET` `RAZORPAY_WEBHOOK_SECRET` | S | Req if billing on | | | Blank placeholders while billing is off. Register `<api>/v1/billing/webhooks/razorpay` in Razorpay. Plans: `RAZORPAY_PLAN_<KEY>_<INTERVAL>` optional. |
| `ANKANA_BILLING_PROVIDER` | C | Req if on | | | `razorpay` when billing is on (never the mock). |
| `ANKANA_SUPPLIER_NAME` `_GSTIN` `_STATE_CODE` `_ADDRESS` `_EMAIL` | C | Req if on | | | Invoice supplier, from `appConfig`. |
| `ANKANA_BILLING_GRACE_DAYS`, `ANKANA_PLANS_FILE` | C | Opt | | | 7 days; custom plan catalogue. |
| `ANKANA_AI_PROVIDER` | C | Opt | Opt | | `anthropic` (default in Bicep). `mock` is refused in production. |
| `ANTHROPIC_API_KEY` | S `anthropic-api-key` | Req when provider is `anthropic` | Same | | Entered by you. Required while `aiProvider` in `appConfig` is `anthropic` (the default). |
| `ANKANA_ALLOW_LOCAL_PROVIDERS` | C | Req `0` | Req `0` | | Must be off when hosted: it lets tenants run local CLI providers in the container. |
| `OLLAMA_BASE_URL` `OLLAMA_API_KEY` `OLLAMA_MODEL` | C/S | Opt | Opt | | Only if `ANKANA_AI_PROVIDER=ollama`. |
| `ANKANA_EPHEMERIS` | C | Req | Req | | `swiss`. |
| `ANKANA_SE_EPHE_PATH` | C | Req | Req | | `/opt/ephe` (baked into the image; preflight checks the three `.se1` files exist). `ANKANA_AYANAMSA_MEAN` optional. |
| `LAL_KITAB_DATA_DIR` | C | Opt | Opt | | `/opt/lal-kitab-data` (image default). |
| `ANKANA_GIT_SHA` `RELEASE_SHA` `ANKANA_SOURCE_URL` | C | Opt | Opt | | AGPL source link; set by the deploy from the commit. Preflight warns if missing. |
| `ANKANA_LEGACY_API` | C | Req off | | | `0`. The unauthenticated SQLite `/api/v1` surface stays off. |
| `API_CORS_ORIGINS` | C | Opt | | | Extra CORS origins beyond `AUTH_ALLOWED_ORIGINS`. |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | S | Opt | Opt | | Traces to Application Insights. Created by Bicep. Preflight warns if absent; when set, preflight requires the `observability` extra (`opentelemetry-sdk`, `azure-monitor-opentelemetry-exporter`, installed by `infra/docker/api.Dockerfile`) so metrics export. |
| `ANKANA_METRICS` | C | Opt | Opt | | `0` keeps traces but skips OpenTelemetry metrics export. Default on. |
| `ANKANA_METRICS_INTERVAL_SECONDS` | C | Opt | Opt | | Metric export interval, default 30. |
| `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE` | S | Opt | Opt | | Blank placeholder keeps Sentry off. |
| `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `LOG_LEVEL` | C | Opt | Opt | | Service name is set per app. |
| `REPORT_RENDERER` | C | | | | Leave unset (Chromium PDF). `stub` is for CI only. |

Not read in production (ignore): `AUTH_DEV_KEY_PATH`, `AUTH_SIGNING_KEY_FILE` (works, but Key Vault to env is the supported path), `STORAGE_LOCAL_DIR`, `STORAGE_PUBLIC_BASE_URL`, `ANKANA_CLAUDE_BIN` and the other CLI provider paths, `LOCATION_PROVIDER`, `WEB_BASE_URL` and `DATABASE_URL` (legacy Node API in `apps/api`, not deployed).

### Which identity reads which Key Vault secret

Role assignments are per secret (Key Vault Secrets User), in `modules/data.bicep`:

| Secret | api | worker | migrate |
|---|---|---|---|
| `db-app-url`, `redis-url`, `appinsights-connection-string` | yes | yes | |
| `ankana-secret-key`, `ankana-master-key`, `notify-link-secret`, `anthropic-api-key`, `acs-connection-string`, `sentry-dsn` | yes | yes | |
| `auth-signing-key-pem`, `razorpay-key-id`, `razorpay-key-secret`, `razorpay-webhook-secret` | yes | | |
| `db-migration-url`, `db-app-password` | | | yes |

Bicep owns `db-*`, `redis-url` and `appinsights-connection-string`. `scripts/bootstrap-secrets.sh` owns the rest and only ever creates them when absent, so a redeploy cannot overwrite a signing key, an encryption key or a value you typed. (Before this change Bicep re-wrote `sentry-dsn` and `anthropic-api-key` as a single space on every deploy, which wiped any real value.)

## 5. What you must do manually

1. **Azure subscription**: create one (Startups credits if eligible). Register providers: `Microsoft.App`, `Microsoft.ContainerRegistry`, `Microsoft.DBforPostgreSQL`, `Microsoft.Cache`, `Microsoft.KeyVault`, `Microsoft.Storage`, `Microsoft.OperationalInsights`, `Microsoft.Insights`, `Microsoft.Network`, `Microsoft.Communication`. Check quota for Container Apps and Postgres `Standard_D2ds_v5` in Central India, and that zone-redundant HA is available there (otherwise set `pgHa: false` in `prod.bicepparam`).
2. **OIDC app registration** (no secret stored in GitHub):
   ```
   az ad app create --display-name ankana-github-deploy
   az ad sp create --id <appId>
   # one federated credential per GitHub environment
   az ad app federated-credential create --id <appId> --parameters '{
     "name":"gh-staging","issuer":"https://token.actions.githubusercontent.com",
     "subject":"repo:mrigankad/Ankana:environment:staging","audiences":["api://AzureADTokenExchange"]}'
   # repeat with environment:prod
   ```
   The deployment creates resource groups and role assignments, so grant the service principal **Owner** (or Contributor plus User Access Administrator) on the subscription. Tighten to the resource groups after the first deploy if you prefer.
3. **Email sender** (needed for sign-in codes, invites and reminders). In the portal create Azure Communication Services plus an Email Communication Service, add and verify a domain (or use the free `azurecomm.net` domain for staging), connect the domain to the Communication Service, and note the sender address (for example `DoNotReply@<guid>.azurecomm.net` or `no-reply@your.domain`) and the Communication Service connection string (Keys blade).
4. **GitHub environments** `staging` and `prod` (add required reviewers on `prod`):
   - variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `MAIL_FROM_ADDRESS` (the verified sender), optional `WEB_CUSTOM_DOMAIN` and `API_CUSTOM_DOMAIN` (full `https://` origins; see step 8, set both or neither)
   - secrets: `PG_ADMIN_PASSWORD`, `PG_APP_PASSWORD` (long random values, 32+ chars; the Bicep URL-encodes them)
5. **First deploy** (staging): Actions, "Deploy (Azure)", `staging`. It creates the infrastructure, generates the Key Vault secrets (signing key, `ANKANA_SECRET_KEY`, `ANKANA_MASTER_KEY`, `NOTIFY_LINK_SECRET`), builds both images and deploys the jobs. **The first run is expected to stop at the "Preflight" step**, listing `ANTHROPIC_API_KEY` and `ACS_CONNECTION_STRING` as missing. That is the preflight doing its job; nothing was rolled out.
6. **Enter the two secrets you own.** Key Vault is private-only, so these scripts use the Azure Resource Manager API and work from your laptop (Git Bash, WSL or Cloud Shell; they need `az`, `jq`). The value is read from a hidden prompt:
   ```
   infra/azure/scripts/set-secret.sh rg-ankana-staging-cin <kv-name> anthropic-api-key
   infra/azure/scripts/set-secret.sh rg-ankana-staging-cin <kv-name> acs-connection-string
   ```
   `<kv-name>` is the `keyVaultName` output of the first run (also in the portal). Optional: `sentry-dsn`, and for billing `razorpay-key-id`, `razorpay-key-secret`, `razorpay-webhook-secret` the same way. Then re-run "Deploy (Azure)": preflight passes, migrations run, api, worker and web roll out and the smoke test checks `/health` and `/health/ready`.
7. **Back up the two encryption keys now.** If `ankana-master-key` or `ankana-secret-key` is lost, encrypted client data and stored AI connections cannot be recovered, and they are not shown anywhere else. Give yourself data-plane read, open the vault briefly, copy both into your password manager, then close it (the next Bicep deploy also resets the vault to private-only):
   ```
   az role assignment create --assignee <your-object-id> --role "Key Vault Secrets User" --scope $(az keyvault show -n <kv-name> --query id -o tsv)
   az keyvault update -n <kv-name> --public-network-access Enabled
   az keyvault secret show --vault-name <kv-name> -n ankana-master-key --query value -o tsv
   az keyvault secret show --vault-name <kv-name> -n ankana-secret-key --query value -o tsv
   az keyvault update -n <kv-name> --public-network-access Disabled
   ```
   Do the same for `auth-signing-key-pem` if you want a recovery copy (losing it only signs everyone out).
8. **Domains and TLS (do before production).** The default `*.azurecontainerapps.io` hosts are cross-site to each other, so the `SameSite=Lax` refresh cookie is not sent between web and api and sign-in will not persist. Use custom domains under one registrable domain, for example `app.your.domain` (web) and `api.your.domain` (api): add them to the two apps (managed certificates), then set the `WEB_CUSTOM_DOMAIN` and `API_CUSTOM_DOMAIN` variables and re-run the workflow (it rebuilds the web image with the api URL baked in). Add Front Door or Cloudflare for edge rate limits before public launch.
9. **Production**: repeat steps 5 and 6 with `prod` (separate Key Vault, separate secrets). Confirm the Postgres HA and backup settings, test a point-in-time restore once, and review log retention and geo-redundancy against your DPDP position (geo-redundant backup is off so data stays in India).
10. **Optional sign-in providers and billing**: external OIDC (Google and others) and Razorpay are off until you add their env (see the table). Billing: set `billing: 'on'` and the `supplier*` fields in the bicepparam `appConfig`, enter the three Razorpay secrets, redeploy.
11. **Messaging (email, WhatsApp, SMS)**: one package, `app/messaging`, serves sign-in codes and reminders. Pick a backend per channel; the console backend only logs and is refused for SMS and WhatsApp when `API_ENV=production` (set `off` to disable a channel; sends then fail visibly in the outbox). The worker also checks this at start-up.

   | Variable | Meaning |
   |---|---|
   | `NOTIFY_EMAIL_BACKEND` | `console` (default), `smtp`, `acs`. Sign-in mail uses `AUTH_MAILER` (same backends) |
   | `NOTIFY_EMAIL_FROM` | From address for reminder mail (SMTP) |
   | `ACS_EMAIL_CONNECTION_STRING`, `ACS_EMAIL_FROM` | Azure Communication Services email (`ACS_CONNECTION_STRING` also accepted). `ACS_EMAIL_USE_SDK=1` sends through the `azure-communication-email` SDK (install the optional extra: `pip install '.[azure-email]'`); default is the built-in signed REST call |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_STARTTLS` | SMTP |
   | `NOTIFY_WHATSAPP_BACKEND` | `console`, `meta`, `gupshup`, `off` |
   | `WHATSAPP_CLOUD_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | Meta Cloud API: permanent system-user token and the phone number id |
   | `WHATSAPP_GRAPH_VERSION` | Graph API version, default `v21.0` |
   | `WHATSAPP_APP_SECRET` | Meta app secret; verifies `X-Hub-Signature-256` on the webhook |
   | `WHATSAPP_VERIFY_TOKEN` | Any long random string you also type into Meta's webhook setup (GET handshake) |
   | `WHATSAPP_TEMPLATES` | JSON, kind to language to template: `{"remedy_due":{"en":{"name":"remedy_due_en","language":"en","id":"<gupshup template uuid>"},"hi":{...}}}`. Kinds: `remedy_due`, `remedy_missed`, `ending_soon`, `plan_complete`, `followup_due`. A missing kind or language falls back to English, then to a session text message |
   | `GUPSHUP_API_KEY`, `GUPSHUP_SOURCE`, `GUPSHUP_APP_NAME`, `GUPSHUP_WEBHOOK_TOKEN` | Gupshup alternative; the webhook URL carries `?token=<GUPSHUP_WEBHOOK_TOKEN>` |
   | `NOTIFY_SMS_BACKEND` | `console`, `msg91`, `twilio`, `off` |
   | `MSG91_AUTH_KEY`, `MSG91_SENDER_ID` | MSG91 auth key and the DLT-registered 6 letter header |
   | `MSG91_DLT_TEMPLATE_ID` | Default DLT template id; `MSG91_DLT_TEMPLATES` is JSON kind to template id (`{"otp":"...","remedy_due":"..."}`) |
   | `MSG91_WEBHOOK_TOKEN` | Delivery-report URL carries `?token=<value>` |
   | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM` or `TWILIO_MESSAGING_SERVICE_SID` | Twilio; `TWILIO_STATUS_CALLBACK_URL` is the public webhook URL (optional) |
   | `MESSAGING_PUBLIC_BASE_URL` | Public API origin, used to rebuild the URL Twilio signed when the API sits behind a proxy |
   | `MESSAGING_DEFAULT_COUNTRY_CODE` | Added to bare 10 digit numbers, default `91` |

   Webhooks (public, fail closed with 403 or 503): `GET/POST /v1/webhooks/whatsapp/meta`, `POST /v1/webhooks/whatsapp/gupshup?token=`, `POST /v1/webhooks/sms/twilio`, `POST /v1/webhooks/sms/msg91?token=`. They record `delivery_status` (`sent`, `delivered`, `read`, `failed`) with `delivered_at`, `read_at` and `delivery_error` on the notification outbox, and treat a reply of STOP, UNSUBSCRIBE, CANCEL, END, QUIT (or the Hindi equivalents) as an opt-out: that channel is switched off for the client, pending sends on it are cancelled, and the `reminders` consent is withdrawn once no channel is left. Run `alembic upgrade head` (migration `0005_messaging`).

   **WhatsApp template approval (Meta).** Business-initiated messages need an approved template; free text works only within 24 hours of the client's last message. Create one template per kind and language in WhatsApp Manager, category UTILITY, body text containing exactly one variable, for example `Namaste, a gentle reminder from your practitioner: {{1}}` (the app puts the rendered reminder, folded to one line, into `{{1}}`). Approval usually takes minutes to a day; rejected templates are fixed and resubmitted. Hindi needs its own template in language `hi`. Marketing content must use a marketing template and needs explicit opt-in.

   **SMS in India (TRAI DLT).** Operators deliver only registered traffic. Register the entity (principal entity) on a DLT portal (Jio, Airtel, Vi, BSNL), register the sender header (`MSG91_SENDER_ID`), then register each content template (service-implicit or transactional for reminders and codes) with `{#var#}` placeholders. The text we send must match the registered template apart from variables, or the operator drops it. The DLT template id goes on every request (`MSG91_DLT_TEMPLATE_ID`, or per kind in `MSG91_DLT_TEMPLATES`; sign-in codes use kind `otp`). Twilio to Indian numbers is subject to the same DLT rules. Promotional SMS may only go out 10:00 to 21:00 and not to NDNC numbers; this product sends service messages only.

   **Quiet hours.** Reminders are scheduled outside the client's quiet window (default 21:00 to 07:00 practice-local time) and SMS or WhatsApp sends that retry or queue into it are pushed to its end at send time.


### Ed25519 signing key (`auth-signing-key-pem`)

`bootstrap-secrets.sh` generates it for you. To make one by hand (rotation, or your own vault):

```
openssl genpkey -algorithm ed25519 > signing.pem          # PKCS8 PEM, unencrypted
python -c "from app.auth.keys import generate_pem; print(generate_pem())"   # same thing, from services/api-py/src
```

Store it with `set-secret.sh <rg> <kv> auth-signing-key-pem < signing.pem`, then delete the local file. Rotation: put the current PEM in the secret `AUTH_SIGNING_KEY_PREVIOUS_PEM` (add the env var and secret), generate a new `auth-signing-key-pem`, redeploy, and remove the previous key after one access-token lifetime (15 minutes by default).

## 6. Authentication notes

Built in, no SaaS provider needed. The API signs its own short-lived EdDSA access tokens, publishes `/.well-known/jwks.json` and `/.well-known/openid-configuration`, and keeps rotating, hashed refresh tokens in Postgres. Register `<AUTH_BUILTIN_ISSUER>/v1/auth/oidc/callback` as the redirect URI for any external provider. Phone codes use the `SmsSender` interface in `app/auth/mailer.py`; only a console sender ships, so SMS sign-in stays off until an MSG91 or Twilio adapter is added. Migration `0003_auth_builtin` adds the auth tables; the deploy runs `alembic upgrade head` before the api rolls out.

## 7. Day-to-day

- Deploy: Actions, "Deploy (Azure)", pick environment. Order: infra, Key Vault bootstrap, images, stage 2a (jobs), **preflight**, migrations, stage 2b (api, worker, web), smoke test of `/health` and `/health/ready`. Images are tagged with the commit sha.
- A revision that fails preflight never serves: the entrypoint exits with the problem list (see the revision console log) and `/health/ready` answers 503, so Container Apps keeps the previous revision.
- Roll back: re-run the workflow on an older commit (images for it remain in ACR). Migrations are forward-only and now run before the new api revision, so ship schema changes as expand then contract.
- Change a secret: `set-secret.sh`, then re-run the workflow (a new revision re-reads Key Vault).
- Logs: Log Analytics (`ContainerAppConsoleLogs_CL`), traces in Application Insights. Filter by `practice_id`.
- Monitoring, alert rules, backup and restore (including erasure replay), rate limiting: `docs/operations.md`. Migrations `0006_encrypt_free_text`, `0007_rate_limit` and `0008_erasure_log` need no new variables; `0006` encrypts existing free text with the master key, so the migrate job now receives `ANKANA_MASTER_KEY` (and `API_ENV=production`) and its identity can read that one secret; preflight `--role migrate` fails without them. Before this, a migration that had rows to encrypt would have used the public development key.
- Legacy SQLite routes are off in production (`ANKANA_LEGACY_API=0`).

## 8. Cost estimate (USD per month, Central India)

These are my estimates from public list prices as I remember them, not fetched or quoted. Verify in the Azure pricing calculator before committing. INR billing and tax excluded.

| Item | Staging | Prod | Assumption |
|---|---|---|---|
| Postgres Flexible Server | 17 (B1ms, 32 GB) | 280 (D2ds_v5 zone-redundant HA, 128 GB) | prod roughly doubles for the standby |
| Redis | 16 (Basic C0) | 100 (Standard C1) | Basic has no replica |
| Container Apps | 0 to 10 | 60 to 120 | staging scale-to-zero inside the free grant; prod api min 2 x 1 vCPU, web min 1 |
| Private endpoints (4) + DNS zones | 31 | 31 | about 7.3 each plus 0.5 per zone, plus small data charges |
| Container Registry | 5 (Basic) | 20 (Standard) | |
| Log Analytics + App Insights | 0 to 5 | 20 to 40 | 5 GB/month free; prod about 10 GB/month |
| Storage | 1 | 3 | small PDFs only |
| Key Vault | 1 | 2 | few operations |
| **Total** | **about 70 to 90** | **about 520 to 620** | excludes LLM spend, email, domains, Front Door |

LLM cost per report and per assistant session will dominate at scale; track it separately. Staging can be stopped when idle (stop Postgres, delete Redis) to cut it to about 30. Azure Cache for Redis Basic/Standard has a published retirement path toward Azure Managed Redis; the Bicep uses the classic resource because that is what was asked for, so plan a swap before the retirement date.

## 9. Known limits

- Bicep compiles (`az bicep build`) but has never been deployed (the secret bootstrap, preflight job and stage split are untested against a real subscription): expect first-run fixes (quota, provider registration, region SKU availability, `az deployment sub create` combining a `.bicepparam` with inline overrides needs a recent Azure CLI).
- Key Vault secret references from Container Apps to a private-endpoint vault rely on the environment's VNet DNS; if the first revision cannot read secrets, check the `privatelink.vaultcore.azure.net` link first.
- No WAF or CDN yet, no autoscale on Postgres, single region.
