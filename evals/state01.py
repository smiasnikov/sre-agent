"""STATE-01: two real Python processes, persisted Incident, no SDK history."""

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from enum import Enum
from pathlib import Path

from agent.cli import OUTPUT_ROOT, PROJECT_ROOT, run_scenario
from agent.constants import DEFAULT_MAX_TURNS, ErrorCode, RunStatus, ToolName
from agent.schemas import JsonObject
from agent.storage import LocalIncidentStore
from . import CORE01, STATE01, core01
from .model import FixtureModelServer

BEFORE_TURN_LIMIT = 2
STATE_FILENAME = "incident.json"


class Phase(str, Enum):
    BEFORE = "before"
    AFTER = "after"


def replay_model_reply(request: JsonObject) -> JsonObject:
    """Deliberately replay saved requests, then reuse CORE-01's collection script."""
    cards = FixtureModelServer.cards(request)
    if len(cards) <= 2:
        tool = ToolName.CATALOGUE if len(cards) == 1 else ToolName.HEALTH
        return {
            "tool": tool,
            "arguments": {
                "service_id": core01.CHECKOUT,
                "question": "Repeat the saved request with different wording",
            },
        }
    return core01.model_reply(request)


def _worker(phase: Phase, directory: Path) -> list[str]:
    store = LocalIncidentStore(directory / STATE_FILENAME)
    trusted = core01.new_incident()
    incident = (
        store.load(trusted.incident_id, trusted.scope) if phase == Phase.AFTER else None
    )
    result = run_scenario(
        CORE01,
        output=directory / phase.value,
        store=store,
        incident=incident,
        max_turns=BEFORE_TURN_LIMIT if phase == Phase.BEFORE else DEFAULT_MAX_TURNS,
        model_reply=replay_model_reply if phase == Phase.AFTER else None,
    )
    if phase == Phase.BEFORE:
        valid = (
            result.status == RunStatus.BLOCKED
            and result.stop_reason == ErrorCode.TURN_LIMIT.value
        )
        return [] if valid else ["first_run_did_not_stop_at_limit"]
    return core01.assess(result)


def run_restart(directory: Path) -> list[str]:
    """Discard each worker entirely; only the Incident file crosses the boundary."""
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    # Reset only this generated scenario's record when rerunning the evaluation.
    (directory / STATE_FILENAME).unlink(missing_ok=True)
    for phase in Phase:
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "evals.state01",
                "--phase",
                phase.value,
                "--output",
                str(directory),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if process.returncode:
            return [f"{phase.value}_worker_failed: {process.stderr or process.stdout}"]
    before = json.loads((directory / Phase.BEFORE.value / "trace.json").read_text())
    after = json.loads((directory / Phase.AFTER.value / "trace.json").read_text())
    initial_request = after["runtime"]["first_model_request"]
    cards = FixtureModelServer.cards(initial_request)
    requests = (
        before["runtime"]["source_requests"] + after["runtime"]["source_requests"]
    )
    replayed = [step for step in after["steps"] if step["reused"]]
    trusted = core01.new_incident()
    saved = LocalIncidentStore(directory / STATE_FILENAME).load(
        trusted.incident_id, trusted.scope
    )
    checks = {
        "fresh_process": before["runtime"]["process_id"]
        != after["runtime"]["process_id"],
        "card_only_resume": len(cards) == 1
        and cards[0] == before["incident"]
        and all(message["role"] == "user" for message in initial_request["messages"]),
        "two_calls_before": len(before["runtime"]["source_requests"]) == 2,
        "three_calls_after": len(after["runtime"]["source_requests"]) == 3,
        "five_distinct_requests": len(requests) == 5
        and len({json.dumps(request, sort_keys=True) for request in requests}) == 5,
        "replays_reuse_references": [step["added_reference"] for step in replayed]
        == ["C1", "E1"],
        "evidence_preserved": all(
            after["incident"]["evidence"].get(ref) == item
            for ref, item in before["incident"]["evidence"].items()
        ),
        "catalogue_preserved": after["incident"]["catalogue"][core01.CHECKOUT]
        == before["incident"]["catalogue"][core01.CHECKOUT],
        "fresh_limits": before["runtime"]["max_turns"] == BEFORE_TURN_LIMIT
        and after["runtime"]["max_turns"] == DEFAULT_MAX_TURNS,
        "completed_calls_saved": len(saved.completed_calls) == 5
        and asdict(saved) == after["incident"],
        "proposal_saved": saved.proposal is not None
        and after["status"] == RunStatus.PROPOSED.value,
        "no_tool_errors": not before["runtime"]["tool_errors"]
        and not after["runtime"]["tool_errors"],
    }
    failures = [name for name, passed in checks.items() if not passed]
    lines = [
        f"# {STATE01}: restart trace",
        "",
        "- Real SDK orchestration; synthetic model and source data; no conversation history reused.",
        "- The first bounded run reaches its two-turn limit after saving C1/E1; the fresh run uses its own limits.",
        "",
        "| Phase | Process ID | External source calls | Reused findings | Turn limit |",
        "| --- | --- | --- | --- | --- |",
    ]
    for phase, result in ((Phase.BEFORE, before), (Phase.AFTER, after)):
        runtime = result["runtime"]
        lines.append(
            f"| {phase.value} | {runtime['process_id']} | {len(runtime['source_requests'])} | "
            f"{sum(step['reused'] for step in result['steps'])} | {runtime['max_turns']} |"
        )
    for phase in Phase:
        trace = (directory / phase.value / "trace.md").read_text()
        lines += [
            "",
            trace.replace(
                "# CORE-01 trace", f"## {phase.value.capitalize()} restart", 1
            ).replace("\n## Outcome", "\n### Outcome"),
        ]
    lines += ["", "## Acceptance", ""]
    lines += [
        f"- {name}: {'PASSED' if passed else 'FAILED'}"
        for name, passed in checks.items()
    ]
    (directory / "trace.md").write_text("\n".join(lines) + "\n")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=[phase.value for phase in Phase])
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT / STATE01.lower())
    args = parser.parse_args()
    if args.phase:
        failures = _worker(Phase(args.phase), args.output)
    else:
        failures = run_restart(args.output)
        print(STATE01 + ": " + ("PASSED" if not failures else "FAILED"))
        print("Trace: " + str(args.output / "trace.md"))
    if failures:
        print("\n".join(failures), file=sys.stderr)
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
