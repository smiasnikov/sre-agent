# State

- **Implemented:** [STATE-01](scenarios/state-01.md) recovers unfinished work in a fresh process; [STATE-02](scenarios/state-02.md) starts a later investigation after an already-assigned alert. Both use synthetic sources and scripted replies.

## Assumptions

- The caller-selected record remains accessible after restart; all writers use the same local store adapter.
- Source reads may repeat if they completed externally but were not saved. No exactly-once action guarantee is needed for these read-only cases.
- STATE-02 receives a later alert already assigned to the same Checkout Incident; its catalogue mappings remain valid.

## Ownership

| Information | Storage / authority |
| --- | --- |
| Incident | Authoritative local record: original/additional alert observations, scope, windows, findings, selected human step, revision, completed calls and proposal history |
| Current and prior proposals | Current proposal stored separately; earlier proposals retain run number, window, hypotheses, reason, uncertainty and evidence references |
| Conversation | Fresh SDK conversation from the Incident; no conversation persistence |
| Trace | Review artifact; not needed for recovery |

- Storage format **3** defines data shape; Incident revision tracks accepted updates. Formats 1/2 are rejected; migrations are not implemented.

## Conversation decision

- **Now:** recover from the Incident only and start a fresh conversation. Some analysis may repeat; completed source calls are still reused.
- **Future option:** use SDK SessionStore for unfinished conversation continuity. Always load the latest Incident; transcript writes are separate, and missing history falls back to Incident-only recovery.
- **Follow-up runs:** start a fresh conversation with the new signal/window and relevant prior conclusions marked historical. Do not resume the earlier run's conversation.

## Incident lifetime

```text
            INCIDENT OPEN — same ID
                        │
          ┌─────────────▼──────────────┐
          │ R1: investigate → proposal │
          └─────────────┬──────────────┘
                        │ remains open
                Already-assigned alert
                        │
          ┌─────────────▼──────────────┐
          │ R2: refresh → new proposal│
          │ Keep R1 findings/history  │
          └─────────────┬──────────────┘
                        │
            Further triggers [planned policy]
            Confirm resolution [planned]
```

## Process recovery

```text
 Validated tool result / proposal
                 │
                 ▼
 Atomically save Incident + completed call
                 │
          PROCESS RESTARTS
                 │
                 ▼
 Load and validate scope, format and references
                 │
                 ▼
 Fresh SDK execution from the saved Incident
 Same unfinished investigation, fresh limits
```

- **Run identity:** restart retries unfinished R1; a new assigned alert after P1 starts R2. Numbers identify investigations, not SDK model turns.
- **Save boundary:** persist findings and completed calls together before reporting success. Failed saves roll back uncommitted application changes.
- **Replay identity:** Incident + scope + tool + service + resolved source + window. Return the existing finding; question wording does not create another request.
- **Follow-up:** archive P1/hypotheses, append new alert observations and advance the window in one revision-checked save. Preserve human decisions and earlier references.
- **Freshness:** current proposal readiness requires cited telemetry from the new window; older observations remain historical context.
- **Limits:** fresh SDK turn limits and timeout per execution, no persisted remaining quotas. Lock acquisition defaults to one second; filesystem I/O is not bounded by that timeout.

## Lifecycle coverage

| Event | Implemented | Planned |
| --- | --- | --- |
| Restart | Fresh-process reload and completed-call reuse without conversation history | Automatic discovery/scheduling of unfinished incidents |
| Deploy | Reload only if the local record survives and its format remains compatible | Storage outside workers, compatible rollout/migration and cross-host coordination |
| Six-hour incident | One follow-up investigation with fresh telemetry and preserved history | Repeated long-duration operation, scheduling, catalogue freshness and context selection |
| Shift handover | Inspect saved findings, selected step/owner and proposal manually | Shared handover view, open questions and responsibility transfer |

## Left out and why

| Omission | Reason |
| --- | --- |
| Conversation persistence | The Incident is sufficient for current cases; accept some repeated analysis instead of maintaining transcript storage |
| Ingestion, correlation, scheduling and closure | Explicit application calls isolate lifecycle behavior |
| Migrations and production storage | Single-host scope; unknown formats fail closed rather than silently changing data |

## First failure risks

| Risk | Consequence |
| --- | --- |
| Lost local volume or incompatible deployment | Recovery is unavailable; format checks do not restore or migrate records |
| Growing history or stale mappings | Full cards become noisy/oversized; saved catalogue entries need a refresh policy |
| Filesystem failure | Atomic replacement does not provide power-loss durability or hard I/O deadlines |
