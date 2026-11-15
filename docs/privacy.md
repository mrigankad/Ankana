# Privacy and DPDP readiness

Engineering reference for how Ankana handles personal data under India's Digital Personal Data
Protection Act 2023 and Rules 2025. Not legal advice: every legal characterisation below is a
working assumption that needs counsel (see "Open legal questions").

Roles (assumed): the practitioner (practice) is the **data fiduciary** for its clients' data and
Ankana is a **processor** under the DPA (`docs/privacy/dpa-template.md`, draft). If Ankana ever decides
purposes itself (analytics, model training) it becomes a fiduciary for that data. Ankana does not train
on client data and sends charts, not names or contact details, to language models.

Code: `services/api-py/src/app/privacy/`. Migrations: `0004_privacy`, `0006_encrypt_free_text`, `0008_erasure_log`. Tests: `tests/pg/test_privacy.py`.

## 1. Field-level encryption

- Envelope encryption. Each practice has a random 256-bit data key (DEK) and a separate blind-index key,
  stored wrapped in `practice_key`. The wrapping key (master key) is outside the database:
  `ANKANA_MASTER_KEY` (base64, 32 bytes; id in `ANKANA_MASTER_KEY_ID`) or Azure Key Vault
  (`ANKANA_KEYVAULT_KEY_ID`, RSA-OAEP-256; implemented behind the same interface, untested in CI).
  Production refuses to start without one. Dev/test fall back to a public development key with a warning.
- Values are AES-256-GCM, stored as `enc1:<dek version>:<base64url(nonce || ciphertext)>`. The AAD is
  `practice_id|table.column`, so a ciphertext moved to another column or tenant fails authentication.
- `EncryptedText` is a transparent SQLAlchemy type. `app.privacy.orm` hooks the Session: `bind_practice`
  stamps the practice on the session, and before any ORM statement or flush the practice keys are loaded
  through the caller's own RLS-bound connection (a session can only ever fetch its own practice's keys).
  Keys are cached per process for 30 seconds.
- Blind index: `HMAC-SHA256(blind key, label || normalised value)` in `client.contact_email_bidx` and
  `contact_phone_bidx`, maintained on insert/update. Email is lower-cased; phone keeps digits and the last
  10 (so `+91 98765-43210` equals `9876543210`). `GET /v1/clients?email=&phone=` uses it. Equality only; no
  prefix or substring search on encrypted fields. Names stay plaintext so the existing name search works.
- Encrypted columns: `client.contact_email`, `client.contact_phone`, `client.legal_hold_reason`,
  `birth_record.place_label`, `consultation_note.body`, `correction_log.old_value/new_value`,
  `privacy_request.reason`, `remedy_item.instructions`, `remedy_checkin.note`, `consultation.topic`,
  `consent.notice_text`, `notification.subject`, `notification.body`. A test asserts this list.
  `consent.notice_text_sha256` keeps the SHA-256 of the notice next to the encrypted text, so
  receipts and evidence survive even if the text is destroyed. Ciphertext is longer than the
  plaintext, so `consultation.topic` and `notification.subject` became `text`.
- Migrations `0004_privacy` and `0006_encrypt_free_text` encrypt existing rows in place (idempotent;
  `python -m app.privacy.cli backfill` repeats it; each migration only touches the columns that
  exist at its revision, and `0006` also fills `notice_text_sha256` before encrypting). Plaintext
  written by older code is still readable until backfilled. The migrate job needs
  `ANKANA_MASTER_KEY` (see deploy.md).

### Key rotation (operator runbook)

```
python -m app.privacy.cli rotate-master          # new master key: re-wrap all keys, no data rewrite
python -m app.privacy.cli rotate-data --all      # new DEK version per practice, re-encrypt, retire old
python -m app.privacy.cli rotate-data --all --purge-retired   # also delete retired keys (after 35 s)
python -m app.privacy.cli rotate-ai-keys         # ai_connection.api_key_enc: _OLD -> current secret
```

Master key: set the new key as `ANKANA_MASTER_KEY` + `ANKANA_MASTER_KEY_ID`, list old ones in
`ANKANA_MASTER_KEY_PREVIOUS="id:base64,..."`, deploy, run `rotate-master`, then drop the old key.
AI provider keys (`ai_connection.api_key_enc`) are Fernet under `ANKANA_SECRET_KEY` (a different,
older mechanism owned by the AI layer): set `ANKANA_SECRET_KEY_OLD` to the previous secret and run
`rotate-ai-keys`. Purging retired DEK versions makes any backup that only holds those versions
unreadable for the rotated data: that is intended, but do it only after backups you still need are covered.
Blind-index keys are not rotated with the DEK (rotating one means recomputing indexes: `backfill`).

### Not encrypted (deliberate or deferred)

- `user_account.email/phone/display_name`, `auth_identity.email`, `practice_invite.email`, `auth_otp.destination`:
  global (not per practice), looked up by value at login and covered by unique indexes. Encrypting needs a
  global master-key-derived blind index and changes to the auth service; deferred. They are removed or
  anonymised on erasure and account deletion.
