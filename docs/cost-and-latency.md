# Cost and latency

- **Goal:** timely, useful incident progress at a controlled cost; lower spend or faster text alone is insufficient.
- **Implemented:** execution turn/time limits, completed-source-call reuse, bounded trace samples and health summaries; SDK turns appear in artifacts.
- **Planned:** token/cost accounting, timing metrics, context selection, evaluated model routing and tenant capacity/spend controls. Existing limits do not guarantee a spending cap.

## Measure — planned

```text
 Accepted trigger → queue → model ⇄ tools → proposal / blocker
                   └──────── responder waiting time ─────────┘
```

| Measure | Include |
| --- | --- |
| Cost per investigation | Model input/output tokens, tool costs, failures, retries and restart attempts; distinguish measured charges from estimates |
| Response time | Queue, model and source timing; median/tail latency to a valid proposal or explicit blocker |
| Useful progress | Sampled grounding/usefulness, critical failures and unnecessary collection; use the [evaluation rubric](evaluation.md) |

- Compare the same cases by release, model and incident category. Record sample counts; cheap successful cases must not hide expensive failures or poor urgent-incident results.

## Optimization order — planned

| Control | Decision |
| --- | --- |
| Reduce context | Store complete history; supply current evidence and relevant conclusions, fetching detail when needed. Repeated full Incident cards currently grow model input |
| Avoid repeated work | Deduplicate triggers, reuse suitable observations and schedule rechecks for explicit reasons; retain freshness requirements |
| Evaluate models | Select an explicit model that meets task-quality requirements; compare cost/latency before routing production traffic |
| Manage capacity | Bound concurrency/retries and preserve tenant fairness/urgent capacity; parallel reads require safe observation merging, currently absent |

## Limits and response — planned

- Define response targets, request deadlines, output/token limits and tenant spending controls in execution policy; calibrate them using measured demand and quality.
- Include all attempts in aggregate accounting: fresh per-execution limits after restart must not permit unlimited repeated spending.
- At a limit, preserve findings, show the missing work and support human continuation. Do not drop required evidence to claim success. Apply [release gates](shipping-changes.md) to optimizations.

## Limits and risks

- **Risks:** growing context, retry amplification and cheaper-but-weaker proposals. Measure whole investigations and retain a quality floor; the current timeout cannot interrupt every blocking source call.
- **Unverified:** production cost, latency distributions and quality/cost trade-offs; synthetic runs establish no efficiency benchmark.
