# Checkout environment

- **Data:** synthetic alert input; discovered catalogue and telemetry data are supplied through MCP tools. The root cause is unknown.
- **Scenario:** [CORE-01](scenarios/core-01.md). Alert time is `T`; the trusted observation window ends at `T + 1 minute`.

## Services and locations

| Service | Role / owner | Dependencies | Available source references |
| --- | --- | --- | --- |
| `checkout-api` | Checkout / Checkout team | `payments-api`, `orders-db` | `metrics/checkout`, `traces/checkout` |
| `payments-api` | Payments / Payments team | None modelled | `metrics/payments` |
| `orders-db` | Known dependency only | Not modelled | No CORE-01 result data |

- Catalogue information is discovered through `get_service_context`, not preloaded into the Incident.
- `get_health` reports errors and latency; `get_failed_traces` returns a bounded failure sample.
- Model inputs contain the service and question. Code supplies tenant/environment/region, source mapping, and observation window.
- Source mappings are navigation metadata, separate from observed incident evidence.

## Signals

| Source | Data |
| --- | --- |
| Alert | Errors 12% (baseline below 1%); p95 2.4 s (baseline 350 ms) |
| Checkout health | Errors 11.8%; p95 2.3 s |
| Failed traces | 8/10 sampled failures contain payment-call timeouts; 2 unclassified |
| Payments health | Errors 9%; p95 2.5 s |

- All tool observations use the same five-minute window. A selected failed-request sample does not establish the population-wide timeout rate.
- Deployment history and detailed logs are outside CORE-01. Their absence does not establish that no change or error occurred.
- Tenant overrides, unknown service access, invalid mappings, and malformed responses are rejected before becoming evidence.
