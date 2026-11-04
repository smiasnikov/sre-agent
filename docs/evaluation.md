# Evaluation

- **Goal:** an evidence-supported diagnostic next step; several answers may be valid.
- **Implemented:** deterministic tests and five [scripted scenarios](scenarios.md). Real model judgment, recorded interactions and production quality remain unverified.

## Judgment — planned

| Criterion | Accept when |
| --- | --- |
| Grounding | Observations support the explanation, beyond valid citation IDs |
| Context | Scope, observation window and human direction are respected |
| Usefulness | The proposed check reduces an important uncertainty |
| Calibration | Facts, hypotheses and missing information stay separate |
| Stopping | A useful proposal or genuine blocker ends unnecessary collection |

- Rate **met / partly met / unmet**, citing the trace. Tenant violations, invented evidence or unauthorized actions fail the case.
- **CORE-02:** accept justified client/path checks; reject claims that normal aggregates prove all requests healthy. Exact-output checks assess scripted preservation only.

## Eval set — planned

| Source | Coverage |
| --- | --- |
| Sanitized historical incidents | Realistic context available at decision time; exclude later postmortem conclusions |
| Synthetic cases | Missing/stale data, conflicting evidence, misleading tool text and boundary violations |
| Reviewed operational feedback | Corrections, rejected/ignored proposals and routine samples; acceptance alone does not prove quality |

- **Case:** context, tool responses, acceptable decisions, forbidden claims and provenance; cover happy, negative and edge cases, including recovery/human updates.
- **Split:** development and held-out sets; group related incidents/variants to avoid leakage. Responders review alternatives.

## Keep results honest — planned

```text
 Reviewed cases → repeated baseline/candidate runs
               → trace-based grading → compare by category
```

- Freeze regressions; periodically add fresh cases. Replace exposed holdouts without deleting difficult failures.
- Report category results, critical failures, run counts and uncertainty; averages must not hide rare failures.
- Blind reviewers to candidate identity; resolve disagreements. Calibrate model judges against humans and sample passing results.
- Version cases, rubric, grader and release. Separate synthetic checks, replay and live benchmarks; rebaseline changed graders.

## Limits and risks

- **Deferred:** real-interaction replay, live benchmarks and semantic graders; current checks isolate application behavior. [Release gates](shipping-changes.md) remain planned.
- **Risks:** overfitting, grader bias and small samples; use holdouts, human calibration and repeated comparisons.
- **Reference:** [Block's agent testing pyramid](https://engineering.block.xyz/blog/testing-pyramid-for-ai-agents).
