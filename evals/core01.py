"""CORE-01 synthetic data and model replies, readable alongside docs/scenarios.md."""

import copy
from dataclasses import asdict

from agent.constants import CATALOGUE_SOURCE, EvidenceKind, ErrorCode, ToolName
from .model import FixtureModelServer
from agent.schemas import (
    Alert,
    Incident,
    JsonObject,
    Scope,
    SourceRequest,
    SourceResult,
    RunResult,
    Window,
)

CHECKOUT = "checkout-api"
PAYMENTS = "payments-api"
ORDERS = "orders-db"
SCOPE = Scope("tenant-checkout", "production", "eu-west-1")
ALERT_WINDOW = Window("2026-10-31T10:00:00Z", "2026-10-31T10:05:00Z")
OBSERVATION_WINDOW = Window("2026-10-31T10:01:00Z", "2026-10-31T10:06:00Z")

CATALOGUE: dict[str, JsonObject] = {
    CHECKOUT: {
        "owner": "Checkout team",
        "dependencies": [PAYMENTS, ORDERS],
        "sources": {
            ToolName.HEALTH.value: "metrics/checkout",
            ToolName.TRACES.value: "traces/checkout",
        },
    },
    PAYMENTS: {
        "owner": "Payments team",
        "dependencies": [],
        "sources": {ToolName.HEALTH.value: "metrics/payments"},
    },
}
HEALTH: dict[str, JsonObject] = {
    CHECKOUT: {"error_rate_percent": 11.8, "p95_latency_ms": 2300},
    PAYMENTS: {"error_rate_percent": 9.0, "p95_latency_ms": 2500},
}
TRACES: JsonObject = {
    "sample_size": 10,
    "dependency": PAYMENTS,
    "timeout_count": 8,
    "unclassified_count": 2,
}


def new_incident() -> Incident:
    alert = Alert(CHECKOUT, ALERT_WINDOW, 12.0, 2400, 1.0, 350)
    return Incident("INC-001", SCOPE, alert, OBSERVATION_WINDOW)


class SourceFixture:
    def __init__(
        self,
        *,
        payments_health: JsonObject | None = None,
        payments_summary: str | None = None,
        checkout_health: JsonObject | None = None,
        observation_window: Window = OBSERVATION_WINDOW,
    ) -> None:
        self.calls: list[SourceRequest] = []
        self.health = copy.deepcopy(HEALTH)
        self.observation_window = observation_window
        if checkout_health is not None:
            self.health[CHECKOUT] = copy.deepcopy(checkout_health)
        if payments_health is not None:
            self.health[PAYMENTS] = copy.deepcopy(payments_health)
        self.payments_summary = payments_summary

    def call(self, request: SourceRequest) -> SourceResult:
        self.calls.append(request)
        if request.scope != SCOPE or request.window != self.observation_window:
            raise ValueError(ErrorCode.OUT_OF_SCOPE.value)
        if request.tool == ToolName.CATALOGUE:
            data = CATALOGUE[request.service_id]
            expected_source = CATALOGUE_SOURCE
            summary = f"{request.service_id}: owner {data['owner']}; dependencies and source mappings returned"
        elif request.tool == ToolName.HEALTH:
            data = self.health[request.service_id]
            expected_source = CATALOGUE[request.service_id]["sources"][
                ToolName.HEALTH.value
            ]
            summary = f"{request.service_id}: {data['error_rate_percent']}% 5xx; p95 {data['p95_latency_ms']} ms"
            if request.service_id == PAYMENTS and self.payments_summary is not None:
                summary = self.payments_summary
        else:
            data = TRACES
            expected_source = CATALOGUE[CHECKOUT]["sources"][ToolName.TRACES.value]
            summary = "8/10 sampled failed checkout requests contain payment-call timeouts; 2 unclassified"
        if request.source_ref != expected_source:
            raise ValueError(ErrorCode.UNKNOWN_MAPPING.value)
        return {
            "scope": asdict(SCOPE),
            "service_id": request.service_id,
            "source_ref": expected_source,
            "window": asdict(self.observation_window),
            "summary": summary,
            "data": copy.deepcopy(data),
        }


