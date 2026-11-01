"""STATE-02: assigned alert starts R2; retain P1 and gather current evidence."""

import argparse
from dataclasses import asdict
from pathlib import Path

from agent.adapters import load_guidance, write_artifacts
from agent.cli import OUTPUT_ROOT, PROJECT_ROOT, run_scenario
from agent.constants import EvidenceKind, RunStatus
from agent.lifecycle import start_followup_run
from agent.schemas import Alert, JsonObject, RunResult, Window
from agent.storage import LocalIncidentStore
from . import CORE01, STATE02, core01, core02
from .model import FixtureModelServer

NEW_WINDOW = Window("2026-10-31T10:11:00Z", "2026-10-31T10:16:00Z")
NEW_ALERT = Alert(core01.CHECKOUT, NEW_WINDOW, 8.0, 1800, 1.0, 350)
SOURCE_OPTIONS: JsonObject = {
    "observation_window": NEW_WINDOW,
    "checkout_health": {"error_rate_percent": 8.0, "p95_latency_ms": 1800},
    "payments_health": core02.NORMAL_HEALTH,
    "payments_summary": core02.NORMAL_SUMMARY,
}


def run_followup(directory: Path) -> tuple[RunResult, RunResult]:
    directory.mkdir(parents=True, exist_ok=True)
    record = directory / "incident.json"
    # Reset only this evaluation's generated synthetic record.
    record.unlink(missing_ok=True)
    store = LocalIncidentStore(record)
    first = run_scenario(CORE01, store=store)
    if core01.assess(first):
        raise AssertionError("R1 did not satisfy CORE-01")
    prepared = start_followup_run(
        store,
        first.incident.incident_id,
        first.incident.scope,
        expected_revision=first.incident.revision,
        alert=asdict(NEW_ALERT),
        observation_window=NEW_WINDOW,
    )
    second = run_scenario(
        CORE01,
        store=store,
        incident=prepared,
        source_options=SOURCE_OPTIONS,
        model_reply=core02.model_reply,
    )
    system, descriptions, _ = load_guidance(PROJECT_ROOT / "harness")
    for result in (first, second):
        result.runtime["scenario"] = STATE02
        initial = FixtureModelServer.cards(result.runtime["first_model_request"])[0]
        write_artifacts(
            directory / f"run-{result.incident.run_number}",
            result,
            {"incident_card": initial},
            system,
            descriptions,
        )
    saved = store.load(first.incident.incident_id, first.incident.scope)
    if asdict(saved) != asdict(second.incident):
        raise AssertionError("Saved Incident differs from R2 result")
    lines = [
        f"# {STATE02}: two runs on one Incident",
        "",
        "- Real SDK orchestration; synthetic sources and scripted model replies. No live model.",
        "- The new alert was already assigned to INC-001 by the trusted caller; no alert correlation is performed.",
        f"- Assigned alert A3/A4 starts R2: Incident revision {first.incident.revision} → {second.runtime['initial_revision']}.",
        "",
        "| Run | Observation window | External calls | Proposal evidence |",
        "| --- | --- | --- | --- |",
    ]
    for result in (first, second):
        incident = result.incident
        refs = incident.proposal.evidence_ids if incident.proposal else []
        lines.append(
            f"| R{incident.run_number} | {incident.observation_window.start} → {incident.observation_window.end} | "
            f"{len(result.runtime['source_requests'])} | {', '.join(refs)} |"
        )
    for result in (first, second):
        run_number = result.incident.run_number
        trace = (
            (directory / f"run-{run_number}" / "trace.md").read_text().split("\n", 1)[1]
        )
        lines += ["", f"## Run R{run_number}", trace.replace("\n## ", "\n### ")]
    failures = assess(first, second)
    lines += [
        "",
        "## Acceptance",
        "",
        "PASSED" if not failures else ", ".join(failures),
    ]
    (directory / "trace.md").write_text("\n".join(lines) + "\n")
    return first, second


def assess(first: RunResult, second: RunResult) -> list[str]:
    before, after = first.incident, second.incident
    initial = FixtureModelServer.cards(second.runtime["first_model_request"])[0]
    initial_request = second.runtime["first_model_request"]
    refs = set(after.proposal.evidence_ids) if after.proposal else set()
    current = [
        e
        for e in after.evidence.values()
        if e.window == NEW_WINDOW and e.kind != EvidenceKind.ALERT
    ]
    checks = {
        "same_open_incident": after.incident_id == before.incident_id
        and after.scope == before.scope
        and after.status == before.status,
        "fresh_run": after.run_number == 2
        and initial["proposal"] is None
        and initial["run_number"] == 2,
        "history_preserved": len(after.proposal_history) == 1
        and asdict(after.proposal_history[0])
        == {
            "run_number": 1,
            "window": asdict(before.observation_window),
            "proposal": asdict(before.proposal) if before.proposal else None,
            "hypotheses": [asdict(h) for h in before.hypotheses],
        },
        "previous_findings_preserved": all(
            after.evidence.get(ref) == item for ref, item in before.evidence.items()
        )
        and after.catalogue == before.catalogue
        and after.alert == before.alert,
        "new_alert_preserved": all(
            ref in after.evidence
            and after.evidence[ref].kind == EvidenceKind.ALERT
            and after.evidence[ref].window == NEW_WINDOW
            for ref in ("A3", "A4")
        ),
        "fresh_observations": len(current) == 3 and refs == {"E4", "E5", "E6"},
        "new_payments_health": any(
            e.service_id == core01.PAYMENTS and e.data == core02.NORMAL_HEALTH
            for e in current
        ),
        "proposal_reassessed": after.proposal is not None
        and after.proposal.next_step == core02.NEXT_STEP
        and after.proposal.reason == core02.REASON,
        "three_new_source_calls": len(second.runtime["source_requests"]) == 3
        and all(
            request["window"] == asdict(NEW_WINDOW)
            for request in second.runtime["source_requests"]
        ),
        "completed_calls_preserved": len(after.completed_calls) == 8
        and after.completed_calls[:5] == before.completed_calls,
        "fresh_limits": first.runtime["max_turns"] == second.runtime["max_turns"],
        "fresh_conversation": len(FixtureModelServer.cards(initial_request)) == 1
        and all(message["role"] == "user" for message in initial_request["messages"]),
        "both_runs_proposed": first.status == second.status == RunStatus.PROPOSED,
        "no_tool_errors": not first.runtime["tool_errors"]
        and not second.runtime["tool_errors"],
    }
    return [name for name, passed in checks.items() if not passed]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT / STATE02.lower())
    args = parser.parse_args()
    failures = assess(*run_followup(args.output))
    print(
        STATE02
        + ": "
        + ("PASSED" if not failures else "FAILED: " + ", ".join(failures))
    )
    print("Trace: " + str(args.output / "trace.md"))
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
