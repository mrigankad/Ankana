#!/usr/bin/env bash
# Create the Key Vault secrets Bicep deliberately does not own. CREATE-IF-ABSENT: a rerun
# never overwrites a signing key, an encryption key or a value you entered.
#
#   infra/azure/scripts/bootstrap-secrets.sh <resource-group> <key-vault-name>
#
# Needs: az (logged in, Key Vault Secrets Officer or Owner on the vault), openssl, jq.
# Works from anywhere, including a laptop: it uses the Azure Resource Manager API
# (az rest), not the Key Vault data plane, so the vault's private-only network setting
# does not matter. Secret values go through a 0600 temp file, never argv or the log.
#
# Generated here (random, never printed):
#   auth-signing-key-pem   Ed25519 PKCS8 PEM, signs access tokens
#   ankana-secret-key      Fernet seed for stored AI provider keys
#   ankana-master-key      AES-256 key wrapping per-practice data keys (privacy envelope)
#   notify-link-secret     HMAC key for one-tap reminder links
# Seeded with a single-space placeholder (you replace them; blank = feature off):
#   anthropic-api-key  acs-connection-string  sentry-dsn
#   razorpay-key-id  razorpay-key-secret  razorpay-webhook-secret
#
# BACK UP ankana-master-key and ankana-secret-key outside Azure (password manager)
# right after the first run: losing them makes encrypted client data and stored AI
# connections unrecoverable. Never regenerate them on a live environment.
set -euo pipefail

rg="${1:?usage: $0 <resource-group> <key-vault-name>}"
kv="${2:?usage: $0 <resource-group> <key-vault-name>}"
for tool in az openssl jq; do command -v "$tool" >/dev/null || { echo "missing tool: $tool" >&2; exit 2; }; done

sub="$(az account show --query id -o tsv)"
base="https://management.azure.com/subscriptions/${sub}/resourceGroups/${rg}/providers/Microsoft.KeyVault/vaults/${kv}/secrets"
api="api-version=2023-07-01"

umask 077
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

exists() { az rest --method get --url "${base}/$1?${api}" >/dev/null 2>&1; }

put() { # name, value (read from stdin)
  jq -Rs '{properties: {value: .}}' > "$tmp"
  az rest --method put --url "${base}/$1?${api}" --body "@${tmp}" >/dev/null
}

seed() { # name, generator command...
  local name="$1"; shift
  if exists "$name"; then echo "keep     $name (already set)"; return; fi
  "$@" | put "$name"
  echo "created  $name"
}

gen_ed25519() { openssl genpkey -algorithm ed25519; }
gen_b64_48() { openssl rand -base64 48 | tr -d '\n'; }
gen_b64_32() { openssl rand -base64 32 | tr -d '\n'; }
gen_hex_32() { openssl rand -hex 32 | tr -d '\n'; }
placeholder() { printf ' '; }

seed auth-signing-key-pem gen_ed25519
seed ankana-secret-key gen_b64_48
seed ankana-master-key gen_b64_32
seed notify-link-secret gen_hex_32

for s in anthropic-api-key acs-connection-string sentry-dsn \
         razorpay-key-id razorpay-key-secret razorpay-webhook-secret; do
  seed "$s" placeholder
done

echo
echo "Done. Still to enter by hand (see docs/deploy.md): anthropic-api-key, acs-connection-string."
