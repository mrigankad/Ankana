#!/bin/sh
# Key Vault placeholders are a single space (secrets cannot be empty). Treat blank
# optional settings as unset so providers and Sentry stay off until a real value exists.
# Container Apps `command` REPLACES the image ENTRYPOINT, so every command in
# infra/azure/modules/apps.bicep starts with this script.
for v in SENTRY_DSN ANTHROPIC_API_KEY OTEL_EXPORTER_OTLP_ENDPOINT \
         RAZORPAY_KEY_ID RAZORPAY_KEY_SECRET RAZORPAY_WEBHOOK_SECRET; do
  eval "val=\${$v:-}"
  if [ -n "$val" ] && [ -z "$(printf '%s' "$val" | tr -d '[:space:]')" ]; then unset "$v"; fi
done
# Fail fast: with ANKANA_ROLE=api|worker|migrate the container validates its whole
# environment (python -m app.preflight) and exits with the full problem list
# instead of starting half configured. Unset locally and in docker compose.
if [ -n "${ANKANA_ROLE:-}" ]; then
  python -m app.preflight --role "$ANKANA_ROLE" || exit 78
fi
exec "$@"
