"""Validated Incident updates; no SDK, fixtures, provider setup, or filesystem paths."""

import copy
from dataclasses import asdict, replace

from .constants import (
    CATALOGUE_PREFIX,
    OBSERVATION_PREFIX,
    CATALOGUE_SOURCE,
    ErrorCode,
    EvidenceKind,
    RunStatus,
    SOURCE_TOOLS,
    ToolName,
)
from .ports import IncidentStore, RevisionConflict, SourceTransport
from .lifecycle import add_alert_observations
from .schemas import (
    CompletedCall,
    Evidence,
    Hypothesis,
    Incident,
    JsonObject,
    ServiceContext,
    SourceRequest,
    TraceStep,
)
from .validation import (
    object_fields,
    proposal,
    proposal_context,
    source_result,
    text,
    texts,
    validate_window,
)


class Investigation:
    def __init__(
        self,
        incident: Incident,
        sources: SourceTransport,
        store: IncidentStore | None = None,
    ) -> None:
        text(incident.incident_id)
        for value in asdict(incident.scope).values():
            text(value)
        text(incident.alert.service_id)
        validate_window(incident.alert.window)
        validate_window(incident.observation_window)
        self.incident, self.sources = incident, sources
        self.store = store
        self.steps: list[TraceStep] = []
        self.status = (
            RunStatus.PROPOSED if incident.proposal else RunStatus.INVESTIGATING
        )
        self.stop_reason: str | None = None
        if not incident.evidence:
            add_alert_observations(incident, incident.alert)

    def context(self) -> JsonObject:
        return {
            "incident_card": asdict(self.incident),
            "run_status": self.status,
            "stop_reason": self.stop_reason,
        }

    def apply(self, tool: ToolName, value: object) -> JsonObject:
        previous = copy.deepcopy(self.incident)
        steps, status, reason = list(self.steps), self.status, self.stop_reason
        try:
            self._apply(tool, value)
            if self.incident != previous:
                if self.store is not None:
                    self.store.save(self.incident, previous.revision)
                else:
                    self.incident.revision = previous.revision + 1
            self.steps[-1] = replace(
                self.steps[-1],
                base_revision=previous.revision,
                revision=self.incident.revision,
            )
        except RevisionConflict as conflict:
            rejected = self.steps[-1]
            self.incident = conflict.current
            self.steps = steps + [
                replace(
                    rejected,
                    base_revision=previous.revision,
                    revision=conflict.current.revision,
                    accepted=False,
                    outcome="Rejected stale update: " + rejected.outcome,
                )
            ]
            self.status = (
                RunStatus.INVESTIGATING
                if self.incident.proposal is None
                else RunStatus.BLOCKED
            )
            self.stop_reason = (
                None
                if self.status == RunStatus.INVESTIGATING
                else ErrorCode.REVISION_CONFLICT.value
            )
            raise
        except Exception:
            self.incident = previous
            self.steps, self.status, self.stop_reason = steps, status, reason
            raise
        return self.context()

    def _apply(self, tool: ToolName, value: object) -> None:
        if not isinstance(tool, ToolName):
            raise ValueError(ErrorCode.INVALID_INPUT.value)
        if self.status != RunStatus.INVESTIGATING:
            raise ValueError(ErrorCode.FINISHED.value)
        if tool in SOURCE_TOOLS:
            args = object_fields(value, {"service_id", "question"})
            service_id, question = text(args["service_id"]), text(args["question"])
            known_services = {self.incident.alert.service_id}
            for entry in self.incident.catalogue.values():
                known_services.update(entry.dependencies)
            if service_id not in known_services:
                raise ValueError(ErrorCode.OUT_OF_SCOPE.value)
            source = CATALOGUE_SOURCE
            if tool != ToolName.CATALOGUE:
                entry = self.incident.catalogue.get(service_id)
                if entry is None or tool.value not in entry.sources:
                    raise ValueError(ErrorCode.UNKNOWN_MAPPING.value)
                source = entry.sources[tool.value]
            request = SourceRequest(
                tool,
                self.incident.scope,
                service_id,
                source,
                self.incident.observation_window,
            )
            for completed in self.incident.completed_calls:
                if completed.request == request:
                    self.steps.append(
                        TraceStep(
                            len(self.steps) + 1,
                            tool,
                            question,
                            service_id,
                            completed.finding_ref,
                            "Reused saved finding; no external source call",
                            True,
                        )
                    )
                    return
            result = source_result(self.sources.call(request), request)
            if tool == ToolName.CATALOGUE:
                reference = CATALOGUE_PREFIX + str(len(self.incident.catalogue) + 1)
                data = result["data"]
                self.incident.catalogue[service_id] = ServiceContext(
                    reference,
                    service_id,
                    data["owner"],
                    copy.deepcopy(data["dependencies"]),
                    copy.deepcopy(data["sources"]),
                )
            else:
                count = sum(
                    e.kind != EvidenceKind.ALERT
                    for e in self.incident.evidence.values()
                )
                reference = OBSERVATION_PREFIX + str(count + 1)
                kind = (
                    EvidenceKind.HEALTH
                    if tool == ToolName.HEALTH
                    else EvidenceKind.TRACES
                )
                self.incident.evidence[reference] = Evidence(
                    reference,
                    kind,
                    service_id,
                    source,
                    request.window,
                    result["summary"],
                    copy.deepcopy(result["data"]),
                )
            self.incident.completed_calls.append(CompletedCall(request, reference))
            self.steps.append(
                TraceStep(
                    len(self.steps) + 1,
                    tool,
                    question,
                    service_id,
                    reference,
                    result["summary"],
                )
            )
        elif tool == ToolName.PROPOSE:
            args = object_fields(value, {"proposal"}, {"hypotheses"})
            proposed = proposal(args["proposal"])
            proposal_context(self.incident, proposed)
            hypotheses = []
            raw = args.get("hypotheses", [])
            if not isinstance(raw, list):
                raise ValueError(ErrorCode.INVALID_INPUT.value)
            known = set(self.incident.evidence) | {
                entry.reference for entry in self.incident.catalogue.values()
            }
            for item in raw:
                body = object_fields(item, {"statement", "evidence_ids"})
                refs = texts(body["evidence_ids"])
                if not refs or not set(refs) <= known:
                    raise ValueError(ErrorCode.INVALID_REFERENCES.value)
                hypotheses.append(Hypothesis(text(body["statement"]), refs))
            self.incident.hypotheses = hypotheses
            self.incident.proposal = proposed
            self.status = RunStatus.PROPOSED
            self.steps.append(
                TraceStep(
                    len(self.steps) + 1,
                    tool,
                    proposed.reason,
                    None,
                    None,
                    proposed.next_step,
                )
            )
        else:
            args = object_fields(value, {"reason"})
            reason = text(args["reason"])
            self.status, self.stop_reason = RunStatus.BLOCKED, reason
            self.steps.append(
                TraceStep(len(self.steps) + 1, tool, reason, None, None, reason)
            )
