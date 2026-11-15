# Development Roadmap

## Phase 0: Foundation
- initialize monorepo, shared config, and CI
- set coding standards, docs conventions, and package boundaries
- implement auth, workspace model, and client records
- establish observability and audit plumbing

## Phase 1: Deterministic Vedic Core
- implement birth input normalization
- integrate ephemeris adapter
- compute D1 chart, divisional charts, panchang, dignities, strengths, dashas, and transits
- store immutable chart artifacts
- build golden-chart validation suite

## Phase 2: Rule And Explainability Layer
- implement yoga and dosha detection
- implement timing and domain prediction rules
- implement remedy recommendation rules with cautions
- expose evidence bundles and confidence semantics

## Phase 3: Practitioner Experience
- build practitioner dashboard and client profile workflow
- build chart explorer and timeline views
- expose report builder and structured chart views

## Phase 4: Reporting And Assistant
- implement branded PDF generation
- ship grounded assistant with citation support
- add consultation summaries and note integration

## Phase 5: Enterprise Hardening
- retention controls
- deletion workflows
- advanced audit views
- role customization
- operational dashboards and alerts

## Phase 6: Expansion Framework
- stabilize module SDK
- add compatibility and synastry contracts
- document onboarding path for future systems such as KP and Western

## Delivery Strategy
- each phase ends with a usable product slice
- deterministic correctness gates precede narrative AI rollout
- enterprise governance is introduced early, not postponed
