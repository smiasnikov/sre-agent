# Multiplayer

- **Implemented:** [MP-01](scenarios/mp-01.md) rejects a stale proposal, preserves the human decision and accepts a scripted revised proposal through the real SDK/MCP loop.

## Assumptions

- Trusted application wiring supplies human identity, authorization and tenant scope; there is no authentication service or UI in this implementation.
- Cooperating processes share one Incident record and stable lock file on a Unix host. Every writer uses the adapter.
- Coordination covers Incident updates; it does not control infrastructure actions or activity outside the application.

## One coherent picture

| Information | Meaning |
| --- | --- |
| Observations | Accepted findings with source/window; proposals cannot rewrite their meaning |
| Human-selected step | Operational direction with owner, reason, evidence, decision maker and time |
| Agent proposal | A recommendation alongside the human decision; accepting it does not replace that decision |
| Incident revision | Version of accepted state; separate from the storage format version |

## Shared update protocol

```text
 Trusted human caller        Agent with card rN
          │                         │
          └───────────┬─────────────┘
                      ▼
          Validate scope and input
                      │
          Acquire stable record lock
                      │
          Check expected revision
                ┌─────┴─────┐
             current       stale
                │            └─ Return current card
                ▼                 Reload + reassess
       Commit Incident + rN+1
                │
          Unlock + return card
```

- Check and write happen under one lock. Model tools cannot choose a revision or submit a human decision.
- MP-01 reads r5; the human commits r6; the old proposal is rejected. The agent receives r6 and submits a revised recommendation as r7. Existing evidence and completed calls remain unchanged.
- Rejected candidates remain labelled stale in the review trace. This is not a durable audit history.
- Lock acquisition uses a monotonic deadline, default one second. `incident_lock_timeout` writes nothing for that attempt, rolls back uncommitted changes and does not interrupt the holder. Retry must still pass the revision check.
- Waiting remains synchronous and does not bound filesystem I/O or guarantee a hard end-to-end deadline.

## Human and agent conflicts

| Situation | Handling / status |
| --- | --- |
| Human selects work while the agent reasons | Implemented: reject stale proposal, return current state and preserve human attribution |
| Concurrent independent observations | Planned: append both after revision checks; no automatic merge currently |
| Human pauses, closes or takes ownership | Planned control state; retain in-flight findings for review |
| Human acts outside the system | Planned: record the report and refresh observations; shared state cannot lock external activity |

## Different agent conclusions — planned

| Step | Decision rule |
| --- | --- |
| Retain alternatives | Keep author, scope/window, evidence and uncertainty; current code has one active proposal, not a competing-proposal collection |
| Compare | Check whether region, observation time or freshness explains the difference |
| Investigate | Choose a read-only check that distinguishes explanations; avoid voting or confidence wording |
| Select | Responder chooses the next step and owner with a reason; retain alternatives and uncertainty |

## Left out and why

| Omission | Reason |
| --- | --- |
| UI/chat connectors, authentication service and durable audit history | A trusted local caller and review traces cover the selected update protocol |
| Observation merges and competing-conclusion storage | Meaningful merging needs separate rules; stale writes are rejected here |
| Distributed writers and event streaming | Same-host locking covers MP-01 without a coordination service |

## First failure risks

| Risk | Consequence |
| --- | --- |
| Frequent updates | Conflicts/timeouts can exhaust a bounded execution without progress; responders need another attempt |
| Uncooperative or cross-host writers | Local locks do not provide the required coordination guarantee |
| Different conclusions | Revisions prevent lost writes but do not decide which explanation is correct |

- **Verification:** scripted human/agent interaction through the SDK; two actual writer processes allow only one commit from the same revision; a real lock holder and controlled clock verify timeout/rollback/retry.
- **Unverified:** independent reassessment quality, stale UI views, pause races, writer failover and multi-agent disagreement handling.
