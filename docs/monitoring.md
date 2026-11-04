# Monitoring

- **Goal:** detect late, stalled or weak investigations, even when answers sound convincing.
- **Implemented:** review artifacts record outcomes/stop reasons, tool errors, evidence references, revisions, harness hashes, reported model and SDK turns.
- **Planned:** metrics export, dashboards, paging, probes, quality review and token/cost accounting; no production monitoring exists.

## Dashboard — planned

| View | Signals |
| --- | --- |
| Responder outcome | Time from accepted trigger to valid proposal/explicit blocker, including queue time; stuck investigations |
| Context collection | Provider/tool error rates, throttling, latency, missing evidence and blocker reasons |
| Progress | Repeated calls, retries, revision conflicts and time since useful committed progress |
| Judgment quality | Sampled grounding/usefulness ratings, unsupported claims, corrections and rejection reasons |
| Capacity | Queue age, active workers, concurrency, turns, tokens and cost per investigation |

- Compare release/model, source and incident category; restrict tenant drill-down. Keep sensitive content/Incident IDs in protected traces, not metric labels.
- Separate valid blockers from failures; proposal rate and human acceptance do not establish quality.

## Paging — planned

| Response | Condition |
| --- | --- |
| Immediate page | Confirmed tenant-data exposure, unauthorized execution or corrupted shared state |
| Impact-based page | Urgent investigations repeatedly miss response targets; queued work stalls; source/provider failures prevent useful assistance |
| Ticket/review | Gradual quality decline, increased corrections, cost growth or isolated recoverable errors; escalate confirmed serious harm |

- Calibrate response targets, windows and sample requirements; none are configured. Group shared-cause alerts instead of paging per Incident.
- Include scope/release, impact, protected trace and response guidance. Guard-rejected requests do not automatically warrant a page.

## Detecting degraded quality — planned

```text
 Runtime checks ───→ explicit failures and stalled progress
 Reference probes → recurring behavioral regressions
 Trace review ────→ grounding, usefulness and uncertainty
                         │
                         ▼
                 Compare with baseline
```

- Apply the [evaluation rubric](evaluation.md) to routine samples and failures; calibrate automated judges against responders.
- Report release/category results and sample counts; check incident-mix changes. Quality review has delay and incomplete coverage.
- On degradation, expose limitations, preserve findings, notify responders and pause/roll back suspect [releases](shipping-changes.md).

## Limits and risks

- **Risks:** weak answers evade checks, sampling misses rare harm and alert floods hide impact. Combine probes/review with deduplicated paging.
- **Reference:** [Google SRE: alerting on SLOs](https://sre.google/workbook/alerting-on-slos/).
