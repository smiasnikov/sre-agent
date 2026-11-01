# Incident tools

## get_service_context
Find the service owner, dependencies, and telemetry source mappings. Supply `service_id` and the `question` this lookup answers. The result updates `incident_card.catalogue`; it is metadata, not observed incident evidence. Look up a dependency only after discovering it in the catalogue.

## get_health
Check service errors and latency in the trusted observation window. Supply `service_id` and `question`. The service must already have a catalogue mapping. The result adds current health evidence to `incident_card.evidence`.

## get_failed_traces
Inspect a bounded sample of failed requests in the trusted observation window. Supply `service_id` and `question`. The service must already have a trace mapping. The result adds trace evidence; do not infer population-wide failure rates from this selected sample.

## propose_next_step
Record one proposal with `next_step`, `reason`, `evidence_ids`, and `uncertainty`. Optional `hypotheses` contain `statement` and `evidence_ids`. Proposal references must exist in `incident_card.evidence`; at least one must be a tool observation. Check the implicated dependency's health before proposing. The result ends the run without resolving the incident or performing the proposed work.

## report_blocker
Explain why essential context cannot be obtained using `reason`. Preserve available findings and end the run. Do not invent evidence or a cause.
