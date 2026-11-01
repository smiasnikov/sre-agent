"""Composition root; scenario data and providers are wired here."""

import argparse
import asyncio
import os
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from evals import CORE01, SCENARIOS

from .adapters import load_guidance, trace_markdown, write_artifacts
from .constants import DEFAULT_MAX_TURNS, DEFAULT_TIMEOUT_SECONDS, ErrorCode, RunStatus
from .investigation import Investigation
from .ports import IncidentStore
from .runtime import run
from .schemas import Incident, JsonObject, RunResult
from .storage import LocalIncidentStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "output"


def run_scenario(
    scenario: str = CORE01,
    *,
    output: Path | None = None,
    live: bool = False,
    max_turns: int = DEFAULT_MAX_TURNS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    store: IncidentStore | None = None,
    incident: Incident | None = None,
    model_reply: Callable[[JsonObject], JsonObject] | None = None,
    source_options: JsonObject | None = None,
) -> RunResult:
    from evals.model import FixtureModelServer

    case = SCENARIOS[scenario]
    if incident is not None and incident.proposal is not None:
        raise ValueError(ErrorCode.FINISHED.value)
    if live and model_reply is not None:
        raise ValueError(ErrorCode.INVALID_INPUT.value)
    sources = case.SourceFixture(**(source_options or {}))
    investigation = Investigation(incident or case.new_incident(), sources, store)
    if store is not None and incident is None:
        store.create(investigation.incident)
    system, descriptions, hashes = load_guidance(PROJECT_ROOT / "harness")
    initial = investigation.context()
    if live:
        result = asyncio.run(
            run(
                investigation,
                system,
                descriptions,
                max_turns=max_turns,
                timeout_seconds=timeout_seconds,
            )
        )
    else:
        with FixtureModelServer(model_reply or case.model_reply) as model:
            result = asyncio.run(
                run(
                    investigation,
                    system,
                    descriptions,
                    model_url=model.url,
                    max_turns=max_turns,
                    timeout_seconds=timeout_seconds,
                )
            )
            result.runtime["first_model_request"] = (
                model.requests[0] if model.requests else None
            )
            result.runtime["model_requests"] = len(model.requests)
    result.runtime["harness_hashes"] = hashes
    result.runtime["scenario"] = scenario
    result.runtime["process_id"] = os.getpid()
    result.runtime["source_requests"] = [asdict(request) for request in sources.calls]
    result.runtime["initial_evidence"] = list(initial["incident_card"]["evidence"])
    result.runtime["initial_revision"] = initial["incident_card"]["revision"]
    result.runtime["initial_catalogue"] = [
        entry["reference"] for entry in initial["incident_card"]["catalogue"].values()
    ]
    if output:
        write_artifacts(output, result, initial, system, descriptions)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS, default=CORE01)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--state", type=Path, help="Local Incident record")
    parser.add_argument("--resume", action="store_true", help="Load the saved Incident")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use local Claude login; sources remain synthetic",
    )
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    parser.add_argument(
        "--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS
    )
    args = parser.parse_args()
    if args.resume and args.state is None:
        parser.error("--resume requires --state")
    if args.state is not None and args.state.exists() and not args.resume:
        parser.error("Incident record already exists; use --resume")
    store = LocalIncidentStore(args.state) if args.state is not None else None
    incident = None
    if args.resume and store is not None:
        trusted = SCENARIOS[args.scenario].new_incident()
        incident = store.load(trusted.incident_id, trusted.scope)
    result = run_scenario(
        args.scenario,
        output=args.output or OUTPUT_ROOT / args.scenario.lower(),
        live=args.live,
        max_turns=args.max_turns,
        timeout_seconds=args.timeout_seconds,
        store=store,
        incident=incident,
    )
    print(trace_markdown(result))
    if result.status != RunStatus.PROPOSED:
        raise SystemExit(1)
