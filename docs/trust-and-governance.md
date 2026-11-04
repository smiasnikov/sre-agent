# Trust and governance

- **Goal:** enforce who may access data and perform work; let customers inspect evidence and control autonomy.
- **Implemented:** code-supplied scope, limited tools, validated references, reasons/uncertainty and preservation of human-selected work. Sources are synthetic and read-only.
- **Planned:** authenticated identities, production isolation, durable audit, customer views, action approvals and autonomy policy. Trusted caller input is not an authentication service.

## Boundaries

| Area | Current foundation | Production control — planned |
| --- | --- | --- |
| Tenant data | Model cannot override scope; mismatched responses rejected | Authenticate callers; enforce tenant access in sources, Incident storage, caches, knowledge, traces and exports |
| Tools | Allowlisted source reads, proposal and blocker operations | Least-privilege credentials and per-customer permissions; validate every operation independently of model instructions |
| Human direction | Trusted caller supplies actor; stale proposals rejected | Verify actor permissions; provide ownership, pause and disable controls |
| Data handling | Scoped synthetic inputs | Minimize/redact provider inputs; approve data routes, retention and customer access policies |

- A returned tenant label cannot prove underlying query isolation. Tool text remains untrusted data; prompt guidance is not an authorization boundary.

## Audit and customer visibility — planned

- Record actor, tenant/Incident, time, release/model/tool versions, requested operation, authorization result and outcome; link evidence/window and any approval or rejection.
- Show observations, concise rationale, uncertainty and human-selected work with protected source links. Enforce viewer access, redaction and retention; local traces are not a complete or tamper-protected audit trail.

## Autonomy progression

| Stage | Permission / status |
| --- | --- |
| Investigate and propose | Current scope; read telemetry and recommend, no infrastructure execution |
| Human-approved action | Planned: approval binds exact target, parameters and expiry; recheck authorization/current conditions at execution |
| Narrow automatic action | Future option: customer opt-in per capability, bounded impact, outcome verification and immediate disable control |

- Promotion requires capability-specific evaluations, operational review and tested failure handling. Diagnostic quality or model confidence alone grants no action permission.
- Approval, policy and execution checks belong in application/downstream controls; record retries and outcomes to prevent unintended repeated actions.

## Limits and risks

- **Unverified:** production tenant isolation, credential enforcement and audit integrity; action execution is outside the implementation.
- **Risks:** broad credentials leak data, misleading explanations create false trust, and autonomy expands faster than evidence. Test boundaries and retain explicit human control.
- **Reference:** [OWASP: excessive agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/).
