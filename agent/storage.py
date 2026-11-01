"""Local Incident persistence; strict decoding and atomic file replacement."""

import json
import os
import tempfile
import fcntl
import math
import time
from contextlib import contextmanager
from dataclasses import asdict, fields, replace
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .constants import (
    ALERT_ERRORS_REFERENCE,
    ALERT_LATENCY_REFERENCE,
    ALERT_SOURCE,
    ALERT_PREFIX,
    CATALOGUE_PREFIX,
    CATALOGUE_SOURCE,
    DEFAULT_LOCK_TIMEOUT_SECONDS,
    LOCK_RETRY_SECONDS,
    OBSERVATION_PREFIX,
    SOURCE_TOOLS,
    STATE_FORMAT_VERSION,
    ErrorCode,
    EvidenceKind,
    IncidentStatus,
    ToolName,
)
from .schemas import (
    CompletedCall,
    Evidence,
    Hypothesis,
    Incident,
    PastProposal,
    JsonObject,
    Scope,
    ServiceContext,
    SourceRequest,
    Window,
)
from .ports import RevisionConflict
from .validation import (
    alert as parse_alert,
    number,
    object_fields,
    proposal,
    proposal_context,
    selected_step,
    source_result,
    text,
    texts,
    validate_window,
)


def _record(value: object, schema: type) -> JsonObject:
    return object_fields(value, {field.name for field in fields(schema)})


def _scope(value: object) -> Scope:
    body = _record(value, Scope)
    return Scope(**{key: text(item) for key, item in body.items()})


def _window(value: object) -> Window:
    window = Window(**_record(value, Window))
    validate_window(window)
    return window


def _hypotheses(value: object, known: set[str]) -> list[Hypothesis]:
    if not isinstance(value, list):
        raise ValueError(ErrorCode.INVALID_STATE.value)
    result = []
    for raw in value:
        item = _record(raw, Hypothesis)
        refs = texts(item["evidence_ids"])
        if not refs or not set(refs) <= known:
            raise ValueError(ErrorCode.INVALID_STATE.value)
        result.append(Hypothesis(text(item["statement"]), refs))
    return result