- `birth_record` date, time, latitude and longitude, and `chart_artifact.payload`: needed in clear for
  computation and indexing. They are personal data and are in scope for export, erasure and retention.

## 2. Data principal rights

All asynchronous: the API creates a `privacy_request` and enqueues a `privacy_request` job; the worker does
the work and the request row carries status and result. Every request writes an audit event.

| Right | Endpoint | Who | Result |
|---|---|---|---|
| Access / portability | `POST /v1/clients/{id}/export` | owner, astrologer, the client themself | ZIP: `data/*.json` (client, birth records, charts, consents, receipts, consultations with notes, remedies, reports metadata, correction log, activity log, requests, portal invites), `files/reports/*.pdf`, `summary.pdf`, `manifest.json` (SHA-256 per file + HMAC signature under the practice key). Download via short-lived signed URL on `GET /v1/privacy/requests/{id}`; ZIP deleted after 7 days. |
| Erasure | `POST /v1/clients/{id}/erase` `{reason}` | owner, astrologer | See below. 409 under legal hold. |
| Correction | normal `PATCH` and new birth-record versions | staff | `correction_log` keeps before/after (encrypted); `GET /v1/clients/{id}/corrections`. Optional `X-Correction-Reason` header. |
| Practice export | `POST /v1/practice/export` | owner | One ZIP: `practice/*` plus `clients/<id>/...` bundles. |
| Account deletion | `POST /v1/practice/delete` `{confirm_name, reason}` | owner | Erases all clients, deletes members, AI connections, exports, settings; destroys the practice keys (crypto-shred of whatever is still encrypted); practice row stays as an anonymised tombstone. 409 while any client is under legal hold. |
| Legal hold | `PUT /v1/clients/{id}/legal-hold` | owner, astrologer | Blocks erasure, retention and account deletion until released. |

**Erasure model: delete and overwrite** (per-client keys were considered; per-practice keys plus
delete/overwrite is simpler and verifiable). For a client: stored report PDFs and prior export ZIPs are
deleted from object storage first (so a retried job still finds the keys); then remedy check-ins, items and
plans, consultation notes and consultations, reports, chart artifacts, birth records (all versions),
matching idempotency-key replays and portal invites are deleted; the portal login is removed and the
global user account anonymised when it has no other memberships (sessions revoked, password and
identities deleted); `correction_log` values are nulled. **Kept as the minimal tombstone**: the `client` row
(id, created_at, `erased_at`, name replaced by "Erased client", contact fields null), consent rows and
consent receipts (evidence of consent and its withdrawal; they hold no personal data beyond the client id),
the `privacy_request` row, and an audit event `client.erased` with row counts only.

