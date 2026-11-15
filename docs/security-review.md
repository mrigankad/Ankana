# Backend security and correctness review (services/api-py)

Scope: FastAPI app, tenancy/RLS, built-in auth, /v1 core API, reports + job queue + storage,
ankana_ai (providers, CLI providers, verifier, refusal gate), AI connections, alembic 0001..0004.
Branch `fix/backend-review`. Every fix has a regression test; the test column names it.

Severity: High = exploitable data exposure or takeover, Medium = needs a precondition,
Low = hardening. Status: fixed, accepted (reason given), decision (needs an owner call).

## Findings

| # | Sev | Area | Finding | Status | Test |
|---|-----|------|---------|--------|------|
| 1 | High | API surface | The legacy `/api/v1` routes (clients with names and birth data, audit events, dashboard, charts, the server-key `ask`) have no authentication and stay mounted when the tenant layer is on. | fixed: off when `API_ENV=production` with tenancy unless `ANKANA_LEGACY_API=1`; dev and tests unchanged | `tests/pg/test_legacy_gate.py` |
| 2 | High | SSRF | Hostname check at config time only. DNS rebinding, decimal/octal IPs (`https://2130706433`), CGNAT and IPv4-mapped IPv6 passed; the logo fetch resolved twice (check, then connect). | fixed: `ankana_ai/netguard.py` resolves once per request, refuses non-global addresses, connects to that IP with Host and SNI kept; used for the logo fetch and every hosted AI connection | `tests/test_netguard.py` |
| 3 | High | CLI providers | `claude`/`codex`/`gemini` children inherited the whole API environment (DB URL, signing key, `ANKANA_SECRET_KEY`, cloud keys); output was uncapped; model names were unvalidated (option injection, and `cmd.exe` metacharacters through Windows `.cmd` shims). | fixed: env allow-list, 4 MB stdout/stderr cap with kill, process-tree kill on timeout, model regex at API edge and in the provider, temp cwd for all three | `tests/test_cli_provider_hardening.py` |
| 4 | Medium | Auth | OTP resend cooldown was read from `auth_otp`, which only exists for real accounts: second request in 30 s returned 429 for known emails and 202 for unknown ones (account enumeration). | fixed: cooldown counted from `auth_event`, written for both | `test_resend_cooldown_does_not_reveal_whether_an_account_exists` |
| 5 | Medium | Auth | OIDC state was not bound to the browser (login CSRF: victim completes the attacker's flow and lands in the attacker's account). | fixed: hashed state in an httpOnly Lax cookie, checked in the callback | `test_oidc_callback_is_bound_to_the_browser_that_started_the_flow` |
| 6 | Medium | Auth | `/v1/auth/signout` revoked by session id alone; the id is in every access token. | fixed: refresh secret must match | `test_signout_needs_the_refresh_secret_not_just_the_session_id` |
| 7 | Medium | Auth | `POST /v1/practices` ignored `AUTH_SIGNUP_ENABLED=0`. | fixed | `test_practice_bootstrap_respects_signup_closed` |
| 8 | Medium | Auth | OIDC trusted the issuer from the discovery document, not the configured one. | fixed: must equal the configured issuer | `test_oidc_discovery_issuer_must_match_configuration` |
| 9 | Medium | Secrets | Key Vault placeholders are a single space (`infra/azure/modules/data.bicep`). A space `ANKANA_SECRET_KEY` or `STORAGE_SIGNING_KEY` was accepted as a real key: guessable Fernet key and forgeable download URLs. | fixed: blank counts as unset; production requires 24+ characters for both | `tests/test_storage.py` |
| 10 | Medium | Queue | `complete()`/`fail()` matched on id only: a worker reaped as lost could finish or fail the run that replaced it. | fixed: guarded on `status='running'` and the claimed attempt | `test_a_reaped_worker_cannot_finish_or_fail_...` |
| 11 | Medium | Reports | Two concurrent retries of a failed report enqueued two render jobs. | fixed: row lock on the retry path | `test_concurrent_retries_of_a_failed_report_enqueue_one_job` |
| 12 | Medium | DB | SECURITY DEFINER functions had `search_path = public` (pg_temp is searched first when not listed). | fixed: `public, pg_temp`, migration `0004_security_hardening` for existing databases | `test_security_definer_functions_pin_search_path_without_temp_first` |
| 13 | Medium | Mail | Practice name went into the invite Subject; a newline raised an uncaught ValueError after the invite was committed. Console SMS printed codes to the log in production. | fixed: names normalised, header errors become `MailError`; console SMS disabled in production (`phone_code` reports false) | `test_phone_codes_are_off_in_production_and_invite_names_cannot_inject_headers` |
| 14 | Medium | Charts | A birth time inside a DST gap was stored and silently computed with the pre-transition offset. | fixed: 422 for nonexistent local times. Ambiguous (fall-back) times still resolve to the first occurrence, see D3 | `test_local_time_status_flags_dst_gaps_and_folds`, `test_birth_record_in_a_dst_gap_is_rejected` |
| 15 | Low | Errors | `/ask` echoed raw exception text from SDKs and the fallback chain to the caller. | fixed: only curated `ProviderError` messages, otherwise the exception class | `test_fallback_errors_do_not_echo_raw_exception_text` |
| 16 | Low | Concurrency | Same Idempotency-Key racing, or two birth-record edits taking the same version, returned 500. | fixed: 409 (whole transaction rolls back, retry replays) | `test_concurrent_same_idempotency_key_never_500_...` |
| 17 | Low | Telemetry | Invite tokens (bearer secrets) sat in the URL path of spans. | fixed: redacted in the scrubbing exporter | `test_scrub_redacts_invite_tokens_in_url_paths` |
| 18 | Low | Auth | OIDC `redirect` accepted `/\evil`; production cookies were only Secure when the issuer URL was https; an external issuer named `ankana` could collide with built-in user rows. | fixed | `test_oidc_redirect_param_rejects_backslash_tricks`, `test_production_defaults_to_secure_cookies`, `test_external_issuer_cannot_impersonate_builtin_users` |
| 19 | Low | Storage | Keys with `:` or NUL (Windows alternate streams). Traversal was already blocked. | fixed, route test added | `tests/test_storage.py` |
| 20 | Low | API | Client search treated `%` and `_` as wildcards. | fixed | `test_client_search_treats_percent_and_underscore_literally` |
| 21 | Low | Migrations | `0002_core_api` downgrade failed on rows with new consent purposes. | fixed (lossy remap, documented in the file); single head asserted | `test_alembic_has_a_single_head_...` |
| 22 | Medium | SSRF | The Anthropic SDK (httpx2) cannot take the guarded transport, so a custom Anthropic base URL is checked by resolution at build time only; a rebinding window remains for that one kind. | accepted for now, see D1 | `test_hosted_providers_use_the_guarded_transport` covers the other kinds |
| 23 | Medium | Infra | `infra/azure/modules/apps.bicep` sets no `AUTH_SIGNING_KEY_PEM`, `AUTH_BUILTIN_ISSUER`, `ANKANA_SECRET_KEY`, `STORAGE_SIGNING_KEY`, `STORAGE_BACKEND=azure`, mailer settings. A production deploy would refuse to start (good) but the secrets are not provisioned. | fixed: `bootstrap-secrets.sh` generates the keys once, `apps.bicep` wires every secret and setting per identity, `app.preflight` fails fast with the full list (readiness probe, entrypoint and a pre-rollout job); see `docs/deploy.md` sections 4 and 5 | `tests/test_preflight.py` |
| 24 | Low | Auth | Refresh reuse detection has no grace window: two tabs refreshing at the same instant kill the session. Per-IP limits behave as one global bucket behind a proxy unless `AUTH_TRUST_PROXY=1`. Per-email lockout lets an attacker slow a victim's sign-in. | accepted (standard trade-offs, documented) | existing `test_refresh_rotates_and_reuse_revokes_the_session` |
| 25 | Low | Auth | OTP request for an unknown email skips the mail send, so response time differs by the send latency. | accepted; fix needs a background send, see D5 | n/a |
| 26 | Low | Storage | Signed download URLs are bearer capabilities (15 min) and do not re-check practice at download time. They are only minted inside a tenant-scoped request and the key embeds the practice id. | accepted | n/a |
| 27 | Low | Queue | Report usage counter can double count when a job is retried after the PDF was stored. | accepted (at-least-once semantics) | n/a |
| 28 | Low | Static | bandit: 7 Low, 0 Medium/High. B404/B603/B607 are the CLI provider (argument list, no shell, scrubbed env) and `taskkill`; B105 is the literal `"Bearer"`; B110 two deliberate best-effort swallows. pip-audit: only the `pip` tool itself (not a runtime dependency). | accepted | n/a |

