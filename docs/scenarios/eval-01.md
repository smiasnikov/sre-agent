# EVAL-01: candidate review

- **Status:** implemented; synthetic CORE-02 observations and proposals, real application hard checks and illustrative review fixtures. No model call or independent human grading.
- **Goal:** show that alternative useful answers can be acceptable while valid references alone cannot establish a sound conclusion.

## Shared context

| Reference | Observation |
| --- | --- |
| E1 | Checkout errors 11.8%; p95 2.3 s |
| E2 | 8/10 sampled failed requests contain payment-call timeouts |
| E3 | Payments aggregates normal: errors 0.2%; p95 180 ms |

- Same trusted tenant, service scope and observation window as [CORE-02](core-02.md). Five existing source-tool calls prepare the card; proposal checks do not change it.

## Candidate table

| Candidate | Proposed next step | Hard checks | Illustrative review |
| --- | --- | --- | --- |
| Checkout client | Inspect failed payment-client spans/logs | Pass | Acceptable: locate the timeout and distinguish causes |
| Payments path | Inspect endpoint/caller-specific Payments failures | Pass | Acceptable: aggregates may hide partial failure |
| Unsupported conclusion | Rule out Payments and investigate Checkout only | Pass | Unacceptable: normal aggregates cannot support that conclusion |

## Acceptance

| Check | Expected behavior |
| --- | --- |
| Schema and evidence prerequisites | Reuse application validation, including current Checkout health/traces and implicated dependency health |
| Different valid wording/next steps | No exact proposal-text comparison; both useful alternatives pass hard checks |
| Unsupported conclusion with valid references | Hard checks pass; separately recorded illustrative ratings identify weak grounding/usefulness/calibration/stopping |
| Positive review plus invalid proposal | Invented/catalogue references, incomplete evidence or malformed fields block the outcome; labels cannot override validation |
| Review output | Markdown shows observations, proposals, rubric ratings, explanations and evidence provenance |

- **Run:** `uv run python -m evals.eval01`; report: `output/eval-01/report.md`. Included in `uv run python -m evals`.
- **Boundary:** ratings/verdicts are authored fixture data, not computed semantic judgments. Editing a proposal does not rescore the fixture; no model-quality or production-accuracy claim follows.
- **Next:** human-reviewed outputs from independent model runs; held-out cases and semantic graders remain planned in [Evaluation](../evaluation.md).
