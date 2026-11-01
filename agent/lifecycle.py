"""Accept an already-assigned alert and begin a new run on an open Incident."""

import copy
from datetime import datetime

from .constants import ALERT_PREFIX, ALERT_SOURCE, ErrorCode, EvidenceKind
from .ports import IncidentStore, RevisionConflict
from .schemas import Alert, Evidence, Incident, PastProposal, Scope, Window
from .validation import alert as parse_alert, number, text, validate_window


def add_alert_observations(incident: Incident, alert: Alert) -> None:
    count = sum(e.kind == EvidenceKind.ALERT for e in incident.evidence.values())
    for summary, data in (
        (
            f"Alert: 5xx rate {alert.error_rate_percent}%; baseline below {alert.baseline_error_rate_percent}%",
            {"error_rate_percent": number(alert.error_rate_percent, maximum=100)},
        ),
        (
            f"Alert: p95 {alert.p95_latency_ms} ms; baseline {alert.baseline_p95_latency_ms} ms",
            {"p95_latency_ms": number(alert.p95_latency_ms)},
        ),
    ):
        count += 1
        reference = ALERT_PREFIX + str(count)
        incident.evidence[reference] = Evidence(
            reference,
            EvidenceKind.ALERT,
            alert.service_id,
            ALERT_SOURCE,
            alert.window,
            summary,
            data,
        )


def start_followup_run(
    store: IncidentStore,
    incident_id: str,
    scope: Scope,
    *,
    expected_revision: int,
    alert: object,
    observation_window: Window,
) -> Incident:
    """Assignment is trusted input; this method does not correlate alerts."""
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError(ErrorCode.INVALID_INPUT.value)
    incident = store.load(text(incident_id), scope)
    if incident.revision != expected_revision:
        raise RevisionConflict(expected_revision, incident)
    if incident.proposal is None:
        raise ValueError(ErrorCode.RUN_NOT_FINISHED.value)
    incoming = parse_alert(alert)
    validate_window(observation_window)
    if incoming.service_id != incident.alert.service_id:
        raise ValueError(ErrorCode.OUT_OF_SCOPE.value)

    def end(window: Window) -> datetime:
        return datetime.fromisoformat(window.end.replace("Z", "+00:00"))

    if end(incoming.window) <= end(incident.observation_window) or end(
        observation_window
    ) < end(incoming.window):
        raise ValueError(ErrorCode.INVALID_INPUT.value)
    incident.proposal_history.append(
        PastProposal(
            incident.run_number,
            incident.observation_window,
            copy.deepcopy(incident.proposal),
            copy.deepcopy(incident.hypotheses),
        )
    )
    incident.run_number += 1
    incident.proposal, incident.hypotheses = None, []
    incident.observation_window = observation_window
    add_alert_observations(incident, incoming)
    store.save(incident, expected_revision)
    return incident
