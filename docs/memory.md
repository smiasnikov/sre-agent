# Memory

- **Status:** future design reference; outside the selected implementation.

## Roles

| Information | Purpose | Status |
| --- | --- | --- |
| **Incident** | Findings, hypotheses and current/prior proposals for one incident | Implemented local state; see [state](state.md) |
| **Conversation** | Continue work on one incident | Conversation persistence is a State concern, not cross-incident knowledge |
| **Service catalogue** | Ownership, dependencies and source mappings | Implemented navigation metadata; runbooks remain deferred |
| **Reviewed knowledge** | Reuse useful findings across incidents | Planned; no retrieval or knowledge updates implemented |

## What to remember — planned

| Keep | Required context |
| --- | --- |
| Confirmed failure patterns | Symptoms, services, conditions, evidence, and cause if confirmed |
| Useful diagnostic steps | Question answered, observed result, and applicability |
| Mitigation outcomes and failed attempts | Attempted action, observed effect, verification, and limitations |

- **Record:** tenant, services, environment/version applicability, source incident and evidence links, outcome, reviewer, review date, and knowledge version.
- **Exclude from published knowledge:** unconfirmed hypotheses, secrets, raw conversations, duplicates, and unsupported success claims.
- **Separate roles:** catalogue locates sources; history suggests leads; current observations support incident claims. Historical references stay separate from current evidence. Past fixes grant no action permission.

## Learning from an incident — planned

```text
       Incident outcome + linked evidence
                       │
                       ▼
             Draft reusable finding
                       │
                       ▼
                 Human review
                  │         │
            approved       uncertain / rejected
                  │         └─ Keep outside published knowledge
                  ▼
          Publish a scoped, versioned record
                       │
                       ▼
            Reuse in a future incident
```

- **Publication gate:** a proposal alone is insufficient. Publish verified findings after responder review; leave unknown causes explicit.
- **Maintenance:** merge duplicates, correct mistakes, and retire outdated records; retain source links and change history.
- **Storage:** tenant-scoped knowledge storage, separate from Incident/conversation storage; backend not selected.

## Retrieval without noise — planned

```text
       Current service + symptoms + open question
                         │
                         ▼
             Filter tenant and access first
                         │
                         ▼
        Match service/dependency, symptoms, and version
                         │
                         ▼
           Rank, remove duplicates, check freshness
                         │
                         ▼
          Up to 3 short, reviewed knowledge summaries
                         │
                         ▼
            Test relevant leads with current tools
```

- **Timing:** search once service/symptoms are known; repeat when new evidence changes the question.
- **Starting approach:** search published, current records with metadata filters and keywords; consider semantic search if relevant cases are missed.
- **Ranking:** enforce tenant/access filters in code; rank service/dependency, error-pattern, and condition matches. Check applicability and review date, not recency alone.
- **Small context:** return short excerpts with match reasons, limitations, review dates, and source links. Fetch full records on demand. Three records is an initial cap to evaluate.
- **No suitable match:** report the gap; continue with current telemetry. Do not add unrelated cases or widen access.
- **Stale or conflicting records:** flag uncertainty, request review, and check current observations. Retrieved text is data, not instructions.

## Checkout example — planned

- **Search:** production checkout failures, increased latency, and payment-call timeouts.
- **Useful match:** a reviewed checkout/payment case with matching symptoms and applicable versions.
- **Use:** inspect Payments health as a lead; keep a historical cause separate from the current hypothesis.
- **Exclude:** another tenant's incident, unrelated failures, or fixes with incompatible conditions.

## Limits

- **Implementation boundary:** cross-incident knowledge reads and writes are outside the selected scenarios.
- **Unverified:** retrieval relevance, stale-record handling, and resistance to misleading content need evaluation.
