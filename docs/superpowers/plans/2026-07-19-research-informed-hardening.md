# Research-Informed Hardening Plan (Plan R)

_Date: 2026-07-19. Sources read end-to-end where open-access; paywalled items
(ACM SIGIR full text, Springer Purple Star chapter, Wiley ACRES) read at
abstract level. Runs alongside Plan D (FastAPI route surface + web cutover)._

## What the literature says, in one paragraph each

1. **Citation correctness ≠ faithfulness** (Ittarat et al., SIGIR ICTIR 2025,
   arXiv:2412.18004). Up to **57% of RAG citations are post-rationalized** -
   the model answered from its own knowledge and attached a plausible citation
   afterwards. Correct-looking citations are not proof the answer came from
   the artifact. Both correctness *and* faithfulness must be tested.
2. **Domain-grounded tiered retrieval** (arXiv:2603.17872). Best practice for
   a grounded assistant: an **answerability gate before retrieval** (detect
   false premises), tiered trust (gold source → secondary → refuse), and a
   **graceful-refusal circuit breaker**. Their top failure mode -
   "False-Premise Overclaiming" - is exactly the risk for astrology Q&A
   ("when will my third marriage be?" for a chart with no such indication).
3. **RAG robustness survey** (arXiv:2506.00054). Actionable: RAGAS-style
   decomposition of answers into atomic claims checked against context;
   ARES-style LLM judges; RGB-style stress tests for noise robustness and
   negative rejection; evidence attribution embedded in outputs.
4. **Factual inconsistency in D2T scales exponentially with LLM size**
   (arXiv:2502.12372). Bigger models do NOT fix data-to-text hallucination;
   it worsens. Justifies Nakshatra's architecture: deterministic reading is
   the source of record, LLM is optional surface polish only.
5. **D2T hallucination-mitigation review** (Osuji et al., arXiv:2402.08496).
   Mitigations that work: pipeline/planning architectures (content selection
   separated from surface realization), controlled generation, data cleaning.
   Matches `nakshatra_interpret`'s design; formalize the LLM step as
   surface-realization-only with a post-check.
6. **Explainable-recommender HCI survey** (arXiv:2505.09065). Evaluate
   explanations on both qualitative and quantitative axes across the
   lifecycle; presentation method matters as much as content. For Nakshatra:
   progressive disclosure of evidence, not walls of citations.
7. **jyotishganit** (GitHub, Python, Skyfield + NASA JPL DE421, True Chitra
   Paksha ayanamsa). Independent open implementation covering the same
   surface (D1–D60, Shadbala 6-fold incl. Drik bala, Ashtakavarga,
   Vimshottari, panchanga). Ideal *independent cross-validator* - different
   ephemeris, different ayanamsa variant, so agreement within tolerance is
   strong evidence of correctness; it also has Drik bala, which our Shadbala
   holds at neutral 0.
8. **Ayanamsa literature** (ICRC/Lahiri). Standardized Lahiri at J2000 =
   **23.853222°**; our engine anchors 23.85306° (~0.6 arcsec off - fine, but
   cite the standard). A 0.3° ayanamsa error flips pada boundaries → boundary
   births are the highest-risk inputs.

## Workstreams

### R1 - Accuracy benchmark suite (trust, marketing-grade)
1. **Cross-validation vs jyotishganit**: script that runs N random birth
   inputs + the 3 golden charts through both engines; assert sign/nakshatra/
   pada/house agreement and longitude deltas < 2 arcmin (expected difference:
   Lahiri vs True Chitra ≈ arcseconds; DE421 vs astronomy-engine ≈ arcsec).
   Disagreements become investigation tickets, not silent drift.
2. **Boundary-case pytest suite**: generated births whose Moon/lagna sit
   within ±0.1° of sign, nakshatra, and pada boundaries; assert stable,
   documented behavior and add a `boundaryProximity` warning field to the
   artifact so the UI can flag "birth-time sensitive" charts (practitioner
   value: rectification prompt).
