# Core loop

- **Implemented:** [CORE-01](scenarios/core-01.md) and [CORE-02](scenarios/core-02.md), using the real SDK/MCP path with synthetic sources and scripted model replies.
- **Goal:** propose one useful diagnostic step with evidence and uncertainty. A proposal ends the investigation; the Incident stays open.

## Assumptions

- Trusted application input supplies the Incident, tenant, environment, region and observation window. The design loads shared Incident state from a durable relational database; current checks use a local adapter.
- Catalogue mappings and synthetic summaries are authoritative within these examples. Failed traces are a selected sample, not a population-wide failure rate.
- Source tools are read-only; humans perform proposed follow-up work.

## Context

- Service dependencies and telemetry locations: [Checkout environment](case-environment.md).

| Stage | Source | Supplied information |
| --- | --- | --- |
| Initial | Alert and trusted runtime | Checkout errors/latency, scope, target window, harness, tools and execution limits |
| Discovered | Service catalogue | Owner, dependencies and telemetry mappings; navigation metadata, not incident evidence |
| Discovered | MCP telemetry | Scoped health summaries and bounded failed-trace samples with source/window references |
| Reused | Durable relational database; adapter planned | Existing mappings, observations, completed calls, human decision and prior proposals; observations remain tied to their original windows |

## Workflow

```text
 Assigned alert / human update / due recheck [planned intake]
 Local command [implemented entry]
            │
            ▼
 Validate/create/load Incident + target window
 Relational database [planned adapter]
            │
            ▼
 SDK: choose next useful question ◄───────────────────┐
            │                                        │
            ├─ Need data → guard → MCP → validate     │
            │                   → update card ───────┘
            ├─ Supported proposal → save → end run
            └─ Essential gap / run limit / provider failure
                                  → end with findings
```

## Collection rules

- **Order:** validate input/scope → resolve a service's catalogue → collect its telemetry → cite recorded observations. Catalogue mapping is required before that service's telemetry; other calls need not follow one exact sequence.
- **Next question:** collect information that could change the proposal. Checkout's reference path is impact → failed request path → implicated dependency health. CORE-02 changes the proposal when Payments aggregates are normal.
- **After each result:** save validated metadata/evidence and completed-call identity together, then return the card. Database commits must check the expected Incident revision; current checks use the local adapter. Invalid requests or responses add no findings.
- **Reuse:** identical completed requests within a window reuse their findings. STATE-02 uses a later window to obtain current telemetry while keeping earlier observations and conclusions.
- **Authority:** code supplies scope, mappings and window; model tools cannot override them. Markdown guides investigation; code enforces the boundary.

## Stopping

| Outcome | Condition |
| --- | --- |
| Proposal | Cited current-window Checkout health, failed traces and implicated dependency health support a diagnostic next step; state uncertainty |
| Blocker | Essential information cannot be obtained; explain the gap and retain findings |
| Runtime stop | SDK turn limit, timeout or provider failure; preserve committed progress |

- Confirming root cause is not required. Human pause controls and incident closure remain planned.
- [STATE-01](scenarios/state-01.md) retries unfinished work; [STATE-02](scenarios/state-02.md) starts the next investigation after an already-assigned alert.
- **Continuation — planned:** durable pending work starts bounded runs after assigned signals or selected recheck times; a proposal releases the worker. See [State](state.md). No supervisor model is required.

## Left out and why

| Omission | Reason / intended direction |
| --- | --- |
| Live integrations and deployment history | Keep the selected source contract small; later retrieve deployed versions/change summaries, then inspect relevant differences |
| Previous incidents and learning | Separate reviewed knowledge from current evidence; future retrieval should be scoped and selective |
| Alert/chat ingestion and correlation | Trusted callers supply assignments; these are separate integration responsibilities |
| Database adapter and scheduling | Durable storage is the design baseline; current checks cover application behavior with a local adapter |
| Repairs and independent model benchmarks | The current goal is a diagnostic proposal; scripted replies isolate workflow verification |

## First failure risks

| Risk | Consequence / planned response |
| --- | --- |
| Unsound reasoning | Valid citations do not prove the conclusion; evaluate independent model judgment on held-out incidents |
| Stale or noisy context | Old mappings, summaries or selected samples can mislead tool choice; add refresh and context-selection policies |
| Slow tools or incident bursts | Calls can block or exceed provider capacity; add per-source deadlines, bounded concurrency and tenant fairness. The current run timeout is not a hard I/O deadline |
