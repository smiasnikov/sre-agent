# Investigation scenarios

| Topic | Category | Scenario | Status |
| --- | --- | --- | --- |
| Core loop | Happy path | [CORE-01: checkout including Payments health](scenarios/core-01.md) | Implemented; deterministic SDK/MCP checks |
| Core loop | Happy path | [CORE-02: payment timeouts with normal Payments health](scenarios/core-02.md) | Implemented; deterministic SDK/MCP checks |
| State | Happy path | [STATE-01: restart after checkout health](scenarios/state-01.md) | Implemented; fresh-process recovery and replay checks |
| State | Happy path | [STATE-02: new signal after a proposal](scenarios/state-02.md) | Implemented; two runs, fresh telemetry and retained proposal history |
| Multiplayer | Happy path | [MP-01: human update during agent investigation](scenarios/mp-01.md) | Implemented; stale proposal rejection and scripted reassessment |

- Scenario IDs are ordered within each topic: happy paths, then negative cases, then edge cases. A happy path means the agent achieves its goal; service health need not be normal.
- SDK checks use a synthetic model and MCP data; live reasoning quality is a separate question.
- Design baseline: state in a durable relational database, transactional saves and tenant-scoped revision checks; see [State](state.md) and [Multiplayer](multiplayer.md).
- Current test scope: trusted tenant/actor identity, one responder and agent on one Unix host, local file adapter and read-only sources. Database integration, worker scheduling and cross-host recovery are not verified. Human updates use an application method; no UI or action executor.

## Test layers and evidence

| Layer | Coverage | Limit |
| --- | --- | --- |
| Deterministic application tests | Scope/schema checks, proposal readiness, stale references, local atomic saves, replay protection and competing processes; lock deadline uses a controlled clock | Does not verify database transactions, database durability, cross-host coordination or model judgment |
| SDK/MCP integration tests | Real SDK orchestration with a local synthetic Messages API and MCP sources | Tool choices and replies are scripted |
| Scenario evaluations | Five readable contracts with generated traces; STATE-01 uses two fresh Python processes | Reuses synthetic fixtures and expected replies; not an independent dataset or model benchmark |
| Semantic evaluation | Planned: held-out incidents, live model runs and human review; see [Evaluation](evaluation.md) | Not run; no accuracy or reasoning-quality claim |

- Run `uv run python -m unittest -v` and `uv run python -m evals` from the repository root.
- A passing SDK result alone is insufficient: scenario checks inspect the Incident, references, tool calls and persisted data.
