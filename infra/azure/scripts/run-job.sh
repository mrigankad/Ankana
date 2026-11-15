#!/usr/bin/env bash
# Start a Container Apps manual job, wait for it, print its console log, and exit
# non-zero if it did not succeed. Used by deploy.yml for the preflight and migrate jobs.
#
#   infra/azure/scripts/run-job.sh <resource-group> <job-name> [timeout-seconds]
set -euo pipefail

rg="${1:?usage: $0 <resource-group> <job-name> [timeout-seconds]}"
job="${2:?usage: $0 <resource-group> <job-name> [timeout-seconds]}"
timeout="${3:-900}"

exec_name="$(az containerapp job start -g "$rg" -n "$job" --query name -o tsv)"
echo "started ${job} execution ${exec_name}"

deadline=$(( $(date +%s) + timeout ))
status=""
while [ "$(date +%s)" -lt "$deadline" ]; do
  status="$(az containerapp job execution show -g "$rg" -n "$job" --job-execution-name "$exec_name" \
            --query properties.status -o tsv)"
  echo "status: ${status}"
  case "$status" in
    Succeeded|Failed|Stopped|Degraded) break ;;
  esac
  sleep 10
done

# Console output (the preflight problem list lands here). Best effort: log ingestion lags.
az containerapp job logs show -g "$rg" -n "$job" --execution "$exec_name" \
  --container "${job##*-}" --format text 2>/dev/null || \
  echo "(logs not available yet: Log Analytics ContainerAppConsoleLogs_CL, job ${job})"

[ "$status" = "Succeeded" ] || { echo "${job} did not succeed (status: ${status:-timeout})" >&2; exit 1; }
