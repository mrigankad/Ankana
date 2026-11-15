# Product Requirements Document

## Product Vision
Build a production-ready astrology platform that behaves like an expert astrologer with transparent reasoning. The system must combine deterministic astrological computation with grounded AI explanations so that users can understand not only the prediction, but also why it was made.

## Product Positioning
- Primary market: professional astrologers and consultants.
- Secondary users: end clients receiving reports, remedies, and guided consultations.
- Delivery model: SaaS platform with secure workspaces, client records, report generation, and conversational assistance.

## Version 1 Scope
### In Scope
- Vedic astrology engine for birth chart, divisional charts, strengths, dasha, transit, yoga, dosha, and remedy analysis.
- Practitioner workspaces with client records and repeat consultation history.
- Explainable predictions across daily, monthly, yearly, and long-range timelines.
- Grounded AI assistant that answers chart questions using computed artifacts only.
- High-quality PDF reports with chart visuals and reasoning sections.
- Enterprise controls: RBAC, audit logs, consent capture, retention controls, and traceability.

### Out of Scope
- Full implementation of KP, Jaimini, Nadi, Western, Numerology, or Lal Kitab as primary calculation systems in v1.
- Open marketplace for third-party rule packs.
- Native mobile apps.
- Direct brokerage, healthcare, or legal product integrations.

## Users
### Practitioner
Needs to onboard clients, generate charts, review timelines, ask follow-up questions, produce branded reports, recommend remedies safely, and track consultation history.

### Client
Needs secure access to reports, charts, timelines, remedies, and guided conversations tied to their own data only.

### Workspace Admin
Needs user management, role configuration, branding, audit visibility, subscription controls, and data governance settings.

## Primary Jobs To Be Done
- Interpret a client birth chart with expert-level detail and evidence.
- Explain current life patterns using dasha, transit, house, and yoga interactions.
- Generate consultation-ready reports quickly.
- Compare likely timing windows for career, relationship, finance, health, and spiritual developments.
- Recommend remedies with both rationale and caution.

## Functional Requirements
### Chart Computation
- Accept birth date, exact time, timezone, and location.
- Accept a human-readable birth location such as city, town, village, district, state, country, hospital name, or address, then resolve it to canonical latitude and longitude before calculation.
- Allow practitioners to review and correct the resolved location if multiple matches or ambiguous results are returned.
- Compute birth chart, panchang details, divisional charts, bala measures, and house-level facts.
- Preserve raw calculation inputs, derived values, and version metadata.

### Predictive Analysis
- Compute Vimshottari and other planned dasha systems with nested periods.
- Compute transit overlays and future transit timelines.
- Detect yogas and doshas with activation context.
- Produce domain-specific predictions for career, relationships, health, finance, education, property, travel, and spirituality.

### Explainability
- Every prediction must cite the underlying chart facts, timing systems, and triggered rules.
- The UI must expose "why this prediction" details.
- Report narratives must include reasoning summaries written for both practitioners and clients.

### Remedies
- Support classical Vedic remedies first.
- Provide contraindications, strength of recommendation, and evidence from the chart.
- Mark risky suggestions, especially gemstones and high-cost rituals, for conservative handling.

### AI Assistant
- Support question-answering over the chart and historical consultation context.
- Refuse unsupported claims if required data or rule support is absent.
- Explain uncertainty and conflicting signals explicitly.

### Reporting
- Generate structured PDF reports for chart overview, life themes, annual forecast, transit summary, and remedy plan.
- Support practitioner branding and configurable report sections.

### Practitioner Workflow
- Manage workspaces, clients, appointments, notes, conversations, reports, and follow-ups.
- Maintain version history for interpretations and issued reports.

## Non-Functional Requirements
- Reproducibility: repeated runs with the same inputs and engine versions must produce the same deterministic outputs.
- Performance: initial chart generation under 10 seconds for standard workload; large report generation under 60 seconds asynchronously.
- Availability: 99.9% target for production API and practitioner web application.
- Security: encryption at rest and in transit, role-based access, tenant isolation, signed downloads, and audit trails.
- Observability: traces, metrics, domain event logs, and explanation provenance tracking.
- Extensibility: additional astrology systems must plug into shared interfaces without rewriting core services.

## Success Metrics
- Time to generate a practitioner-ready first report.
- Prediction explanation click-through rate.
- Practitioner retention and weekly active workspaces.
- Client report completion rate.
- Assistant grounded answer rate.
- Low hallucination and unsafe remedy incident rate.

## Risks
- Overpromising predictive certainty.
- Using AI to infer unsupported domain facts.
- Inconsistent domain rules across traditions.
- Poor source validation for deterministic calculations.
- Practitioner distrust if outputs cannot be traced and reproduced.

## Compliance and Safety Expectations
- Advisory product posture with regulated-style controls.
- Clear disclaimers around medical, financial, legal, and high-stakes decisions.
- Consent and audit coverage for client data usage in AI interactions.
- Workspace-level retention and deletion controls.

## Phased Delivery
### Phase 1
Platform foundation, auth, workspaces, client intake, deterministic Vedic core, and chart storage.

### Phase 2
Rule engine, explainability layer, remedies engine, and practitioner chart workspace.

### Phase 3
PDF reports, AI assistant, conversation memory, and timeline visualizations.

### Phase 4
Analytics, notifications, advanced governance, and expansion module SDK.

## Acceptance Standard
The first release is successful when a practitioner can onboard a client, generate a complete Vedic analysis, inspect the astrological reasoning behind each major conclusion, ask follow-up questions in natural language, and deliver a branded PDF report from a secure workspace.
