"""EVAL-01: real hard checks beside illustrative review ratings; no model judge."""

import argparse
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from agent.constants import EvidenceKind, ToolName
from agent.investigation import Investigation
from agent.schemas import Incident, Proposal
from agent.validation import proposal, proposal_context
from . import EVAL01, core01, core02

HARD_CHECK_PASSED = "passed"


class Criterion(str, Enum):
    GROUNDING = "Grounding"
    CONTEXT = "Context"
    USEFULNESS = "Usefulness"
    CALIBRATION = "Calibration"
    STOPPING = "Stopping"


class Rating(str, Enum):
    MET = "met"
    PARTLY_MET = "partly met"
    UNMET = "unmet"


class Verdict(str, Enum):
    ACCEPTABLE = "acceptable"
    UNACCEPTABLE = "unacceptable"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Candidate:
    name: str
    proposal: Proposal
    ratings: dict[Criterion, Rating]
    review_verdict: Verdict
    review_reason: str


@dataclass(frozen=True)
class CandidateResult:
    candidate: Candidate
    hard_error: str | None

    @property
    def verdict(self) -> Verdict:
        # A recorded positive review cannot override an invalid proposal.
        return Verdict.BLOCKED if self.hard_error else self.candidate.review_verdict


def checkout_context() -> Incident:
    """Prepare CORE-02 observations through existing validated source tools."""
    investigation = Investigation(core02.new_incident(), core02.SourceFixture())
    for tool, service in (
        (ToolName.CATALOGUE, core01.CHECKOUT),
        (ToolName.HEALTH, core01.CHECKOUT),
        (ToolName.TRACES, core01.CHECKOUT),
        (ToolName.CATALOGUE, core01.PAYMENTS),
        (ToolName.HEALTH, core01.PAYMENTS),
    ):
        investigation.apply(
            tool, {"service_id": service, "question": "Collect review context"}
        )
    return investigation.incident


def candidates() -> tuple[Candidate, ...]:
    """Synthetic proposals and illustrative labels, not independent human reviews."""
    return (
        Candidate(
            "Checkout client",
            Proposal(
                core02.NEXT_STEP, core02.REASON, ["E1", "E2", "E3"], core02.UNCERTAINTY
            ),
            {criterion: Rating.MET for criterion in Criterion},
            Verdict.ACCEPTABLE,
            "E1/E2 show Checkout impact and payment-call timeouts; E3 does not locate the timeout. Client-span inspection can distinguish causes.",
        ),
        Candidate(
            "Payments path",
            Proposal(
                "Ask Payments to inspect endpoint- and caller-specific errors for Checkout payment requests.",
                "E1 confirms Checkout impact and E2 shows payment-call timeouts. E3 is normal aggregate health, so inspect the affected request subset.",
                ["E1", "E2", "E3"],
                "Normal aggregates may hide a partial Payments failure; client or network issues remain possible.",
            ),
            {criterion: Rating.MET for criterion in Criterion},
            Verdict.ACCEPTABLE,
            "E3 is aggregate data; a targeted Payments check is a useful alternative to the Checkout-client check.",
        ),
        Candidate(
            "Unsupported conclusion",
            Proposal(
                "Stop investigating Payments and focus only on Checkout.",
                "E1 shows Checkout degradation and E2 contains payment-call timeouts, but E3 proves Payments cannot be responsible because its aggregate health is normal.",
                ["E1", "E2", "E3"],
                "The exact Checkout fault is not yet known.",
            ),
            {
                criterion: Rating.MET if criterion == Criterion.CONTEXT else Rating.UNMET
                for criterion in Criterion
            },
            Verdict.UNACCEPTABLE,
            "E3 cannot rule out partial Payments failure. Valid references and a nonempty uncertainty field do not make that conclusion supported.",
        ),
    )


def hard_check(incident: Incident, value: object) -> str | None:
    """Validate the proposal boundary and current evidence prerequisites, read-only."""
    try:
        proposal_context(incident, proposal(value))
    except ValueError as error:
        return str(error)
    return None


def evaluate(incident: Incident, candidate: Candidate) -> CandidateResult:
    return CandidateResult(candidate, hard_check(incident, asdict(candidate.proposal)))


def report(incident: Incident, results: list[CandidateResult]) -> str:
    def cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    lines = [
        f"# {EVAL01}: candidate review",
        "",
        "- Sources and proposals are synthetic. No model was called.",
        "- Hard checks execute application validation; review ratings/verdicts are illustrative fixture data, not independent human review or automated semantic grading.",
        "- Editing a proposal does not rescore its review fixture. These labels do not establish model quality.",
        f"- Incident: {incident.incident_id}; {incident.scope.tenant_id}; {incident.scope.environment}; {incident.scope.region}.",
        f"- Current window: {incident.observation_window.start} → {incident.observation_window.end}.",
        "",
        "## Available observations",
        "",
        "| Reference | Observation |",
        "| --- | --- |",
    ]
    for evidence in incident.evidence.values():
        if evidence.kind != EvidenceKind.ALERT:
            lines.append(f"| {evidence.reference} | {cell(evidence.summary)} |")
    lines += [
        "",
        "## Review summary",
        "",
        "| Candidate | Hard checks | Recorded review | Outcome |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        candidate = result.candidate
        lines.append(
            f"| {cell(candidate.name)} | {result.hard_error or HARD_CHECK_PASSED} | "
            f"{candidate.review_verdict.value} | {result.verdict.value} |"
        )
    lines += [
        "",
        "Hard-check failures block the outcome regardless of the recorded review.",
        "",
        "## Illustrative rubric ratings",
        "",
        "| Candidate | " + " | ".join(criterion.value for criterion in Criterion) + " |",
        "| --- | " + " | ".join("---" for _ in Criterion) + " |",
    ]
    for result in results:
        candidate = result.candidate
        lines.append(
            f"| {cell(candidate.name)} | "
            + " | ".join(candidate.ratings[criterion].value for criterion in Criterion)
            + " |"
        )
    for result in results:
        candidate, proposed = result.candidate, result.candidate.proposal
        lines += ["", "## " + candidate.name, "", "| Field | Value |", "| --- | --- |"]
        for label, value in (
            ("Next step", proposed.next_step),
            ("Reason", proposed.reason),
            ("Evidence", ", ".join(proposed.evidence_ids)),
            ("Uncertainty", proposed.uncertainty),
            ("Illustrative review reason", candidate.review_reason),
        ):
            lines.append(f"| {label} | {cell(value)} |")
    return "\n".join(lines) + "\n"


def run_evaluation(directory: Path) -> list[str]:
    incident = checkout_context()
    results = [evaluate(incident, candidate) for candidate in candidates()]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.md").write_text(report(incident, results))
    return [
        result.candidate.name + ": " + result.hard_error
        for result in results
        if result.hard_error is not None
    ]


def main() -> None:
    from agent.cli import OUTPUT_ROOT

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT / EVAL01.lower())
    args = parser.parse_args()
    failures = run_evaluation(args.output)
    print((args.output / "report.md").read_text())
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
