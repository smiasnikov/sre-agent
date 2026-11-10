# Scope

- **Goal:** propose one useful next step supported by scoped incident observations; do not claim a confirmed cause or incident resolution.
- **Design baseline:** a durable relational database outside workers, transactional Incident updates and tenant-scoped revision checks. Application scheduling uses durable pending work; no supervisor model or event stream is required.
- **Status:** CORE-01/02, STATE-01/02 and MP-01 are implemented with deterministic checks; independent model reasoning remains unverified.

## Selected topics

| Topic | Covered behavior | Status |
| --- | --- | --- |
| Core loop | Checkout and Payments health → grounded diagnostic proposal | Current scope complete: CORE-01/02; deterministic SDK/MCP verification |
| State | Resume interrupted work; assigned alert starts another run | STATE-01/02 verified with a local adapter; database persistence and scheduling pending |
| Multiplayer | A newer human decision conflicts with a stale agent update | MP-01 verified locally; conditional database updates and cross-host checks pending |

- **Scenario contracts:** [readable test tables](scenarios.md).
- **Core boundary:** CORE-01/02 cover the two successful investigation paths. Focused tests cover validation and limits; full source-outage trajectories and live reasoning quality remain unverified. See [core-loop assumptions and risks](core-loop.md).
- **Operating design:** shared relational database state with short transactions, read-only MCP sources and trusted tenant/actor context. Worker replacement must not depend on a worker disk. Job ownership and capacity controls remain planned.
- **Verification boundary:** one responder and agent on one Unix host, local file adapter and mocked external data. No database integration, real UI or chat ingestion is implemented.
- **Architecture:** small modules, inward dependencies, typed internal structures, runtime validation at external boundaries, Markdown agent guidance, and code-enforced scope.
- **Verification:** [scenario tables and test layers](scenarios.md) distinguish deterministic integration checks from independent model evaluation.
- **Evaluation example:** [EVAL-01](scenarios/eval-01.md) compares application hard checks with illustrative review ratings; independent semantic grading and live benchmarks remain planned.

## Outside this implementation

| Omission | Reason |
| --- | --- |
| Live telemetry, detailed logs, deployments and previous incidents | Keep source contracts and the investigation path small and repeatable |
| Alert/chat ingestion, scheduling and production rollout | Explicit invocation isolates behavior; the database design adds durable pending work and due rechecks |
| Alert correlation and incident merging | STATE-02 accepts an already-assigned alert from trusted application wiring |
| Database adapter, migrations and database recovery tests | A durable relational database is the architecture baseline; current tests establish local application behavior only |
| Conversation persistence and cross-host execution checks | Structured Incident recovery is sufficient for selected cases; database concurrency and worker ownership still need verification |
| Infrastructure changes, action execution and approval workflows | Diagnostic proposals are the current goal |
| Cross-incident learning | Defer knowledge retrieval and review; [memory](memory.md) remains a future design reference |
| Event streaming | Database transactions and pending-work records are the initial design; no separate stream is needed |
| Full end-to-end failure coverage | Focused boundary tests cover meaningful errors; additional source-outage and long-duration trajectories remain unimplemented |
