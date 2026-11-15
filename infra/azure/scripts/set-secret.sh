#!/usr/bin/env bash
# Set (or replace) ONE Key Vault secret through the Azure Resource Manager API, so it
# works against the private-only vault from any machine. The value is read from a
# hidden prompt (or stdin when piped), never from argv, and is not echoed.
#
#   infra/azure/scripts/set-secret.sh <resource-group> <key-vault-name> <secret-name>
#   printf '%s' "$ACS_CONNECTION_STRING" | infra/azure/scripts/set-secret.sh rg kv acs-connection-string
#
# Then restart the apps so they pick it up:
#   az containerapp revision restart -g <rg> -n ca-ankana-<env>-cin-api --revision <name>
# (or simply run the Deploy workflow again; Container Apps re-reads Key Vault references
# when a new revision starts.)
set -euo pipefail

rg="${1:?usage: $0 <resource-group> <key-vault-name> <secret-name>}"
kv="${2:?usage: $0 <resource-group> <key-vault-name> <secret-name>}"
name="${3:?usage: $0 <resource-group> <key-vault-name> <secret-name>}"
for tool in az jq; do command -v "$tool" >/dev/null || { echo "missing tool: $tool" >&2; exit 2; }; done

umask 077
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

if [ -t 0 ]; then
  read -r -s -p "Value for ${name} (hidden): " value; echo
  printf '%s' "$value" | jq -Rs '{properties: {value: .}}' > "$tmp"
  unset value
else
  jq -Rs '{properties: {value: .}}' > "$tmp"
fi
if [ "$(jq -r '.properties.value | gsub("\\s"; "") | length' "$tmp")" = "0" ]; then
  echo "refusing to store an empty value" >&2; exit 1
fi

sub="$(az account show --query id -o tsv)"
az rest --method put \
  --url "https://management.azure.com/subscriptions/${sub}/resourceGroups/${rg}/providers/Microsoft.KeyVault/vaults/${kv}/secrets/${name}?api-version=2023-07-01" \
  --body "@${tmp}" >/dev/null
echo "set ${name}"
