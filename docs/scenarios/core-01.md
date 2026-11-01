# CORE-01: checkout investigation

- **Contract:** check Payments health before proposing a next step.
- **Verification:** synthetic model and source data through the real SDK/MCP path; this is not a live-model quality result.

## Initial context

| Field | Value |
| --- | --- |
| Incident / scope | `INC-001`; `tenant-checkout`; production; `eu-west-1` |
| Service | `checkout-api` |
| Alert | 5xx rises from below 1% to 12%; p95 rises from 350 ms to 2.4 s |
| Clock | Alert at `T`; observation window is the five minutes ending at `T + 1 minute` |
| Unknown | Ownership, dependencies, source mappings, dependency health, deployment history, and root cause |

## Source data and reference path

| Step | Tool / service | Returned data | Card change |
| --- | --- | --- | --- |
| 1 | Catalogue / Checkout | Checkout team; Payments and orders dependencies; telemetry mappings | C1: navigation metadata |
| 2 | Health / Checkout | 11.8% errors; p95 2.3 s | E1: checkout health |
| 3 | Failed traces / Checkout | 8/10 sampled failures contain payment-call timeouts; 2 unclassified | E2: trace observation |
| 4 | Catalogue / Payments | Payments team; health source mapping | C2: navigation metadata |
| 5 | Health / Payments | 9% errors; p95 2.5 s in the same observation window | E3: dependency health |
| 6 | Proposal | Involve Payments and inspect payment errors and recent changes | Proposal; run ends; Incident stays open |

- **Inputs:** source tools accept `service_id` and `question`. Code supplies trusted scope, discovered source mappings, and the explicit observation window.
- **Order:** catalogue lookup precedes that service's telemetry. Health and traces may otherwise be gathered in a different order; exact call order is not the acceptance contract.

## Acceptance tests

| Given | When | Then |
| --- | --- | --- |
| Alert only | Run starts | Only A1/A2 are evidence; catalogue and dependency health are absent |
| No mapping for a service | Telemetry is requested | Reject the request before source access |
| Payment-call timeouts but no Payments health | A proposal is submitted | Reject the premature proposal; allow further investigation |
| Checkout health, failed traces, and Payments health | A useful next step is proposed | Accept current evidence references and explicit uncertainty; reject catalogue or invented evidence IDs |
| An accepted proposal | The run finishes | No additional source calls; no infrastructure change; Incident remains open |

- **Limits:** this scenario covers investigation. Local recovery, follow-up runs and shared updates are verified separately in STATE-01/02 and MP-01.
- **Trace:** `uv run python -m agent` writes a step table to `output/core-01/trace.md`; initial model input is readable in `model-input.md`.
