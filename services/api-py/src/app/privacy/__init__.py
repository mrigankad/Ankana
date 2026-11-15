"""DPDP readiness: field encryption, data principal rights, retention, consent receipts.

Modules
- keys:      master-key providers (env, Azure Key Vault) that wrap per-practice data keys
- crypto:    AES-GCM envelope codec, key cache, blind index (HMAC)
- types:     EncryptedText, the transparent SQLAlchemy column type
- orm:       Session hooks that load the practice key before binds and result processing
- models:    privacy tables (practice_key, privacy_request, correction_log, ...)
- service:   export, erasure, retention, receipts, corrections
- jobs:      the `privacy_request` queue handler
- api:       /v1 routes (install_privacy)
- cli:       key rotation, backfill, retention sweep (python -m app.privacy.cli)
"""
