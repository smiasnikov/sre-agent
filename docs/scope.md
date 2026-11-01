# Scope

- **Goal:** propose one useful next step supported by scoped incident observations; do not claim a confirmed cause or incident resolution.
- **Status:** CORE-01/02, STATE-01/02 and MP-01 are implemented with deterministic checks; independent model reasoning remains unverified.

## Selected topics

| Topic | Covered behavior | Status |
| --- | --- | --- |
| Core loop | Checkout and Payments health → grounded diagnostic proposal | Current scope complete: CORE-01/02; deterministic SDK/MCP verification |
| State | Resume interrupted work; assigned alert starts another run | STATE-01/02 implemented; local recovery, refreshed evidence and proposal history |
| Multiplayer | A newer human decision conflicts with a stale agent update | MP-01 implemented; same-host atomic revision checks and scripted reassessment |

- **Scenario contracts:** [readable test tables](scenarios.md).
- **Core boundary:** CORE-01/02 cover the two successful investigation paths. Focused tests cover validation and limits; full source-outage trajectories and live reasoning quality remain unverified. See [core-loop assumptions and risks](core-loop.md).
- **Operating boundary:** one responder and agent on one host, read-only MCP source tools, trusted tenant/actor context, mocked external data. No real UI or chat ingestion.
- **Architecture:** small modules, inward dependencies, typed internal structures, runtime validation at external boundaries, Markdown agent guidance, and code-enforced scope.
- **Verification:** [scenario tables and test layers](scenarios.md) distinguish deterministic integration checks from independent model evaluation.

## Outside this implementation

| Omission | Reason |
| --- | --- |
| Live telemetry, detailed logs, deployments and previous incidents | Keep source contracts and the investigation path small and repeatable |
| Alert/chat ingestion, scheduling and production rollout | Local invocation isolates core-loop behavior |
| Alert correlation and incident merging | STATE-02 accepts an already-assigned alert from trusted application wiring |
| Production durability, conversation persistence and distributed writers | STATE-01 covers local recovery; MP-01 coordinates cooperating same-host writers. Cross-host coordination remains planned |
| Infrastructure changes, action execution and approval workflows | Diagnostic proposals are the current goal |
| Cross-incident learning | Defer knowledge retrieval and review; [memory](memory.md) remains a future design reference |
| Event streaming and distributed coordination | Same-host record locking covers the selected example |
| Full end-to-end failure coverage | Focused boundary tests cover meaningful errors; additional source-outage and long-duration trajectories remain unimplemented |
