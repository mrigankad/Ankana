# Backend Architecture

## Overview
The backend should use a modular service-oriented architecture deployed from a single monorepo. Services may begin as a modular monolith plus worker tier, then split later if scale or team boundaries justify it.

## Core Services
- `api-gateway`
- `case-service`
- `chart-service`
- `forecast-service`
- `remedy-service`
- `assistant-service`
- `report-service`
- `notification-service`
- `governance-service`
- `location-resolution-service`

## Execution Model
- synchronous APIs for reads, writes, and orchestration
- queue-backed workers for heavy chart, report, and AI workloads
- scheduled jobs for transit refresh, notifications, and retention tasks

## Service Notes
### `chart-service`
- validates generation requests
- requires canonical latitude, longitude, and timezone before deterministic execution
- orchestrates deterministic engine execution
- stores immutable chart artifacts
- emits chart-generated events

### `location-resolution-service`
- resolves user-entered place names and addresses through a geocoding provider
- normalizes canonical location labels, coordinates, and timezone
- returns ranked matches and confidence metadata
- records provider ids needed for audit and reproducibility

### `forecast-service`
- evaluates timing windows
- exposes long-range prediction APIs
- persists forecast summaries and evidence links

### `assistant-service`
- resolves context
- orchestrates grounding
- communicates with the LLM gateway
- stores validated grounded answers

### `report-service`
- manages templates and manifests
- renders report jobs
- stores output files in object storage

## Queueing
Recommended job classes:
- `chart.generate`
- `chart.recompute`
- `forecast.refresh`
- `report.render`
- `assistant.summarize`
- `notification.send`
- `governance.purge`

Use retry policies tuned per job class and dead-letter queues for operator review.

## Caching
- artifact cache keyed by input hash and engine version
- read cache for common chart dashboards
- bounded TTL cache for transit windows
- no cache should bypass authorization checks

## Data Consistency
- transactional writes within a bounded context
- event-driven propagation for downstream consumers
- idempotency keys for public POST endpoints that launch jobs

## Integration Boundaries
- identity provider for auth and SSO
- object storage for reports and exports
- message/email providers for notifications
- LLM gateway for AI
- geocoding and timezone providers for birth-place normalization
- observability providers for tracing and metrics

## Operations
- health endpoints per app
- readiness checks on dependency availability
- structured logs with request ids and workspace ids
- worker dashboards for stuck or poisoned jobs