def decode_incident(value: object, incident_id: str, scope: Scope) -> Incident:
    """Treat local files as external data, including their cross-references."""
    try:
        envelope = object_fields(value, {"format_version", "incident"})
        version = envelope["format_version"]
        if type(version) is not int or version != STATE_FORMAT_VERSION:
            raise ValueError(ErrorCode.INVALID_STATE.value)
        body = _record(envelope["incident"], Incident)
        if text(body["incident_id"]) != incident_id or _scope(body["scope"]) != scope:
            raise ValueError(ErrorCode.OUT_OF_SCOPE.value)
        alert = parse_alert(body["alert"])
        incident = Incident(
            incident_id,
            scope,
            alert,
            _window(body["observation_window"]),
            status=IncidentStatus(body["status"]),
        )
        if type(body["revision"]) is not int or body["revision"] < 0:
            raise ValueError(ErrorCode.INVALID_STATE.value)
        incident.revision = body["revision"]
        if not isinstance(body["catalogue"], dict) or not isinstance(
            body["evidence"], dict
        ):
            raise ValueError(ErrorCode.INVALID_STATE.value)
        for service, raw in body["catalogue"].items():
            item = _record(raw, ServiceContext)
            if text(service) != text(item["service_id"]):
                raise ValueError(ErrorCode.INVALID_STATE.value)
            incident.catalogue[service] = ServiceContext(
                text(item["reference"]),
                service,
                text(item["owner"]),
                texts(item["dependencies"]),
                item["sources"],
            )
        for reference, raw in body["evidence"].items():
            item = _record(raw, Evidence)
            if text(reference) != text(item["reference"]):
                raise ValueError(ErrorCode.INVALID_STATE.value)
            incident.evidence[reference] = Evidence(
                reference,
                EvidenceKind(item["kind"]),
                text(item["service_id"]),
                text(item["source_ref"]),
                _window(item["window"]),
                text(item["summary"]),
                item["data"],
            )
        for ref, data in (
            (ALERT_ERRORS_REFERENCE, {"error_rate_percent": alert.error_rate_percent}),
            (ALERT_LATENCY_REFERENCE, {"p95_latency_ms": alert.p95_latency_ms}),
        ):
            evidence = incident.evidence[ref]
            if (
                evidence.kind != EvidenceKind.ALERT
                or evidence.service_id != alert.service_id
                or evidence.source_ref != ALERT_SOURCE
                or evidence.window != alert.window
                or evidence.data != data
            ):
                raise ValueError(ErrorCode.INVALID_STATE.value)
        observed = {
            ref for ref, e in incident.evidence.items() if e.kind != EvidenceKind.ALERT
        }
        alert_refs = {
            ref for ref, e in incident.evidence.items() if e.kind == EvidenceKind.ALERT
        }
        if len(alert_refs) % 2 or alert_refs != {
            ALERT_PREFIX + str(i + 1) for i in range(len(alert_refs))
        }:
            raise ValueError(ErrorCode.INVALID_STATE.value)
        for i in range(1, len(alert_refs) + 1, 2):
            pair = [
                incident.evidence[ALERT_PREFIX + str(i + offset)] for offset in (0, 1)
            ]
            for evidence, key in zip(pair, ("error_rate_percent", "p95_latency_ms")):
                data = object_fields(evidence.data, {key})
                number(
                    data[key],
                    maximum=100 if key == "error_rate_percent" else float("inf"),
                )
                if (
                    evidence.source_ref != ALERT_SOURCE
                    or evidence.service_id != alert.service_id
                    or evidence.window != pair[0].window
                ):
                    raise ValueError(ErrorCode.INVALID_STATE.value)
        catalogue_refs = {entry.reference for entry in incident.catalogue.values()}
        if (
            set(incident.evidence) != observed | alert_refs
            or observed
            != {OBSERVATION_PREFIX + str(i + 1) for i in range(len(observed))}
            or catalogue_refs
            != {CATALOGUE_PREFIX + str(i + 1) for i in range(len(incident.catalogue))}
        ):
            raise ValueError(ErrorCode.INVALID_STATE.value)

        completed = body["completed_calls"]
        if not isinstance(completed, list):
            raise ValueError(ErrorCode.INVALID_STATE.value)
        known_services, recorded_refs = {alert.service_id}, set()
        for raw in completed:
            item = _record(raw, CompletedCall)
            args = _record(item["request"], SourceRequest)
            request = SourceRequest(
                ToolName(args["tool"]),
                _scope(args["scope"]),
                text(args["service_id"]),
                text(args["source_ref"]),
                _window(args["window"]),
            )
            ref = text(item["finding_ref"])
            if (
                request.tool not in SOURCE_TOOLS
                or request.scope != scope
                or request.service_id not in known_services
                or ref in recorded_refs
                or any(call.request == request for call in incident.completed_calls)
            ):
                raise ValueError(ErrorCode.INVALID_STATE.value)
            if request.tool == ToolName.CATALOGUE:
                entry = incident.catalogue[request.service_id]
                if request.source_ref != CATALOGUE_SOURCE or ref != entry.reference:
                    raise ValueError(ErrorCode.INVALID_STATE.value)
                data = {
                    key: asdict(entry)[key]
                    for key in ("owner", "dependencies", "sources")
                }
                summary = entry.owner
                known_services.update(entry.dependencies)
            else:
                entry = incident.catalogue[request.service_id]
                evidence = incident.evidence[ref]
                expected_kind = (
                    EvidenceKind.HEALTH
                    if request.tool == ToolName.HEALTH
                    else EvidenceKind.TRACES
                )
                if (
                    request.source_ref != entry.sources[request.tool.value]
                    or evidence.kind != expected_kind
                    or evidence.service_id != request.service_id
                    or evidence.source_ref != request.source_ref
                    or evidence.window != request.window
                ):
                    raise ValueError(ErrorCode.INVALID_STATE.value)
                data, summary = evidence.data, evidence.summary
            source_result(
                {
                    "scope": asdict(request.scope),
                    "service_id": request.service_id,
                    "source_ref": request.source_ref,
                    "window": asdict(request.window),
                    "summary": summary,
                    "data": data,
                },
                request,
            )
            incident.completed_calls.append(CompletedCall(request, ref))
            recorded_refs.add(ref)
        if recorded_refs != observed | catalogue_refs:
            raise ValueError(ErrorCode.INVALID_STATE.value)
        known = set(incident.evidence) | catalogue_refs
        incident.hypotheses = _hypotheses(body["hypotheses"], known)
        if body["proposal"] is not None:
            incident.proposal = proposal(body["proposal"])
            proposal_context(incident, incident.proposal)
        history = body["proposal_history"]
        if (
            not isinstance(history, list)
            or type(body["run_number"]) is not int
            or body["run_number"] != len(history) + 1
        ):
            raise ValueError(ErrorCode.INVALID_STATE.value)
        incident.run_number = body["run_number"]
        for index, raw in enumerate(history, start=1):
            item = _record(raw, PastProposal)
            if type(item["run_number"]) is not int or item["run_number"] != index:
                raise ValueError(ErrorCode.INVALID_STATE.value)
            past = PastProposal(
                index,
                _window(item["window"]),
                proposal(item["proposal"]),
                _hypotheses(item["hypotheses"], known),
            )
            next_window = (
                history[index]["window"]
                if index < len(history)
                else asdict(incident.observation_window)
            )
            # UTC windows have already been validated; compare actual instants.
            if datetime.fromisoformat(
                past.window.end.replace("Z", "+00:00")
            ) >= datetime.fromisoformat(next_window["end"].replace("Z", "+00:00")):
                raise ValueError(ErrorCode.INVALID_STATE.value)
            proposal_context(
                replace(incident, observation_window=past.window), past.proposal
            )
            incident.proposal_history.append(past)
        if body["selected_next_step"] is not None:
            incident.selected_next_step = selected_step(body["selected_next_step"])
            if (
                not set(incident.selected_next_step.evidence_ids)
                <= incident.evidence.keys()
            ):
                raise ValueError(ErrorCode.INVALID_STATE.value)
        return incident
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        if str(error) == ErrorCode.OUT_OF_SCOPE.value:
            raise
        raise ValueError(ErrorCode.INVALID_STATE.value) from error


