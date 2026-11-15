# Testing Strategy

## Testing Philosophy
Deterministic astrology logic requires stronger validation than a typical content product. The system should prove mathematical correctness, rule consistency, grounding integrity, and secure behavior.

## Test Layers
### Unit Tests
- planetary calculations
- dignity and strength calculators
- rule evaluators
- remedy contraindication logic
- API request validation

### Golden Chart Tests
- curated birth charts with trusted reference outputs
- tolerance checks for longitudes and house calculations
- fixed expected outputs for dashas, yogas, and strengths

### Integration Tests
- chart generation pipeline
- rule engine over generated chart artifacts
- assistant grounding pipeline without the live LLM
- report manifest assembly

### Contract Tests
- API schema and auth behavior
- event payload stability
- report template input contracts

### End-To-End Tests
- practitioner creates client, generates chart, asks assistant question, generates report, shares with client

### Security Tests
- access control regressions
- tenant isolation
- signed link expiry
- injection handling for notes and assistant prompts

### AI Evaluation Tests
- groundedness and citation accuracy
- refusal behavior for unsupported questions
- unsafe remedy regression checks

## Environments
- local fast suites for unit and selected integration
- CI for full deterministic and contract suites
- nightly for golden charts, PDF snapshots, and AI evaluation batches

## Release Gates
- no deterministic regression against approved golden charts
- no broken API contracts
- no increase in unsafe answer rate beyond budget
- critical PDF templates render successfully
