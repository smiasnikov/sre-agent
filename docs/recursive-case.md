# Recursive case

- **Goal:** contain harm caused or worsened by the agent, restore customer service and prevent recurrence.
- **Implemented foundations:** synthetic read-only sources, no infrastructure execution, evidence/revision checks and review traces. These do not guarantee sound recommendations.
- **Planned:** production detection, emergency disable controls, human-led recovery, protected audit and recovery drills; no agent-caused outage scenario is tested.

## Example

- An unsupported Payments diagnosis leads a responder to an unnecessary rollback; Checkout worsens. Read-only agents can also harm production through excessive queries or misleading advice.

## Response — planned

```text
 Suspected harm → contain → human-led recovery
                    │              │
                    └─ preserve evidence ─┘
                                   │
                        review → fix → limited return
```

| Phase | Required response |
| --- | --- |
| Detect | Combine customer-service monitoring, responder reports and agent traces; correlate deterioration with recommendations, queries or actions. Contain credible harm before proving causality |
| Contain | Authorized operators disable the affected capability/release; broaden containment if scope is unknown. Stop dispatch/retries and remove in-flight workers' authority at tool/store boundaries |
| Coordinate | Human incident commander owns recovery through an independent operational path; link agent-service and customer incidents, communicate impact/uncertainty and avoid recursive agent spawning |
| Preserve | Retain protected inputs, observations, proposals, release identity, revisions, human actions and timeline. Flag disputed recommendations without deleting history |
| Recover | Inspect actual service state, choose mitigation and verify customer recovery independently. Reversing the last action may be unsafe after other changes |

- Emergency controls must work outside the model conversation. Preserve manual access and findings while suspect automation is disabled; customer-facing status and controls remain planned.

## Changes afterwards — planned

- Review contributing failures across reasoning, freshness, presentation, permissions and coordination; assign preventive work with owners and verification criteria. A prompt patch alone may be insufficient.
- Add the incident and nearby variants to [evaluation](evaluation.md); test containment, cancellation and recovery under fault injection.
- Re-enable only after reviewed fixes and drills; start with limited assistance/traffic and reduced autonomy, then use [release gates](shipping-changes.md). Preserve customer control.

## Limits and risks

- **Risks:** delayed harm detection, ineffective cancellation and unsafe reversal; independently test detection, authority revocation and service recovery.
- **References:** [Google SRE: incident management](https://sre.google/sre-book/managing-incidents/), [postmortem culture](https://sre.google/sre-book/postmortem-culture/).
