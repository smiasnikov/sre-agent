# CORE-02: payment timeouts with normal Payments health

- **Status:** implemented with deterministic SDK/MCP checks; sources and model replies are synthetic.
- **Category:** happy path — valid observations support a useful diagnostic proposal despite mixed signals.
- **Contract:** use normal Payments health to revise the lead; neither assert nor exclude a Payments failure.

## Scenario input

| Field | Synthetic value |
| --- | --- |
| Initial context | Same scope, alert and observation window as [CORE-01](core-01.md); only A1/A2 are initial evidence |
| Checkout catalogue | Checkout owner; Payments/Orders dependencies; health and trace mappings |
| Checkout health | E1: 11.8% errors; p95 2.3 s |
| Failed Checkout traces | E2: 8/10 sampled failures contain payment-call timeouts; 2 unclassified |
| Payments catalogue | Payments owner and health mapping |
| Payments health | E3: source reports normal aggregate health: 0.2% errors; p95 180 ms, in the same scoped window |
| Still unknown | Timeout location, affected request subset, detailed errors, deployment history and root cause |

## Expected workflow

| Step | Observation / open question | Tool choice or interpretation | Card update |
| --- | --- | --- | --- |
| 1 | Ownership and sources are unknown | Get Checkout catalogue before its telemetry | C1: navigation metadata |
| 2 | Is impact continuing? | Get Checkout health | E1 confirms current degradation |
| 3 | Which request path is involved? | Get failed Checkout traces | E2 supports a payment-path hypothesis; the selected sample is not a traffic-wide failure rate |
| 4 | Is Payments itself broadly degraded? | Get Payments catalogue, then health | C2: navigation metadata; E3: normal aggregate health |
| 5 | E2 and E3 describe different views | Weaken the Payments-wide outage hypothesis. Keep partial Payments failure, Checkout client issues and network issues as unconfirmed alternatives | Preserve E1/E2/E3; record hypothesis and uncertainty separately |
| 6 | What would distinguish those alternatives? | Propose that the Checkout owner inspect failed payment-client spans and related logs for timeout location and affected requests | Save a proposal citing E1/E2/E3; end the run; Incident stays open |

- **Order:** catalogue before that service's telemetry; otherwise choose the next unanswered question. The table is a reference path, not an exact call-order requirement.
- **Source limits:** normal aggregate health does not establish that every Payments endpoint, caller or request is healthy. A client timeout does not establish that Payments caused it.
- **Tool limits:** detailed span/log inspection is proposed follow-up work; the current tools return summaries only. Do not claim that inspection occurred.

## Acceptance and stopping

| Given | When | Expected result |
| --- | --- | --- |
| E2 suggests the payment path; E3 is normal | Interpret the findings | Explicitly acknowledge both; no confirmed root cause or claim that Payments is ruled out |
| Available summaries leave several causes possible | Choose the next step | Name a targeted check that can distinguish the alternatives; explain why it helps |
| E1/E2/E3 support that check | Submit the proposal | Cite all three observations, state uncertainty, and end without repeating answered queries |
| Detailed logs are unavailable through current tools | Decide whether to stop | A useful diagnostic proposal is sufficient; missing root-cause proof alone is not a blocker |
| Proposal is accepted | Finish | Run is `proposal_ready`; Incident remains `open`; no infrastructure changes |

## Verification

| Check | What it verifies |
| --- | --- |
| Scenario data isolation | CORE-02 has normal Payments health; running it does not change CORE-01's degraded Payments data |
| SDK/MCP execution | The existing workflow preserves observations, citations and the expected scripted proposal/hypothesis; five distinct source queries, then proposal |
| Checker sensitivity | Replacing the saved reason with the old degraded-Payments conclusion, or removing the Payments health citation, fails the deterministic checks |

- **Run:** `uv run python -m agent --scenario CORE-02`; artifacts are written to `output/core-02/`.
- **Limit:** exact scripted-output checks verify preservation, not independent reasoning. No live model was run. A separate live evaluation should assess meaning without requiring exact proposal wording.
