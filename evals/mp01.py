"""MP-01: simulated human update between model input and proposal execution."""

import argparse
from dataclasses import asdict
from pathlib import Path

from agent.adapters import load_guidance, write_artifacts
from agent.cli import OUTPUT_ROOT, PROJECT_ROOT, run_scenario
from agent.collaboration import select_next_step
from agent.constants import ErrorCode, RunStatus, ToolName
from agent.investigation import Investigation
from agent.schemas import JsonObject, RunResult
from agent.storage import LocalIncidentStore
from . import CORE01, MP01, core01
from .model import FixtureModelServer

HUMAN_ACTOR = "responder-1"
HUMAN_STEP: JsonObject = {
    "next_step": "Checkout owner inspects failed payment-client spans and logs",
    "owner": "Checkout team",
    "reason": "Timeout location remains unknown",
    "evidence_ids": ["E1", "E2", "E3"],
}
REVISED_STEP = "Support the Checkout-owned timeout inspection by correlating failed payment-client spans with Payments health."
REVISED_REASON = "The responder selected Checkout-owned inspection. Payment-call timeouts and degraded Payments health support that check without establishing the timeout location or root cause."


def model_reply(request: JsonObject) -> JsonObject:
    """Expected replies are scripted from the card, not independently reasoned."""
    card = FixtureModelServer.cards(request)[-1]
    selected = core01.model_reply(request)
    if (
        card["selected_next_step"] is not None
        and selected.get("tool") == ToolName.PROPOSE
    ):
        selected["arguments"]["proposal"].update(
            next_step=REVISED_STEP, reason=REVISED_REASON
        )
    return selected


def run_multiplayer(directory: Path) -> RunResult:
    directory.mkdir(parents=True, exist_ok=True)
    record = directory / "incident.json"
    # Only generated synthetic state is reset when rerunning this evaluation.
    record.unlink(missing_ok=True)
    store = LocalIncidentStore(record)
    prepared = Investigation(core01.new_incident(), core01.SourceFixture(), store)
    store.create(prepared.incident)
    for tool, service in (
        (ToolName.CATALOGUE, core01.CHECKOUT),
        (ToolName.HEALTH, core01.CHECKOUT),
        (ToolName.TRACES, core01.CHECKOUT),
        (ToolName.CATALOGUE, core01.PAYMENTS),
        (ToolName.HEALTH, core01.PAYMENTS),
    ):
        prepared.apply(
            tool, {"service_id": service, "question": "Prepare shared findings"}
        )
    initial = prepared.context()
    human_update: JsonObject = {}

    def interleave_human_update(request: JsonObject) -> JsonObject:
        # Test driver acts after the model received r5 and before its tool executes.
        if not human_update:
            current = select_next_step(
                store,
                prepared.incident.incident_id,
                prepared.incident.scope,
                expected_revision=prepared.incident.revision,
                responder_id=HUMAN_ACTOR,
                value=HUMAN_STEP,
            )
            assert current.selected_next_step is not None
            human_update.update(
                revision=current.revision, selection=asdict(current.selected_next_step)
            )
        return model_reply(request)

    result = run_scenario(
        CORE01,
        store=store,
        incident=store.load(prepared.incident.incident_id, prepared.incident.scope),
        model_reply=interleave_human_update,
    )
    result.runtime.update(scenario=MP01, human_update=human_update)
    system, descriptions, _ = load_guidance(PROJECT_ROOT / "harness")
    write_artifacts(directory, result, initial, system, descriptions)
    saved = store.load(result.incident.incident_id, result.incident.scope)
    if asdict(saved) != asdict(result.incident):
        raise AssertionError("Saved Incident differs from the SDK result")
    return result


def assess(result: RunResult) -> list[str]:
    failures = core01.assess(result)
    initial = FixtureModelServer.cards(result.runtime["first_model_request"])[-1]
    selection = result.incident.selected_next_step
    steps = result.steps
    checks = {
        "started_at_revision_5": initial["revision"] == 5
        and initial["selected_next_step"] is None,
        "human_committed_revision_6": result.runtime["human_update"]["revision"] == 6,
        "stale_proposal_rejected": len(steps) == 2
        and not steps[0].accepted
        and (steps[0].base_revision, steps[0].revision) == (5, 6),
        "revised_proposal_accepted": len(steps) == 2
        and steps[1].accepted
        and (steps[1].base_revision, steps[1].revision) == (6, 7),
        "human_selection_preserved": selection is not None
        and asdict(selection) == result.runtime["human_update"]["selection"]
        and selection.decision_maker == HUMAN_ACTOR,
        "findings_preserved": all(
            asdict(result.incident)[key] == initial[key]
            for key in ("evidence", "catalogue", "completed_calls")
        ),
        "no_repeated_sources": result.runtime["source_requests"] == [],
        "scripted_reassessment_preserved": result.incident.proposal is not None
        and result.incident.proposal.next_step == REVISED_STEP
        and result.incident.proposal.reason == REVISED_REASON,
        "expected_conflict_only": [
            error["error"] for error in result.runtime["tool_errors"]
        ]
        == [ErrorCode.REVISION_CONFLICT.value],
        "finished_at_revision_7": result.incident.revision == 7
        and result.status == RunStatus.PROPOSED,
    }
    return failures + [name for name, passed in checks.items() if not passed]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT / MP01.lower())
    args = parser.parse_args()
    failures = assess(run_multiplayer(args.output))
    print(
        MP01 + ": " + ("PASSED" if not failures else "FAILED: " + ", ".join(failures))
    )
    print("Trace: " + str(args.output / "trace.md"))
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
