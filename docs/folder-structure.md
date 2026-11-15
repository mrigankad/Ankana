# Folder Structure

## Monorepo Layout
```text
docs/
apps/
  api/
  worker/
  web-practitioner/
  web-client-portal/
  admin-console/
packages/
  astrology-core/
  rule-engine/
  ai-orchestrator/
  reporting-core/
  case-core/
  auth-core/
  analytics-core/
  notifications-core/
  module-sdk/
  shared-types/
  shared-config/
infra/
  docker/
  kubernetes/
  terraform/
scripts/
tests/
  unit/
  integration/
  contract/
  golden-charts/
  e2e/
```

## Application Responsibilities
- `apps/api`: HTTP API, auth enforcement, orchestration, and public contracts.
- `apps/worker`: async jobs for chart generation, report rendering, notifications, and AI summaries.
- `apps/web-practitioner`: primary SaaS interface for astrologers.
- `apps/web-client-portal`: secure client-facing report and remedy portal.
- `apps/admin-console`: tenant management, audits, and governance controls.

## Package Responsibilities
- `packages/astrology-core`: deterministic calculation engines and artifact builders.
- `packages/rule-engine`: yoga, dosha, prediction, and remedy rules.
- `packages/ai-orchestrator`: grounding, retrieval, prompt contracts, and LLM integration.
- `packages/reporting-core`: report manifests, chart visuals, section builders, and PDF adapters.
- `packages/case-core`: clients, consultations, notes, and workflow models.
- `packages/auth-core`: roles, policies, memberships, sessions, and consent.
- `packages/module-sdk`: interfaces for future astrology systems and extension modules.
- `packages/shared-types`: DTOs, ids, enums, and event contracts.
- `packages/shared-config`: environment schema and common configuration loaders.

## Internal Conventions
- Keep domain code inside packages, not spread across applications.
- Apps orchestrate packages and handle transport concerns.
- Shared utility code must live in named packages, not in generic `utils` buckets unless truly cross-domain.
- Documentation should stay under `docs/`; ADRs can later live under `docs/adr/`.

## Test Placement
- package-local unit tests alongside source when practical.
- cross-package integration tests under `tests/integration/`.
- API contract tests under `tests/contract/`.
- golden deterministic chart cases under `tests/golden-charts/`.
- full product e2e tests under `tests/e2e/`.

## Module Expansion Layout
Future astrology systems can follow:
```text
packages/modules/
  vedic/
  kp/
  jaimini/
  western/
```

Each module exports:
- system registration
- calculation providers
- rule pack references
- vocabulary mappings
- UI metadata

## Infrastructure Layout
- `infra/docker`: local development containers.
- `infra/kubernetes`: deployment manifests or Helm charts.
- `infra/terraform`: cloud provisioning for databases, queues, storage, and secrets.
- `scripts`: repeatable local and CI scripts for validation and maintenance.

## Documentation Discipline
- Every package should eventually include a concise `README.md`.
- Public interfaces should generate docs from code contracts where possible.
- Keep business rules in dedicated rule definitions, not hidden inside controllers or UI components.
