"""Runtime validation of model arguments and external source data."""

import math
from datetime import datetime, timedelta

from .constants import (
    ErrorCode,
    EvidenceKind,
    MAX_TRACE_SAMPLE_SIZE,
    MAX_WINDOW_SECONDS,
    ToolName,
)
from .schemas import (
    Alert,
    Incident,
    JsonObject,
    Proposal,
    SelectedStep,
    SourceRequest,
    Window,
)


def text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(ErrorCode.INVALID_INPUT.value)
    return value


def object_fields(
    value: object, required: set[str], optional: set[str] | None = None
) -> JsonObject:
    if (
        not isinstance(value, dict)
        or not required <= value.keys()
        or value.keys() - required - (optional or set())
    ):
        raise ValueError(ErrorCode.INVALID_INPUT.value)
    return value


def texts(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(ErrorCode.INVALID_INPUT.value)
    return [text(item) for item in value]


def number(value: object, minimum: float = 0, maximum: float = math.inf) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(ErrorCode.INVALID_RESPONSE.value)
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(ErrorCode.INVALID_RESPONSE.value)
    return float(value)


def validate_window(window: Window) -> None:
    start, end = [
        datetime.fromisoformat(text(value).replace("Z", "+00:00"))
        for value in (window.start, window.end)
    ]
    if (
        any(value.utcoffset() != timedelta(0) for value in (start, end))
        or not 0 < (end - start).total_seconds() <= MAX_WINDOW_SECONDS
    ):
        raise ValueError(ErrorCode.INVALID_INPUT.value)


def alert(value: object) -> Alert:
    body = object_fields(
        value,
        {
            "service_id",
            "window",
            "error_rate_percent",
            "p95_latency_ms",
            "baseline_error_rate_percent",
            "baseline_p95_latency_ms",
        },
    )
    window = Window(**object_fields(body["window"], {"start", "end"}))
    validate_window(window)
    return Alert(
        text(body["service_id"]),
        window,
        number(body["error_rate_percent"], maximum=100),
        number(body["p95_latency_ms"]),
        number(body["baseline_error_rate_percent"], maximum=100),
        number(body["baseline_p95_latency_ms"]),
    )


def proposal(value: object) -> Proposal:
    body = object_fields(value, {"next_step", "reason", "evidence_ids", "uncertainty"})
    references = texts(body["evidence_ids"])
    if not references:
        raise ValueError(ErrorCode.INVALID_REFERENCES.value)
    return Proposal(
        text(body["next_step"]),
        text(body["reason"]),
        references,
        text(body["uncertainty"]),
    )


def proposal_context(incident: Incident, proposed: Proposal) -> None:
    references = set(proposed.evidence_ids)
    if not references <= incident.evidence.keys() or not any(
        incident.evidence[ref].kind != EvidenceKind.ALERT for ref in references
    ):
        raise ValueError(ErrorCode.INVALID_REFERENCES.value)
    # Historical references may be cited, but cannot satisfy current readiness.
    current = [
        e
        for e in incident.evidence.values()
        if e.window == incident.observation_window and e.reference in references
    ]
    health = {e.service_id for e in current if e.kind == EvidenceKind.HEALTH}
    traces = [
        e
        for e in current
        if e.kind == EvidenceKind.TRACES and e.service_id == incident.alert.service_id
    ]
    dependencies = {e.data["dependency"] for e in traces if e.data["timeout_count"] > 0}
    if (
        incident.alert.service_id not in health
        or not traces
        or not dependencies <= health
    ):
        raise ValueError(ErrorCode.INCOMPLETE_CONTEXT.value)


def selected_step(value: object) -> SelectedStep:
    body = object_fields(
        value,
        {
            "next_step",
            "owner",
            "reason",
            "evidence_ids",
            "decision_maker",
            "decided_at",
        },
    )
    references = texts(body["evidence_ids"])
    if not references:
        raise ValueError(ErrorCode.INVALID_REFERENCES.value)
    decided_at = text(body["decided_at"])
    if datetime.fromisoformat(
        decided_at.replace("Z", "+00:00")
    ).utcoffset() != timedelta(0):
        raise ValueError(ErrorCode.INVALID_INPUT.value)
    return SelectedStep(
        text(body["next_step"]),
        text(body["owner"]),
        text(body["reason"]),
        references,
        text(body["decision_maker"]),
        decided_at,
    )


def source_result(value: object, request: SourceRequest) -> JsonObject:
    from dataclasses import asdict

    body = object_fields(
        value, {"scope", "service_id", "source_ref", "window", "summary", "data"}
    )
    if (
        body["scope"] != asdict(request.scope)
        or body["service_id"] != request.service_id
    ):
        raise ValueError(ErrorCode.OUT_OF_SCOPE.value)
    if body["source_ref"] != request.source_ref or body["window"] != asdict(
        request.window
    ):
        raise ValueError(ErrorCode.INVALID_RESPONSE.value)
    text(body["summary"])
    data = body["data"]
    if request.tool == ToolName.CATALOGUE:
        data = object_fields(data, {"owner", "dependencies", "sources"})
        text(data["owner"])
        texts(data["dependencies"])
        if not isinstance(data["sources"], dict):
            raise ValueError(ErrorCode.INVALID_RESPONSE.value)
        for name, location in data["sources"].items():
            if name not in (ToolName.HEALTH, ToolName.TRACES):
                raise ValueError(ErrorCode.INVALID_RESPONSE.value)
            text(location)
    elif request.tool == ToolName.HEALTH:
        data = object_fields(data, {"error_rate_percent", "p95_latency_ms"})
        number(data["error_rate_percent"], maximum=100)
        number(data["p95_latency_ms"])
    else:
        data = object_fields(
            data, {"sample_size", "dependency", "timeout_count", "unclassified_count"}
        )
        for key in ("sample_size", "timeout_count", "unclassified_count"):
            if (
                type(data[key]) is not int
                or not 0 <= data[key] <= MAX_TRACE_SAMPLE_SIZE
            ):
                raise ValueError(ErrorCode.INVALID_RESPONSE.value)
        if data["sample_size"] != data["timeout_count"] + data["unclassified_count"]:
            raise ValueError(ErrorCode.INVALID_RESPONSE.value)
        text(data["dependency"])
    return body
