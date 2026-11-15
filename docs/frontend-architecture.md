# Frontend Architecture

## Frontend Goals
Build a practitioner-first web application that exposes deep astrological data without overwhelming users. The interface must support expert workflows, evidence inspection, report production, and client-friendly delivery.

## Applications
- Practitioner dashboard.
- Client portal.
- Admin console.

## Practitioner Information Architecture
- workspace overview
- client directory
- client profile
- chart explorer
- prediction timeline
- remedies center
- report builder
- assistant workspace
- settings and branding
- audit and governance views

## Key Screens
### Client Profile
- demographic profile
- birth records and rectification status
- location search with resolved latitude, longitude, timezone, and manual confirmation controls
- consultation history
- generated artifacts
- follow-up notes

### Chart Explorer
- D1 chart and divisional chart switcher
- planetary facts and house analysis
- strengths and dignities panels
- yoga and dosha panels with evidence drill-down
- dasha and transit timeline views

### Assistant Workspace
- chart-aware chat thread
- evidence sidebar
- suggested follow-up questions
- safe answer status and citation display

### Report Builder
- report template picker
- section toggles
- practitioner notes merge
- preview and async generation status

## UI Composition Strategy
- shell-level routing in each app
- feature modules aligned to product domains
- data fetching via typed API client
- server state cache for chart and report resources
- local UI state for panel selections and builder drafts

## Design Constraints
- dense data must remain scannable.
- explanations should collapse progressively from summary to evidence.
- visualizations must be accessible and printable.
- client-facing language should be softer than practitioner-facing terminology.
- birth input UX should prefer place-name search over raw coordinate entry, while still allowing expert override when needed.

## Visualization Components
- North and South Indian chart renderers
- tabular planetary positions
- timeline components for dasha and transit windows
- confidence and caution badges
- remedy evidence cards

## Frontend Security
- role-aware navigation
- signed report links for clients
- no caching of sensitive pages in shared browsers
- explicit confirmation for destructive actions and sensitive exports

## State Boundaries
- authentication and workspace context at app shell
- chart and report data in server-state cache
- assistant draft and report builder state locally scoped
- feature flags injected from API or config service

## Accessibility
- keyboard access for chart and timeline exploration
- semantic headings for long analyses
- screen-reader labels for chart nodes and confidence badges
- color-independent status indicators
