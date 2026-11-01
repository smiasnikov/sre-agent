"""Human Incident updates from a trusted caller; not exposed as model tools."""

from datetime import datetime, timezone

from .constants import ErrorCode
from .ports import IncidentStore, RevisionConflict
from .schemas import Incident, Scope
from .validation import object_fields, selected_step, text


def select_next_step(
    store: IncidentStore,
    incident_id: str,
    scope: Scope,
    *,
    expected_revision: int,
    responder_id: str,
    value: object,
) -> Incident:
    """Caller supplies authorized identity/scope; code supplies attribution/time."""
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError(ErrorCode.INVALID_INPUT.value)
    incident = store.load(text(incident_id), scope)
    if incident.revision != expected_revision:
        raise RevisionConflict(expected_revision, incident)
    body = object_fields(value, {"next_step", "owner", "reason", "evidence_ids"})
    selection = selected_step(
        dict(
            body,
            decision_maker=text(responder_id),
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
    )
    if not set(selection.evidence_ids) <= incident.evidence.keys():
        raise ValueError(ErrorCode.INVALID_REFERENCES.value)
    incident.selected_next_step = selection
    store.save(incident, expected_revision)
    return incident
