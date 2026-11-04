# Failure and failover

- **Goal:** preserve useful progress and responder control during model/provider or tool failures.
- **Implemented:** turn limits, execution timeout, explicit failure outcomes, tool-error responses and committed-progress recovery through the local adapter. Missing evidence cannot satisfy proposal prerequisites.
- **Planned:** controlled retries, request deadlines, cancellation, fallback routing and responder-facing degraded mode. Tests simulate failures; real outage/failover drills are absent.

## Sev-1 response — planned

```text
 Slow/erroring dependency → bound waiting and retry load
                                   │
                 ┌─────────────────┴──────────────────┐
                 ▼                                    ▼
       Evaluated fallback                    No suitable fallback
       Resume from Incident                  Findings + limitation
                                             Human investigation
```

| Step | Rule |
| --- | --- |
| Detect impact | Track timeouts, latency, queue age and stalled progress; occasional success does not establish usable service |
| Contain load | Bound concurrency and retries; use backoff/jitter within one response deadline across attempts. Account for retries at every layer |
| Select fallback | Require evaluated judgment/tool compatibility, approved customer-data routing and available capacity; switching a name/endpoint is insufficient |
| Resume safely | Load latest Incident, preserve human direction, reuse completed calls and refresh stale evidence. Prevent the replaced worker from committing further updates |
| Explain limitation | Show committed findings, links, unavailable context and the last proposal with its window; enable manual work without another model call |

## Failure boundaries

| Situation | Current behavior / remaining gap |
| --- | --- |
| Provider failure or no terminal decision | Unfinished execution becomes blocked; no automatic provider failover |
| Slow execution | Turn/time limits exist; synchronous source calls can block beyond the intended timeout |
| Tool failure | Error returned without fabricated findings; per-source deadlines/retries remain planned |
| Restart | Saved calls are reused; automatic worker recovery/ownership remains planned |

- **Checkout:** unavailable Payments health means unknown, not healthy. Report the gap; do not weaken evidence requirements to produce a proposal.
- **Recovery policy — planned:** prioritize urgent work with tenant fairness, limit retry amplification and probe recovery before restoring traffic. Do not simply extend every timeout.

## Limits and risks

- **Risks:** retries worsen overload; fallback changes judgment; replaced workers keep running. Test bounded retries, fallback quality and ownership/cancellation with fault injection.
- Preserve committed state; source reads completed but not saved may repeat. No exactly-once execution guarantee.
- **Reference:** [AWS: timeouts, retries and backoff](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/).
