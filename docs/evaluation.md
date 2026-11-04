# Evaluation

- **Goal:** judge whether the agent proposes a useful next diagnostic step supported by available evidence; a confirmed root cause is not required.
- **Implemented:** deterministic tests and five [scenario checks](scenarios.md) with scripted model replies. Independent model judgment is unverified.

## Assumptions

- Responders review cases and acceptable alternatives; several next steps may be valid.
- Historical data is sanitized and access-controlled before evaluation; only information available at the decision time enters the agent context.

## Evaluation layers

| Layer | What it establishes | Status |
| --- | --- | --- |
| Deterministic foundations | Validation, scope, reference checks, recovery and revision handling | Implemented; local adapter |
| SDK/MCP scenarios | Workflow and scripted-output preservation across CORE-01/02, STATE-01/02 and MP-01 | Implemented; synthetic sources/model |
| Recorded interactions | Replay reviewed real tool/model interactions to detect integration regressions | Planned; recordings do not measure a new model's judgment |
| Live judgment evaluation | Repeated model runs scored against responder-reviewed criteria | Planned; no quality benchmark or production success claim |

## Judging a proposal — planned

| Criterion | Review question |
| --- | --- |
| Grounding | Do the observations actually support the explanation, beyond valid citation IDs? |
| Context | Are tenant, service, observation window and human direction respected? |
| Usefulness | Would the proposed check reduce an important uncertainty? |
| Calibration | Are observations, hypotheses and missing information clearly separated? |
| Stopping | Is a useful proposal or genuine blocker reached without unnecessary calls? |

- Score each criterion as met, partly met or unmet, with evidence from the trace. Any tenant-boundary violation, invented evidence or unauthorized action fails the case independently of other scores.
- **CORE-02:** accept a justified Checkout-client or targeted Payments-path check; reject claims that normal Payments aggregates prove every request is healthy. Do not require exact wording or one tool sequence beyond required prerequisites.
- Exact-output checks currently verify scripted replies survive the workflow; they are not semantic graders.

## Building the eval set — planned

| Source | Contribution |
| --- | --- |
| Sanitized historical incidents | Realistic alerts, decision-time telemetry and responder-reviewed alternatives; keep final postmortem conclusions out of inputs |
| Synthetic cases | Controlled missing/stale data, conflicting evidence, scope violations and misleading tool text; label separately |
| Reviewed operational feedback | Failures, corrections and ignored/rejected proposals, plus a sample of routine cases; acceptance alone is not proof of quality |

- Each case includes initial context, available tool responses, expected decision properties, forbidden claims and provenance. Cover happy paths, negative cases and edge cases, including restart, follow-up and human-update scenarios.
- Keep development and held-out cases separate; group related incidents and variants to avoid leakage. Begin with a small reviewed set and expand coverage from observed gaps.

## Keeping results honest — planned

- Freeze a regression set; add fresh incidents periodically. Retire exposed holdouts from independent comparisons and replace them; never remove a hard case merely because it fails.
- Compare baseline and candidate on the same cases with repeated runs. Report per-category success, critical failures, run counts and uncertainty; averages must not hide rare failures.
- Blind human reviewers to candidate identity; resolve disputed ratings. Calibrate any model judge against human labels, and review disagreements and sampled passes.
- Version cases, rubric, grader, harness, model and tool contracts. Report live runs, recorded replay and synthetic checks separately; changed graders require a new comparison baseline.

## Left out and why

- Live benchmarks, production-derived cases and automated semantic judges remain unimplemented; current checks isolate application behavior before measuring reasoning quality.
- Release thresholds and production rollout belong to the shipping design; no quality threshold is claimed here.

## First failure risks

| Risk | Response — planned |
| --- | --- |
| Overfitting to familiar incidents | Hold out incident families and refresh cases from new failures |
| Grader rewards plausible language | Require evidence-based ratings, human calibration and review of sampled passes |
| Small or biased sample hides regressions | Track coverage, repeat runs and report critical failures separately |

- **Reference:** [Block's agent testing pyramid](https://engineering.block.xyz/blog/testing-pyramid-for-ai-agents); current synthetic scenarios do not yet provide its recorded-reality or live judgment layers.