### Checked and fine

* Tenancy: every table with `practice_id` (and `practice`) has ENABLE + FORCE RLS and a policy; the
  app role is neither superuser nor BYPASSRLS; composite FKs cover client, birth record, chart,
  invite and AI routing; every `/v1` query runs in `tenant_db`; client-role scoping goes through
  `load_client`/`load_chart`/`_plan`; the worker re-opens a `tenant_session(job.practice_id)` so RLS
  re-checks every report. `app_memberships` returns only the caller's own user id rows and
  `app_invite_lookup` is keyed on a SHA-256 token hash. (`test_every_practice_scoped_table_has_forced_rls_and_a_policy`)
* Tokens: EdDSA pinned, `iss`/`aud`/`exp`/`sub` required, previous key supported for rotation, `sid`
  revocation checked on every request, dev stub refused in production. Refresh tokens are hashed,
  rotated, reuse revokes the session. OTP codes are HMAC-hashed, five attempts, atomic counter.
  Cookie is httpOnly, SameSite=Lax, path `/v1/auth`; refresh/signout need Origin plus `X-Ankana-Csrf`.
* Jinja2 autoescape is on for `.j2`; the two `|safe` outputs are the bundled font CSS and the SVG
  built from escaped values. Chromium runs with JavaScript off and every non-`data:` request aborted.
  No user-supplied Jinja source anywhere, so no sandbox is needed.
