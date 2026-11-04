# Shipping changes

- **Goal:** detect regressions and limit exposure when prompts, tools or models change.
- **Implemented:** versioned harness, recorded harness hashes/model information, pinned SDK dependencies, tests and five scripted scenarios. Live model selection is not pinned.
- **Planned:** production gates, shadow execution, canaries and rollback; no release pipeline exists.

## Release path — planned

```text
 Review + version → checks/evals → shadow → canary → expand
                         │           │        │
                         └── fail ───┴────────┴─→ hold / roll back
```

| Gate | Required evidence |
| --- | --- |
| Reproducible candidate | Version code, harness, model, SDK, tools/permissions and configuration; keep fixed per run |
| Deterministic checks | Schemas, scope, prerequisites, recovery and revision behavior pass |
| Judgment comparison | Repeat baseline/candidate on the same [eval set](evaluation.md); inspect category regressions and critical failures |
| Shadow | Use captured inputs or isolated tools; no authoritative Incident writes or responder messages; bound source traffic |
| Canary | Compare a small cohort with control; require quality, error-rate, latency and cost evidence before expansion |

- Agree thresholds/sample requirements **before** rollout: no observed critical violations; quality, latency and cost within agreed limits. Insufficient evidence means hold. Thresholds remain uncalibrated.

## Change-specific checks — planned

| Change | Focus |
| --- | --- |
| Prompt | Evidence use, uncertainty, human direction and stopping |
| Tool | Permissions, scope, response validation, failures and appropriate selection |
| Model | Repeated judgment/tool-choice comparison, latency and cost; select an explicit version where available |

## Rollback — planned

- Stop expansion on violations/breached thresholds; route new runs to the last known good compatible release. End unsafe runs before further tool use.
- Preserve Incident evidence/history; resume from current state. Require schema compatibility; do not rewind Incident data.
- Record affected runs, notify misled responders and add reviewed failures to regressions. Rollback cannot undo human actions.

## Limits and risks

- **Assumption:** comparable control traffic and reviewed samples; request success does not establish judgment quality.
- **Risks:** missed rare cases, mixed versions and incompatible rollback. Use representative cohorts, per-run release identity and rollback drills.
- **Reference:** [Google SRE: canarying releases](https://sre.google/workbook/canarying-releases/).
