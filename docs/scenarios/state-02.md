# STATE-02: new signal after a proposal

- **Status:** implemented happy path; two SDK runs with synthetic sources and scripted model replies. No live model.
- **Starting point:** CORE-01 run R1 ended with proposal P1. INC-001 remains open; A1/A2, C1/C2, E1/E2/E3 and five completed source calls are saved.
- **Boundary:** a trusted upstream system or human has already assigned the new alert to INC-001. Validate the supplied Incident ID and caller scope; do not infer the assignment. Catalogue ownership and source mappings remain valid. No conversation history is required.

## Synthetic inputs

| Context | Earlier run R1 | New signal / run R2 |
| --- | --- | --- |
| Incident assignment | INC-001, open | Already assigned to INC-001 by the trusted caller; same tenant, environment and region |
| Observation window | W1: 10:01–10:06 UTC | W2: 10:11–10:16 UTC, same date and scope |
| Alert signals | A1/A2: original Checkout alert | A3/A4: new alert at 10:16; 8% errors; p95 1.8 s |
| Checkout health | E1: 11.8% errors; p95 2.3 s | E4: 8% errors; p95 1.8 s |
| Failed Checkout traces | E2: 8/10 sampled failures contain payment-call timeouts | E5: same pattern, freshly sampled in W2 |
| Payments health | E3: 9% errors; p95 2.5 s | E6: normal aggregate health; 0.2% errors; p95 180 ms |

## Scenario table

| Step | Event | Expected behavior |
| --- | --- | --- |
| 1 | Receive a new alert already assigned to INC-001 | Validate the supplied Incident ID and trusted scope, then append A3/A4 with source/window. Preserve the original alert, A1/A2 and Incident ID |
| 2 | Accept the signal and start R2 | Atomically retain P1 as completed-run history and select W2 for this run. R1 stays completed; R2 starts investigating with fresh turn/time limits |
| 3 | Assemble R2 context | Load the same Incident, new signal, valid catalogue mappings and prior proposal/findings labelled with W1. Start a fresh conversation; retain any human-selected decision |
| 4 | Determine what needs refreshing | W1 health/traces cannot establish current conditions in W2. Reuse C1/C2; request Checkout health, failed traces and Payments health for W2 |
| 5 | Tools return current observations | Append E4/E5/E6 and three completed-call entries. Preserve E1/E2/E3, their references and original windows |
| 6 | Reassess the earlier lead | Checkout remains degraded with payment-call timeouts, but Payments aggregates are now normal. A Payments-wide outage is unconfirmed; a partial failure remains possible |
| 7 | Submit proposal P2 | Cite E4/E5/E6; propose Checkout-owned payment-path inspection, with uncertainty. Save P2 alongside P1 history; end R2 while the Incident stays open |

## Acceptance rules

- **History:** retain R1's proposal, reason, uncertainty, hypotheses and evidence references, linked to its run/window. A newer proposal does not erase the older conclusion or any human decision.
- **Freshness:** current-condition claims require W2 observations. W1 findings may support an explicitly historical comparison; their presence cannot satisfy R2's proposal-readiness check.
- **Replay:** W2 makes telemetry requests distinct from W1. A repeated request within W2 reuses its finding. Expected external calls: five in R1, three in R2; no catalogue refetch.
- **Run lifetime:** P1 does not finish R2. Only an accepted P2 or a blocker/limit ends the new run. No saved remaining quotas are introduced.
- **Consistency:** signal acceptance, run transition and later updates use atomic revision checks; no evidence is lost or renumbered.

- **Implemented boundary:** an explicit application method validates the assignment/scope and advances the window, archives P1 and its hypotheses, appends A3/A4 and starts R2 in one revision-checked save. Directly rerunning a completed proposal without this transition remains rejected.
- **History:** `proposal_history` holds earlier completed proposals with run number, window and hypotheses; `proposal` holds the current run's proposal. No full card copies or conversation transcripts are required for continuation.
- **Verification:** `uv run python -m evals.state02`; review `output/state-02/trace.md`, `run-1/` and `run-2/`. Tests reject stale-only/mixed stale citations, invalid assignments and malformed history. Storage format 3 is required; older formats are rejected without migration.
- **Outside scope:** alert correlation, choosing an Incident for an unassigned alert, and merging incidents. An existing assignment does not prove a common root cause.
- **Deferred:** duplicate/out-of-order signals, changed catalogue mappings, missing fresh telemetry, concurrent triggers, automated resolution and unbounded history retention.
