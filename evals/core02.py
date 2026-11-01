"""CORE-02 synthetic data and scripted output; no independent reasoning judge."""

import copy

from agent.constants import EvidenceKind, ToolName
from agent.schemas import JsonObject, RunResult
from . import core01
from .core01 import PAYMENTS, new_incident as new_incident

NORMAL_HEALTH: JsonObject = {"error_rate_percent": 0.2, "p95_latency_ms": 180}
NORMAL_SUMMARY = "payments-api: normal aggregate health; 0.2% 5xx; p95 180 ms"
NEXT_STEP = "Ask the Checkout owner to inspect failed payment-client spans and related logs for timeout location and affected requests."
REASON = "Checkout remains degraded and sampled failed traces show payment-call timeouts, while Payments aggregate health is normal in the same window. Inspecting the request path can distinguish Checkout client, network and partial Payments issues."
UNCERTAINTY = "Payments-wide degradation is unconfirmed. Normal aggregates do not rule out a partial Payments failure; the selected trace sample does not establish a root cause. Detailed logs and deployment history have not been checked."
HYPOTHESIS = "A Checkout client, network or partial Payments issue may explain payment-call timeouts despite normal aggregate Payments health."


class SourceFixture(core01.SourceFixture):
    def __init__(self) -> None:
        super().__init__(payments_health=NORMAL_HEALTH, payments_summary=NORMAL_SUMMARY)


def model_reply(request: JsonObject) -> JsonObject:
    """Reuse the collection script, substituting CORE-02's expected proposal."""
    selected = core01.model_reply(request)
    if selected.get("tool") == ToolName.PROPOSE:
        args = selected["arguments"]
        args["proposal"].update(
            next_step=NEXT_STEP, reason=REASON, uncertainty=UNCERTAINTY
        )
        args["hypotheses"] = [
            {
                "statement": HYPOTHESIS,
                "evidence_ids": copy.deepcopy(args["proposal"]["evidence_ids"]),
            }
        ]
    return selected


def assess(result: RunResult) -> list[str]:
    """Check data and scripted-output preservation, not semantic reasoning."""
    failures = core01.assess(result)
    evidence = result.incident.evidence
    payment_health = [
        e
        for e in evidence.values()
        if e.kind == EvidenceKind.HEALTH and e.service_id == PAYMENTS
    ]
    proposal = result.incident.proposal
    observations = {
        e.reference for e in evidence.values() if e.kind != EvidenceKind.ALERT
    }
    source_steps = [s for s in result.steps if s.service_id is not None]
    checks = {
        "normal_payments_health_preserved": len(payment_health) == 1
        and payment_health[0].data == NORMAL_HEALTH
        and payment_health[0].summary == NORMAL_SUMMARY,
        "all_observations_cited": proposal is not None
        and set(proposal.evidence_ids) == observations,
        "scripted_proposal_preserved": proposal is not None
        and (proposal.next_step, proposal.reason, proposal.uncertainty)
        == (NEXT_STEP, REASON, UNCERTAINTY),
        "scripted_hypothesis_preserved": len(result.incident.hypotheses) == 1
        and result.incident.hypotheses[0].statement == HYPOTHESIS
        and set(result.incident.hypotheses[0].evidence_ids) == observations,
        "no_repeated_source_queries": len(source_steps) == 5
        and len({(s.tool, s.service_id) for s in source_steps}) == 5,
    }
    return failures + [name for name, passed in checks.items() if not passed]
