"""Internal dataclasses and the external tool-result JSON contract."""

from dataclasses import dataclass, field
from typing import Any, TypedDict

from .constants import EvidenceKind, IncidentStatus, RunStatus, ToolName

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    environment: str
    region: str


@dataclass(frozen=True)
class Window:
    start: str
    end: str


@dataclass(frozen=True)
class Alert:
    service_id: str
    window: Window
    error_rate_percent: float
    p95_latency_ms: float
    baseline_error_rate_percent: float
    baseline_p95_latency_ms: float


@dataclass(frozen=True)
class Evidence:
    reference: str
    kind: EvidenceKind
    service_id: str
    source_ref: str
    window: Window
    summary: str
    data: JsonObject


@dataclass(frozen=True)
class ServiceContext:
    reference: str
    service_id: str
    owner: str
    dependencies: list[str]
    sources: dict[str, str]


@dataclass(frozen=True)
class Hypothesis:
    statement: str
    evidence_ids: list[str]


@dataclass(frozen=True)
class Proposal:
    next_step: str
    reason: str
    evidence_ids: list[str]
    uncertainty: str


@dataclass(frozen=True)
class SelectedStep:
    next_step: str
    owner: str
    reason: str
    evidence_ids: list[str]
    decision_maker: str
    decided_at: str


@dataclass(frozen=True)
class PastProposal:
    run_number: int
    window: Window
    proposal: Proposal
    hypotheses: list[Hypothesis]


@dataclass
class Incident:
    incident_id: str
    scope: Scope
    alert: Alert
    observation_window: Window
    catalogue: dict[str, ServiceContext] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    proposal: Proposal | None = None
    status: IncidentStatus = IncidentStatus.OPEN
    completed_calls: list["CompletedCall"] = field(default_factory=list)
    revision: int = 0
    selected_next_step: SelectedStep | None = None
    run_number: int = 1
    proposal_history: list[PastProposal] = field(default_factory=list)


@dataclass(frozen=True)
class SourceRequest:
    tool: ToolName
    scope: Scope
    service_id: str
    source_ref: str
    window: Window


@dataclass(frozen=True)
class CompletedCall:
    request: SourceRequest
    finding_ref: str


class SourceResult(TypedDict):
    scope: JsonObject
    service_id: str
    source_ref: str
    window: JsonObject
    summary: str
    data: JsonObject


@dataclass(frozen=True)
class TraceStep:
    number: int
    tool: ToolName
    question: str
    service_id: str | None
    added_reference: str | None
    outcome: str
    reused: bool = False
    base_revision: int | None = None
    revision: int | None = None
    accepted: bool = True


@dataclass(frozen=True)
class RunResult:
    incident: Incident
    steps: list[TraceStep]
    runtime: JsonObject
    status: RunStatus
    stop_reason: str | None = None
