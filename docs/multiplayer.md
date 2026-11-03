# Multiplayer

- **Design baseline:** humans and agents share one Incident in a durable relational database; tenant-scoped conditional updates prevent lost writes across workers.
- **Verified behavior:** [MP-01](scenarios/mp-01.md) preserves a human decision, rejects a stale proposal and accepts a scripted reassessment. Current tests use a local file adapter; database concurrency is not verified.

## Assumptions

- Trusted application wiring supplies actor identity, authorization and tenant scope; an authentication service and UI are not implemented.
- Every writer uses the revision protocol against the authoritative database. Reading a card does not reserve it for later writing.
- Coordination covers Incident records; it does not control infrastructure actions or human activity outside the application.

## One coherent picture

| Information | Meaning |
| --- | --- |
| Observations | Findings with source/window; proposals cannot rewrite their meaning |
| Human-selected step | Operational direction with owner, reason, evidence, decision maker and time |
| Agent proposal | Recommendation alongside the human decision; does not replace it |
| Incident revision | Version of accepted state, separate from database schema version |

## Shared update protocol — database design

```text
 Human update                 Agent with card rN
       │                              │
       └──────────────┬───────────────┘
                      ▼
          Validate scope and input
                      │
                      ▼
          Short database transaction
          Update only if revision = rN
                ┌─────┴─────┐
             updated       stale
                │            └─ Return latest card
                ▼                 Reload + reassess
       Commit Incident + rN+1
```

- The revision condition and write are one database operation. Include tenant/Incident identity; zero updated rows cannot be treated as success.
- Model reasoning and external reads happen outside the transaction. Model tools cannot choose revisions or submit human decisions.
- MP-01 reads r5; a human commits r6; the old proposal is rejected. Reassessment produces r7 while preserving the human step, evidence and completed calls.
- A database timeout or uncertain commit requires a reload and operation check before retrying. Configure bounded database waits; never bypass revision checks.
- Rejected candidates remain labelled stale in the review trace; durable audit history is not implemented.

## Human and agent conflicts

| Situation | Handling / status |
| --- | --- |
| Human selects work while the agent reasons | Verified locally: reject stale proposal, return current state and preserve human attribution; database adapter pending |
| Concurrent independent observations | Planned: retain both through controlled append/retry rules; no automatic merge currently |
| Human pauses, closes or takes ownership | Planned control state; retain in-flight findings for review |
| Human acts outside the system | Planned: record the report and refresh observations; database coordination cannot lock external activity |

## Different agent conclusions — planned

| Step | Decision rule |
| --- | --- |
| Retain alternatives | Keep author, scope/window, evidence and uncertainty; current code has one active proposal |
| Compare | Check whether scope, observation time or freshness explains the difference |
| Investigate | Choose a read-only check that distinguishes explanations; avoid voting or confidence wording |
| Select | Responder chooses next step and owner with a reason; retain alternatives and uncertainty |

## Left out and why

| Omission | Reason |
| --- | --- |
| Database adapter and cross-host concurrency tests | Local checks isolate revision semantics; database behavior needs separate verification |
| UI/chat, authentication service and durable audit history | Trusted callers and review traces cover the current example |
| Observation merges and competing-conclusion storage | Need explicit rules beyond rejecting stale writes |
| Event streaming | Database transactions are sufficient for the proposed update protocol |

## First failure risks

| Risk | Consequence / planned response |
| --- | --- |
| Repeated revision conflicts | State stays protected while the agent makes no progress; bound retries and group pending updates while preserving human direction |
| Shared record without shared awareness | Stale UI views or unreported external work can leave responders acting on different context; add update notifications, explicit ownership and pause controls |
| Different conclusions | Revisions do not establish which explanation is correct; retain alternatives, collect distinguishing evidence and let the responder select the next step |

- **Current adapter:** a stable file lock protects check/write on one Unix host; lock acquisition defaults to one second. This is test evidence for local behavior, not database durability or database timeout behavior.
- **Verification:** scripted human/agent reassessment, two competing writer processes and controlled lock-timeout/rollback checks.
- **Unverified:** database transactions across hosts, independent reassessment quality, pause races, stale UI views, writer failover and multi-agent disagreements.
