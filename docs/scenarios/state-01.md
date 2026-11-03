# STATE-01: restart after checkout health

- **Status:** implemented happy path; deterministic SDK/MCP checks across two Python processes using the local adapter. A durable relational database is the design baseline; database integration is pending. No conversation history.
- **Starting point:** CORE-01, interrupted after Checkout catalogue and health have been saved. No source call is in flight.
- **Test boundary:** one local writer; immediate restart with the same trusted scope and observation window. The database design allows replacement workers to load the same committed Incident independently of worker disks.
- **Run identity:** restart retries the unfinished investigation with fresh SDK limits. A later assigned alert after a proposal starts the next investigation number in [STATE-02](state-02.md).

## What we save

| Part of the persisted Incident | Value at interruption | Purpose |
| --- | --- | --- |
| Identity and scope | INC-001; tenant, environment, region; original alert and observation window | Resume the same incident and validate it against trusted caller scope |
| Findings and status | Incident open; A1/A2, catalogue C1, health E1; existing hypotheses and proposal fields retained | Preserve observations and references; no proposal exists yet |
| Completed source calls | Checkout catalogue → C1; Checkout health → E1; canonical request fields for each | Recognise already completed requests without calling the source again |
| Data compatibility | Reader understands the stored shape | Database design requires compatible migrations; current adapter validates its storage format |

- **Database contract:** commit findings, completed-call identity and Incident revision together before returning tool success. Keep model and source calls outside the transaction; no separate recovery entity is needed.
- **Current adapter:** a local record and atomic file replacement exercise this application contract; they do not verify database durability, transactions or automatic work recovery.
- **Not required:** saved model-turn counters, remaining quotas or a serialized running process. Diagnostic traces are not recovery storage. Conversation persistence remains separate optional work; this scenario starts a fresh conversation from the saved Incident.

## Resume scenario

| Given | When | Expected result |
| --- | --- | --- |
| First process collected C1 and E1 | Each validated result is saved | The stored Incident contains both the finding and its completed-call entry |
| Two calls have been saved | First process exits | Discard its agent, source adapter and model conversation; retain only persisted Incident data |
| Fresh process receives the incident ID and trusted caller scope | Load committed Incident state; local adapter in current checks | Validate compatibility, scope, fields and references; preserve A1/A2/C1/E1 exactly |
| No conversation history is supplied | Start a new bounded run | Supply the saved card and harness; apply fresh SDK turn limits and timeout |
| Checkout mappings and health are already known | Choose the next unanswered question | Fetch failed Checkout traces, then Payments catalogue and health; add E2/C2/E3 |
| Model requests either completed Checkout query again | Check the request identity before source access | Return the recorded finding and current card; no source call or duplicate C/E entry |
| All required observations support a next step | Submit the proposal | Save the proposal; run ends as proposal_ready; Incident remains open |

## Completed-call identity

| Included in identity | Excluded |
| --- | --- |
| Tenant, environment, region, tool, service, resolved source and observation window; entries belong to this Incident | Wording of the model's question, SDK tool-call ID and model-turn number |

- **Code guarantee:** check this identity even if the model ignores completed-call information. Reuse the existing finding rather than creating another evidence reference.
- **Fresh data:** a different observation window is a different request. This scenario does not refresh stale findings or continue after a finished proposal.
- **Acceptance:** two source calls before restart plus three after restart; five distinct external requests in total. A replay request adds zero external calls. No evidence is lost or renumbered.
- **Verification:** `uv run python -m evals.state01` launches separate before/after workers. The first run reaches a two-turn limit after saving C1/E1; the second receives a fresh seven-turn limit and deliberately replays both saved requests. Review `output/state-01/trace.md` and the `before/` and `after/` model inputs.
- **Limit:** a read completed externally but not yet committed may repeat after a crash, including with a database. Database outage, uncertain-commit recovery, migrations and cross-host retries need integration tests; no exactly-once source execution is claimed.