def model_reply(request: JsonObject) -> JsonObject:
    """Deterministic fake model; no private cursor and no access to source transport."""
    card = FixtureModelServer.cards(request)[-1]
    if card["proposal"] is not None:
        return {"text": card["proposal"]["next_step"]}
    catalogue = card["catalogue"]
    evidence = list(card["evidence"].values())

    def collected(kind, service):
        return any(
            e["kind"] == kind
            and e["service_id"] == service
            and e["window"] == card["observation_window"]
            for e in evidence
        )

    if CHECKOUT not in catalogue:
        tool, service, question = (
            ToolName.CATALOGUE,
            CHECKOUT,
            "Who owns checkout, what does it depend on, and where is its telemetry?",
        )
    elif not collected(EvidenceKind.HEALTH, CHECKOUT):
        tool, service, question = (
            ToolName.HEALTH,
            CHECKOUT,
            "Does newer checkout health confirm continuing impact?",
        )
    elif not collected(EvidenceKind.TRACES, CHECKOUT):
        tool, service, question = (
            ToolName.TRACES,
            CHECKOUT,
            "Which dependency appears in sampled failed checkout requests?",
        )
    elif PAYMENTS not in catalogue:
        tool, service, question = (
            ToolName.CATALOGUE,
            PAYMENTS,
            "Who owns Payments and where can its health be checked?",
        )
    elif not collected(EvidenceKind.HEALTH, PAYMENTS):
        tool, service, question = (
            ToolName.HEALTH,
            PAYMENTS,
            "Does Payments health support the payment-timeout lead?",
        )
    else:
        refs = [
            e["reference"]
            for e in evidence
            if e["kind"] != EvidenceKind.ALERT
            and e["window"] == card["observation_window"]
        ]
        return {
            "tool": ToolName.PROPOSE,
            "arguments": {
                "proposal": {
                    "next_step": "Involve the Payments team and inspect payment errors and recent changes.",
                    "reason": "Checkout remains degraded; failed traces show payment-call timeouts, and Payments health is degraded in the same window.",
                    "evidence_ids": refs,
                    "uncertainty": "Root cause is unconfirmed; failed traces are a selected sample, and deployment history has not been checked.",
                },
                "hypotheses": [
                    {
                        "statement": "Payments-path degradation may contribute to checkout failures.",
                        "evidence_ids": refs,
                    }
                ],
            },
        }
    return {"tool": tool, "arguments": {"service_id": service, "question": question}}


def assess(result: "RunResult") -> list[str]:
    """Acceptance checks, independent of the fake model's chosen call order."""
    from agent.constants import IncidentStatus, RunStatus

    incident = result.incident
    collected = list(incident.evidence.values())
    health = {e.service_id for e in collected if e.kind == EvidenceKind.HEALTH}
    trace_refs = {
        e.reference
        for e in collected
        if e.kind == EvidenceKind.TRACES and e.service_id == CHECKOUT
    }
    health_refs = {
        e.reference
        for e in collected
        if e.kind == EvidenceKind.HEALTH and e.service_id == PAYMENTS
    }
    proposal = incident.proposal
    cited = set(proposal.evidence_ids) if proposal else set()
    checks = {
        "run_proposes": result.status == RunStatus.PROPOSED,
        "incident_remains_open": incident.status == IncidentStatus.OPEN,
        "alert_preserved": {"A1", "A2"} <= incident.evidence.keys(),
        "both_services_checked": {CHECKOUT, PAYMENTS} <= health,
        "checkout_traces_collected": bool(trace_refs),
        "owners_discovered": {CHECKOUT, PAYMENTS} <= incident.catalogue.keys(),
        "payment_lead_cited": bool(trace_refs & cited) and bool(health_refs & cited),
        "only_observation_references": bool(cited)
        and cited <= incident.evidence.keys(),
        "bounded_current_window": all(
            e.window == OBSERVATION_WINDOW
            for e in collected
            if e.kind != EvidenceKind.ALERT
        ),
        "scope_preserved": incident.scope == SCOPE,
        "uncertainty_present": proposal is not None and bool(proposal.uncertainty),
    }
    return [name for name, passed in checks.items() if not passed]