Backups cannot be edited, so they age out under the backup retention window (35 days in prod; say so
in the notice). A restore re-runs every erasure since the restore point from the durable erasure
log (ids only, written before the erasure starts, one blob per event in object storage plus the
append-only `erasure_log` table): `python -m app.privacy.cli replay-erasures --since <ts>`. Runbook
and test evidence: `docs/operations.md`. Erasure now also deletes the client's `notification` rows
(rendered reminders held the client's first name). Log archives remain a procedure.

## 3. Retention

`PUT /v1/practice/privacy-settings {retention_inactive_years: N|null, retention_auto_apply}` (owner).
A client is a candidate when its last activity (client edit, consultation, birth record, report,
remedy check-in, consent) is older than N years. Skipped: legal hold, an active remedy plan, already
erased. `POST /v1/practice/retention/dry-run` queues a report (ids and last-activity dates, counts of
skipped clients; no names) in `privacy_request.result`. `POST /v1/practice/retention/apply
{confirm: true}` erases the candidates with the same cascade. `python -m app.privacy.cli retention-sweep`
(cron) queues an apply for practices with auto-apply on. Default is off: practices opt in.

## 4. Consent receipts

Every grant and withdrawal (`/v1/clients/{id}/consents...`) writes an immutable `consent_receipt` (RLS:
SELECT and INSERT only): event, purpose, notice version and language, **SHA-256 of the notice text shown**,
channel, timestamp, a receipt hash and an HMAC signature under the practice key. Retrieval for the client
portal: `GET /v1/clients/{id}/consent-receipts[/{rid}]` (portal users see only their own); responses
include the stored notice text and `verified` (recomputed hash and signature) so tampering at database
level is detectable. A receipt's text hash is null when the caller sent no notice text: clients should always
send it.

## 5. Data map

Lawful basis column uses DPDP terms: **consent** (s.6) unless stated; "legitimate use" refers to s.7;
all are working assumptions for counsel. Retention values are proposals, configurable per practice where
noted. Location: Postgres (target: India region) unless stated.

| Field / data | Purpose | Lawful basis | Retention | Encryption | Location |
|---|---|---|---|---|---|
| `client.display_name` | identify the client, search | consent (`chart_compute`) | until erasure or practice retention N years inactive | disk only (queryable) | Postgres `client` |
| `client.contact_email`, `contact_phone` | contact, reminders, portal invite | consent | as above | field AES-GCM + HMAC blind index | `client` |
| `client.timezone`, `preferred_language` | render reports and notices | consent | as above | disk only | `client` |
| `birth_record` date/time/lat/lon/tz | compute the chart | consent (`chart_compute`) | as above; versions kept for reproducibility | disk only | `birth_record` |
| `birth_record.place_label` | birth place free text | consent | as above | field AES-GCM | `birth_record` |
| `chart_artifact.payload` | computed chart (derived from birth data) | consent | as above | disk only | `chart_artifact` |
| `consultation` (mode, time) | consultation record | consent | as above | disk only | `consultation` |
| `consultation.topic` | what the consultation was about | consent | as above | field AES-GCM | `consultation` |
| `consultation_note.body` | practitioner's notes | consent | as above | field AES-GCM | `consultation_note` |
| `remedy_*` (title) | remedy plan | consent | as above | disk only | `remedy_*` |
| `remedy_item.instructions`, `remedy_checkin.note` | remedy plan and tracking | consent | as above | field AES-GCM | `remedy_item`, `remedy_checkin` |
| `notification.subject`, `notification.body` | rendered reminder (carries the client's first name) | consent | as above; deleted on erasure | field AES-GCM | `notification` |
| `report` PDF (name, chart, branding) | deliver report | consent (`report_sharing` when sent on) | as above; deleted on erasure | disk/blob encryption | object storage `<practice>/reports/...` |
| `consent`, `consent_receipt` | prove consent and withdrawal | legal obligation to evidence consent (assumed) | kept after erasure; proposal: 7 years | `notice_text` field AES-GCM, SHA-256 and receipt signed, not encrypted | `consent`, `consent_receipt` |
| `erasure_log` (ids, kind, time) | re-apply erasures after a restore | legal obligation | kept; no personal data beyond ids | disk only; also an immutable blob per event | `erasure_log`, `_erasure_log/` in object storage |
| `correction_log` old/new values | record of rectification | consent / legal obligation | values nulled on erasure | field AES-GCM | `correction_log` |
| `privacy_request.reason`, `client.legal_hold_reason` | rights handling, legal hold | legal obligation | request row kept; reason destroyed with practice keys | field AES-GCM | `privacy_request`, `client` |
| Export ZIPs | fulfil access request | legal obligation | 7 days | disk/blob encryption, signed manifest | object storage `<practice>/privacy/...` |
| `user_account` email, phone, name | log in, notify the practitioner | contract / consent | until account closure; anonymised on erasure | disk only (deferred) | `user_account` |
| `auth_identity`, `auth_otp`, `auth_session` (ip, user agent) | authentication, abuse limits | legitimate use (security) | OTP minutes; sessions until expiry | hashed secrets | auth tables |
| `auth_event` (hash of email, ip) | sign-in audit, rate limits | legitimate use (security) | proposal: 12 months | hashed subject | `auth_event` |
| `audit_event` (actor, action, ip; no PII in meta) | accountability, breach investigation | legitimate use / legal obligation | kept; proposal 3 years | disk only | `audit_event` |
| `practice` (name, GSTIN, state, Razorpay ids) | billing, tax | contract / legal obligation (GST records) | kept on account deletion for tax | disk only | `practice` |
| `ai_connection.api_key_enc` | practice's own LLM keys | contract | deleted on account deletion | Fernet (`ANKANA_SECRET_KEY`) | `ai_connection` |
| `idempotency_key.response` | safe request replay | legitimate use | pruned on erasure; proposal 24 h TTL | disk only | `idempotency_key` |
| `job.payload` | queue (ids only, never PII) | n/a | 30 days after completion (proposal) | n/a | `job` |
| Data sent to the LLM | AI assistant answers | consent (`ai_assistant`) | not retained by Ankana; provider terms apply | TLS | hosted LLM |

## Open legal questions (for counsel)

1. Fiduciary/processor split, and whether Ankana is a fiduciary for account and billing data of practitioners.
2. Whether the 7 day export TTL, retention of consent evidence and the audit log periods are acceptable.
3. Residency: no blanket localisation duty was verified for this data; hosting in India regardless.
4. Children's data (verifiable parental consent) if clients can be minors: not implemented.
5. Breach notification timelines and the Board/consent-manager obligations arriving in 2026-2027.
6. Whether erasure must also reach backups sooner than the backup window.

## Known gaps

- Hindi (and other language) notices: English only, Hindi flagged TODO in the template.
- Erasure by the client themself is request-and-approve through the practitioner; there is no
  portal-initiated erasure endpoint yet.
- Export PDF summary uses a built-in font (Latin text); non-Latin text appears as "?" in the PDF, exact text
  is in the JSON files.
- Azure Key Vault master key provider has no automated test.
