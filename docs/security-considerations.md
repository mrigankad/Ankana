# Security Considerations

## Security Goals
Protect sensitive client data, preserve tenant boundaries, and ensure every critical interpretation is traceable and governable.

## Identity And Access
- role-based access control by workspace
- least-privilege permissions
- MFA for privileged roles
- optional SSO for enterprise tenants

## Data Protection
- encryption in transit and at rest
- signed downloads for reports and exports
- field-level protection for especially sensitive PII if required
- strict separation of tenant-scoped queries

## Auditability
- log access to client records, reports, exports, and admin functions
- capture actor, workspace, entity, action, and request metadata
- preserve audit events in tamper-evident storage if required by enterprise customers

## AI-Specific Risks
- prompt injection via user notes or uploaded content
- unsupported claims presented as astrological fact
- leakage of one tenant's data into another tenant's response context
- unsafe remedy guidance

Mitigations:
- sanitize retrieval inputs
- require citation-backed answer assembly
- validate post-generation output
- enforce workspace-scoped retrieval
- apply policy filters before delivery

## Sensitive Advice Guardrails
- never present medical, legal, or financial advice as definitive instruction
- require caution language for high-stakes content
- attach contraindications to remedies
- support workspace-configured disclaimer blocks

## Operational Security
- dependency scanning
- image and artifact signing
- secret rotation
- least-privilege service accounts
- protected admin actions with re-auth when needed

## Privacy And Governance
- consent tracking for AI interactions and report sharing
- retention policy enforcement
- export and deletion workflows
- data residency readiness for future enterprise tiers
