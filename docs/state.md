# State

- **Design baseline:** a durable relational database outside workers owns Incident state. Worker disks and conversations are disposable; there are no separate snapshot or checkpoint entities.
- **Verified behavior:** [STATE-01](scenarios/state-01.md) covers fresh-process recovery; [STATE-02](scenarios/state-02.md) covers a later assigned alert. Both use the local adapter, synthetic sources and scripted replies. Database integration and automatic scheduling are not implemented.

## Assumptions

- All writers use tenant-scoped transactions and expected-revision checks against the same authoritative database.
- Durable storage, compatible migrations and tested backup/restore are operational prerequisites.
- Source reads may repeat if they completed externally but were not committed. STATE-02 assumes valid catalogue mappings and an alert already assigned to the same Incident.

## Ownership

| Information | Storage / authority |
| --- | --- |
| Incident | Database record: scope, alerts, windows, catalogue, evidence, hypotheses, human-selected step, revision, completed calls and proposal history |
| Agent run | Bounded investigation; run number/window and proposals belong to the Incident. Live execution status and errors are not currently durable |
| Pending work — planned | Database records for accepted signals, due rechecks, work ownership and retry state; execution coordination, separate from Incident findings |
| Conversation | Fresh conversation from the Incident; no conversation persistence |
| Trace | Review artifact; not recovery authority or a durable audit log |

## Save and recovery contract

```text
 Source read / proposed update
              │
              ▼
 Validate result + expected Incident revision
              │
              ▼
 Transaction: findings + completed call + revision
              │
           COMMIT
              │
       Report tool success
              │
       WORKER RESTARTS
              │
              ▼
 Load committed Incident → fresh bounded execution
```

- **Transactions:** save related changes together or save none. Commit findings and completed-call identity before reporting success; keep model and source calls outside the transaction.
- **Revision checks:** accept an update only if the stored revision matches the one the writer read; reject stale updates to prevent lost writes.
- **Conflict:** reject a stale revision, reload current state and reassess; keep human decisions. See [Multiplayer](multiplayer.md).
- **Uncertain commit:** a lost connection may hide a successful commit. Reload and inspect the revision and recorded operation before retrying; revision changes alone do not identify which update succeeded.
- **Replay identity:** Incident + scope + tool + service + resolved source + window. Reuse committed findings; question wording does not create another request. Source calls are not part of the database transaction.
- **Run identity:** restart retries unfinished R1; a later assigned alert after P1 starts R2. Each execution gets fresh turn/time limits; no persisted budget entity.
- **Compatibility:** Incident revision tracks accepted updates; schema version tracks data shape. Compatible migrations and mixed-version rollout rules are required. The local adapter accepts format 3 only; migrations are absent.

## Incident lifetime

```text
            SAME INCIDENT — durable database state
                           │
              R1: investigate → proposal P1
                           │ remains open; worker released
                  Later assigned signal
                           │
              R2: refresh → proposal P2
                  Keep P1 and earlier evidence
                           │
              More triggers / resolution [planned]
```

- **Follow-up:** archive P1/hypotheses, append new alert observations and advance the window in one revision-checked commit. Preserve human decisions and earlier references.
- **Freshness:** current readiness requires telemetry from the new window; old observations remain historical. Catalogue refresh and context selection need policies.

## Execution scheduling — planned

- Save an accepted assigned signal and pending work in the same database transaction; acknowledge receipt after commit. Deduplicate redelivery using a stable signal ID. This requires one database, not a separate queue write.
- Workers claim due work with time-limited ownership; reclaim interrupted work and prevent expired owners from committing job completion. Detailed retry and ownership rules remain open.
- Only one investigation should be active per Incident; retain signals arriving during it for later processing. A scheduled recheck uses the same work mechanism with a future due time.
- At follow-up start, consume the saved signal into Incident observations and advance the run in one transaction. Do not change an active run's window on signal arrival.
- Worker replacement loads the latest Incident. Closure/pause checks, bounded retries and tenant capacity limits remain unimplemented; alert correlation stays upstream.

## Conversation decision

- **Now:** Incident-only recovery with a fresh conversation; some analysis may repeat, but committed source calls are reused.
- **Future option:** SDK SessionStore for unfinished conversations; always load the latest Incident. Missing history falls back to Incident-only recovery.
- **Follow-up:** fresh conversation with the new signal/window and relevant prior conclusions marked historical.

## Lifecycle coverage

| Event | Database design | Current verification / gap |
| --- | --- | --- |
| Restart | Another worker loads committed state and reclaims due work | Fresh-process reload/replay verified locally; automatic recovery and database integration pending |
| Deploy | Database survives worker replacement; compatible readers/writers share revisions | Database migrations, rollback and mixed-version operation unverified |
| Six-hour incident | Multiple bounded runs; refresh relevant evidence and retain history | One follow-up verified; scheduling, freshness and context limits pending |
| Shift handover | Shared findings, current proposal, selected next step/owner and reason | Fields persist locally; shared view, open questions and responsibility transfer pending |

## Left out and why

| Omission | Reason |
| --- | --- |
| Database adapter and database failure tests | Application recovery was isolated with a local adapter; transaction behavior needs integration verification |
| Scheduling, correlation and closure | Separate lifecycle responsibilities; only explicit follow-up calls are implemented |
| Conversation persistence | Accept repeated analysis while retaining structured Incident progress |

## First failure risks

| Risk | Consequence / required response |
| --- | --- |
| Incomplete working context after restart | Incident-only recovery repeats reasoning and may repeat unsaved reads; record important findings and open questions explicitly. Durable open-question fields remain planned |
| Growing history and stale context | Long incidents can fill model context with outdated findings; select relevant history, refresh mappings and define retention. These policies remain planned |
| Saved progress without reliable continuation | An Incident record alone cannot schedule or own the next run; durable pending work, deduplication and bounded retry/ownership rules remain planned |
