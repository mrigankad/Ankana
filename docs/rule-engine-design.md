# Rule Engine Design

## Purpose
Convert deterministic chart facts into explainable findings, predictions, and remedy recommendations through a versioned declarative rule system.

## Rule Categories
- yoga detection
- dosha detection
- dasha interpretation
- transit interpretation
- life-domain prediction
- remedy suggestion
- confidence adjustment
- contradiction and caution rules

## Rule Model
Each rule should define:
- `ruleId`
- `systemKey`
- `rulePackVersion`
- `category`
- `inputs`
- `conditions`
- `scoring`
- `outputTemplate`
- `evidenceSelectors`
- `activationStrategy`
- `safetyFlags`

## Example Conceptual Rule
```yaml
ruleId: vedic.gajakesari.basic
category: yoga_detection
inputs:
  - planetStates.jupiter
  - planetStates.moon
conditions:
  - type: angular_relation
    left: jupiter
    right: moon
    allowedHousesFromReference: [1, 4, 7, 10]
scoring:
  baseStrength: 0.65
  modifiers:
    - if: jupiter.debilitated
      delta: -0.20
outputTemplate:
  code: gaj_kesari_yoga
  effectTags: [wisdom, status, support]
```

## Evaluation Layers
### Layer 1: Fact Match
Consumes chart artifacts and resolves whether preconditions hold.

### Layer 2: Strength Scoring
Adjusts signal strength using dignity, aspect support, house ownership, combustion, retrogression, and divisional reinforcement.

### Layer 3: Timing Activation
Maps a finding to likely activation windows through dasha, transit, age band, or lifecycle patterns.

### Layer 4: Explanation Assembly
Produces structured evidence references and human-readable explanation fragments.

## Confidence Semantics
Confidence must be rule-based, not probabilistic theater. Compute from:
- evidence completeness
- signal agreement across chart layers
- timing alignment
- contradiction penalties
- data quality penalties

Confidence should be stored as:
- `low`
- `moderate`
- `high`
- `mixed`

Also keep a numeric internal score for ranking.

## Remedy Engine Integration
Remedies are a specialized rule output. A remedy rule should declare:
- target planet or affliction
- eligibility conditions
- contraindications
- practitioner review requirement
- expected benefit tags

High-risk remedies should require stronger evidence thresholds and may require practitioner acknowledgment before client delivery.

## Contradiction Handling
The engine must not flatten conflicting signals into a falsely certain answer. It should:
- preserve competing findings
- down-rank low-support conclusions
- surface ambiguity in the interpretation layer
- prefer caution when remedies or high-stakes decisions are involved

## Rule Pack Versioning
- Vedic rules ship as versioned packs.
- Historical findings are pinned to the rule pack version used at generation time.
- New rule packs should support re-evaluation workflows without mutating existing historical artifacts.

## Authoring Strategy
- Write rules in declarative config plus typed evaluators.
- Keep non-trivial math in shared evaluator primitives, not duplicated in many rules.
- Attach domain citations to rules so experts can review source rationale later.

## Testing Strategy
- rule unit tests for match and no-match cases
- regression suites for known charts
- contradiction tests
- remedy safety tests
- timing activation window tests

## Outputs
The engine should emit:
- `FindingArtifact`
- `PredictionArtifact`
- `RemedyArtifact`
- `EvidenceBundle`
- `ConfidenceSummary`

These become the source material for UI, reports, and assistant responses.