* SQL: the only `text()` calls use bind parameters (queue, usage counter, `set_config`, functions).
* Keys: `api_key` is write-only (`has_key` only), audit rows exclude it, Fernet token prefixed `v1:`.
* Alembic: `upgrade head`, `downgrade base`, `upgrade head` on a fresh Postgres 16 leaves 27 tables,
  then nothing but `alembic_version`; the openapi export matches the committed file.

## Decisions needed

* **D1** Anthropic custom base URL on hosted deployments: keep the resolve-at-save check, or refuse a
  custom URL for that kind (simplest, closes the window), or move the SDK onto an httpx2 guarded transport.
* **D2** Resolved (Phase 3): `/v1/locations/search`, its legacy twin and `/api/v1/panchang/today` are
  behind the shared Postgres rate limiter (30 and 120 per minute per caller, 429 with `Retry-After`),
  and the public reminder links use it too instead of per-process counters. Requiring auth was not
  needed for launch; the limiter is the control. See `docs/operations.md` section 3 and
  `tests/pg/test_ratelimit.py`.
  Nominatim with no rate limit. Require auth or add a limiter before public launch?
* **D3** Ambiguous fall-back birth times resolve to the first occurrence with no flag. Add a `fold`
  field to birth records so the astrologer picks?
* **D4** Done: production secrets are provisioned (row 23). Remaining founder actions: enter `anthropic-api-key` and `acs-connection-string`, back up the two encryption keys.
* **D5** Constant-time OTP request (send mail from a background task) to close the timing side of row 25.
* **D6** `ANKANA_SECRET_KEY` is SHA-256 hashed into the Fernet key (no KDF, no rotation). Moving to
  MultiFernet with a key list would allow rotation without invalidating stored keys.
* **Merge note**: `0004_security_hardening` descends from `0003_ai_connections`. Parallel branches that
  add a migration must chain after it or `alembic heads` will show two heads (the single-head test
  catches this).