3. **Rashtriya Panchang golden dates**: encode ~12 published panchang rows
   (tithi/nakshatra/yoga/karana for known dates) as fixtures; assert engine
   agreement. This is the benchmark the comparative-software study used.
4. **Sunrise-based vara + panchang** (known v1 limitation): implement
   sunrise via astronomy-engine's rise/set; vara switches at sunrise, not
   midnight; expose `sunrise`/`sunset` in the artifact (also enables hora,
   gulika later). Golden-test against published sunrise tables.
5. Comment the Lahiri anchor with the ICRC J2000 value and the delta.

### R2 - Assistant faithfulness harness (the 57% problem)
1. **Counterfactual perturbation eval**: for each eval question, answer once
   against the true artifact and once against a perturbed artifact (e.g.,
   Mercury moved to house 5). If the answer text doesn't change accordingly,
   the citation was post-rationalized. Score = % of answers that track the
   perturbation. This is the cheapest faithfulness test available because our
   ground truth is structured JSON we can mutate surgically.
2. **Claim-level grounding check (RAGAS-style)**: decompose each assistant
   answer into atomic claims (LLM judge or regex for numeric/name claims);
   verify every claim against the artifact; report a groundedness score per
   answer and block responses below threshold with a refusal.
3. **Answerability gate**: before the tool loop, classify the question as
   answerable-from-artifact / answerable-from-rules / unanswerable; refuse
   unanswerable premises explicitly ("the chart does not indicate X") instead
   of overclaiming - mirrors the tiered-retrieval circuit breaker.
4. **Negative-rejection test set**: ~30 questions with false premises or
   out-of-scope asks (health diagnosis, lottery numbers); assert refusal.

### R3 - LLM polish guardrails (justified by exponential D2T scaling)
1. Polish step contract: input = deterministic reading items; instruction =
   rewrite prose only; **post-check** = extract all numerals, planet names,
   sign names, house numbers from polished text and assert each exists in
   the source item's facts; on violation, fall back to deterministic text.
2. Label polished sections `aiPolished: true` in the payload; UI shows a
   subtle badge (transparency contract).

### R4 - Evidence UX (explainable-recommender findings)
1. Full Reading tab: evidence collapsed by default, one tap to expand per
   paragraph (progressive disclosure); per-section "how this was derived".
2. Later: instrument comprehension (do users expand evidence? do they edit
   predictions in reports?) - the survey's lifecycle evaluation point, and
   the only ML-worthy data collection in the app today.

### R5 - Rule engine upgrades (ACRES/RecGen direction)
1. Attach **uncertainty weights** to every prediction rule: confidence =
   f(Shadbala ratio band, SAV bindus of the window lords' houses, dignity).
   Surface as low/medium/high with the numeric drivers in evidence.
2. **Contradiction surfacing**: when two fired rules push the same domain in
   opposite directions within overlapping windows, emit a paired
   "tension" prediction instead of two contradictory lines - honesty beats
   false precision.

## Order of execution
R1.1–R1.3 first (pure tests, fast, immediately raise trust in the new Python
engine) → R2.1 + R2.4 (assistant evals, needed before Plan D ports the
assistant) → R1.4 sunrise vara (small engine feature) → R3 (with the polish
step when it lands) → R5 (with the predictions port in Plan D) → R4 (with the
Full Reading tab).

## Sources
- arXiv:2412.18004 - Correctness is not Faithfulness in RAG Attributions
- arXiv:2603.17872 - Domain-Grounded Tiered Retrieval
- arXiv:2506.00054 - RAG: Comprehensive Survey (robustness frontiers)
- arXiv:2502.12372 - Factual Inconsistency in D2T Scales Exponentially
- arXiv:2402.08496 - D2T Generation: systematic review incl. hallucination mitigation
- arXiv:2505.09065 - HCI in Explainable Recommender Systems: a survey
- github.com/northtara/jyotishganit - independent Python Vedic engine (JPL DE421)
- ICRC Lahiri standardization (J2000 = 23.853222°); r-astro.com/blog/lahiri-ayanamsa
- academia.edu/128386692 - comparative accuracy study (Rashtriya Panchang benchmark; abstract)