class LocalIncidentStore:
    """Cooperating processes on one Unix host; no power-loss guarantee."""

    def __init__(
        self, path: Path, *, lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS
    ) -> None:
        if (
            isinstance(lock_timeout_seconds, bool)
            or not isinstance(lock_timeout_seconds, (int, float))
            or not math.isfinite(lock_timeout_seconds)
            or lock_timeout_seconds <= 0
        ):
            raise ValueError(ErrorCode.INVALID_INPUT.value)
        self.path = path.resolve()
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.lock_timeout_seconds = lock_timeout_seconds

    @contextmanager
    def _locked(self) -> Iterator[None]:
        # Lock a stable sibling file: the Incident file's inode is replaced.
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock_path.open("a") as stream:
                deadline = time.monotonic() + self.lock_timeout_seconds
                while True:
                    try:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise ValueError(ErrorCode.LOCK_TIMEOUT.value)
                        time.sleep(min(LOCK_RETRY_SECONDS, remaining))
                try:
                    yield
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        except OSError as error:
            raise ValueError(ErrorCode.STORAGE_FAILURE.value) from error

    def create(self, incident: Incident) -> None:
        with self._locked():
            if self.path.exists():
                raise ValueError(ErrorCode.INCIDENT_EXISTS.value)
            if type(incident.revision) is not int or incident.revision != 0:
                raise ValueError(ErrorCode.INVALID_STATE.value)
            self._write(incident)

    def save(self, incident: Incident, expected_revision: int) -> None:
        if (
            type(expected_revision) is not int
            or expected_revision < 0
            or type(incident.revision) is not int
            or incident.revision != expected_revision
        ):
            raise ValueError(ErrorCode.INVALID_STATE.value)
        with self._locked():
            current = self.load(incident.incident_id, incident.scope)
            if current.revision != expected_revision:
                raise RevisionConflict(expected_revision, current)
            updated = replace(incident, revision=expected_revision + 1)
            self._write(updated)
            incident.revision = updated.revision

    def _write(self, incident: Incident) -> None:
        temporary: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(
                    {
                        "format_version": STATE_FORMAT_VERSION,
                        "incident": asdict(incident),
                    },
                    stream,
                    allow_nan=False,
                )
                stream.write("\n")
            os.replace(temporary, self.path)
        except (OSError, ValueError, TypeError) as error:
            raise ValueError(ErrorCode.STORAGE_FAILURE.value) from error
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def load(self, incident_id: str, scope: Scope) -> Incident:
        try:
            value = json.loads(self.path.read_text())
        except OSError as error:
            raise ValueError(ErrorCode.STORAGE_FAILURE.value) from error
        except ValueError as error:
            raise ValueError(ErrorCode.INVALID_STATE.value) from error
        return decode_incident(value, text(incident_id), scope)
