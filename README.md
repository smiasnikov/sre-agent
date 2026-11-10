# Checkout incident investigation agent

Investigates checkout degradation and proposes one diagnostic next step with evidence and uncertainty. The run ends while the Incident stays open. CORE-01 covers degraded Payments; CORE-02 covers normal Payments aggregates despite Checkout payment-call timeouts.

## Run and verify

Requires Python 3.10+ and `uv`.

```sh
uv sync --locked
uv run python -m agent
uv run python -m agent --scenario CORE-02
uv run python -m unittest -v
uv run python -m evals
```

Default runs use real Claude Agent SDK/MCP orchestration with a deterministic mock model and synthetic sources. No real model credentials are needed. Evaluations run CORE-01/02, STATE-01/02 and MP-01; they verify workflow and coordination, not independent reasoning.

EVAL-01 adds a candidate-review report using application hard checks and illustrative rubric ratings: `uv run python -m evals.eval01`. Ratings are synthetic review fixtures, not independent judgment. It is also included in `uv run python -m evals`.

The design uses a durable relational database outside workers for shared Incident state. Transactions save related changes together; revision checks reject stale updates. The database adapter is not implemented; current persistence checks use a local file adapter. Use `--state PATH`, then `--state PATH --resume` for local recovery checks.

## Current boundaries

- **Assumptions:** a durable relational database with transactional updates, trusted scope/identity, read-only tools, and a shared telemetry window. Current checks use one responder and agent on one Unix host.
- **Left out:** database integration, automatic scheduling, live integrations, repairs and cross-incident learning. Recovery and revision-checked updates are verified with the local adapter; database durability and cross-host behavior remain unverified.
- **First failure risks:** valid references cannot guarantee sound reasoning. Growing or stale context can mislead later runs; missing execution coordination can strand or repeat work. Incident bursts can overload model and telemetry capacity.

## Review guide

| Document | Contents |
| --- | --- |
| [Core loop](docs/core-loop.md) | Context, tool choice, stopping rules, assumptions and failure risks |
| [Scenarios and tests](docs/scenarios.md) | Inputs, expected outcomes, test layers and verification limits |
| [Evaluation](docs/evaluation.md) | Judgment criteria, eval-set sources and controls against misleading results |
| [Shipping changes](docs/shipping-changes.md) | Planned release gates, shadow testing, canaries and rollback |
| [Monitoring](docs/monitoring.md) | Dashboard signals, paging rules and degraded-quality detection |
| [Failure and failover](docs/failure-and-failover.md) | Bounded failures, fallback eligibility and graceful degradation |
| [Cost and latency](docs/cost-and-latency.md) | Measurement, context efficiency and planned execution controls |
| [Trust and governance](docs/trust-and-governance.md) | Tenant boundaries, audit visibility and planned autonomy controls |
| [Recursive case](docs/recursive-case.md) | Detection, containment and recovery when the agent causes harm |
| [State](docs/state.md) | Durable relational database design, recovery and current verification limits |
| [Multiplayer](docs/multiplayer.md) | Human decisions, stale proposals and coordination limits |
| [Scope](docs/scope.md) | Implemented boundaries, omissions and reasons |

Each topic document records its assumptions, omission reasons and first failure risks. Generated traces and initial model inputs are under `output/`, grouped by scenario. Code lives in `agent/`, checks in `evals/` and `tests/`, and runtime guidance in `harness/`.
