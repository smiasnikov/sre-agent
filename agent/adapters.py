"""Markdown guidance loading and review artifacts; no orchestration."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from .constants import ErrorCode, RunStatus, ToolName
from .schemas import JsonObject, RunResult


def load_guidance(directory: Path) -> tuple[str, dict[ToolName, str], JsonObject]:
    system = (directory / "agent.md").read_text()
    tools_text = (directory / "tools.md").read_text()
    descriptions = {}
    for section in tools_text.split("\n## ")[1:]:
        name, body = section.split("\n", 1)
        descriptions[ToolName(name.strip())] = body.strip()
    if (
        not system.strip()
        or set(descriptions) != set(ToolName)
        or not all(descriptions.values())
    ):
        raise ValueError(ErrorCode.INVALID_HARNESS.value)
    hashes = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in ("agent.md", "tools.md")
    }
    return system, descriptions, hashes


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _history_table(history: list[JsonObject]) -> list[str]:
    lines = [
        "",
        "## Previous proposals",
        "",
        "| Run | Observation window | Next step | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for past in history:
        window, proposal = past["window"], past["proposal"]
        lines.append(
            f"| R{past['run_number']} | {window['start']} → {window['end']} | "
            f"{_cell(proposal['next_step'])} | {', '.join(proposal['evidence_ids'])} |"
        )
    return lines


def trace_markdown(result: RunResult) -> str:
    incident = result.incident
    lines = [
        f"# {result.runtime.get('scenario', 'Checkout incident')} trace",
        "",
        f"- Model: {result.runtime['model_mode']}; sources: synthetic MCP data.",
        f"- Incident: {incident.incident_id}; tenant: {incident.scope.tenant_id}; {incident.scope.environment}; {incident.scope.region}.",
        f"- Agent run: R{incident.run_number}.",
        f"- Observation window: {incident.observation_window.start} → {incident.observation_window.end}.",
        f"- Incident revision: {result.runtime.get('initial_revision', 0)} → {incident.revision}.",
        "- Initial evidence: "
        + ", ".join(result.runtime.get("initial_evidence", ["A1", "A2"]))
        + "; catalogue: "
        + (", ".join(result.runtime.get("initial_catalogue", [])) or "empty")
        + ".",
        "",
    ]
    human_update = result.runtime.get("human_update")
    if human_update:
        selection = human_update["selection"]
        lines += [
            f"- Human update committed revision {human_update['revision']} before the agent's first proposal: {selection['next_step']}; owner {selection['owner']}.",
            "",
        ]
    lines += [
        "| Step | Tool | Service | Revision | Question | Card change / result |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for step in result.steps:
        change = (
            (step.added_reference + ": ") if step.added_reference else ""
        ) + step.outcome
        lines.append(
            "| {} | {} | {} | {} | {} | {} |".format(
                step.number,
                step.tool.value,
                step.service_id or "—",
                f"{step.base_revision} → {step.revision}"
                if step.accepted
                else f"expected {step.base_revision}; current {step.revision}",
                _cell(step.question),
                _cell(change),
            )
        )
    lines += [
        "",
        "## Outcome",
        "",
        f"- Run: {result.status.value}. Incident resolution is not asserted.",
    ]
    if result.status == RunStatus.PROPOSED and incident.proposal:
        p = incident.proposal
        lines += [
            f"- Next step: {p.next_step}",
            f"- Evidence: {', '.join(p.evidence_ids)}.",
            f"- Reason: {p.reason}",
            f"- Uncertainty: {p.uncertainty}",
        ]
    else:
        lines.append(f"- Stop reason: {result.stop_reason}")
    if incident.selected_next_step is not None:
        selected = incident.selected_next_step
        lines += [
            f"- Human-selected step: {selected.next_step}",
            f"- Owner: {selected.owner}; decision maker: {selected.decision_maker}; time: {selected.decided_at}.",
            f"- Human reason: {selected.reason}",
        ]
    if incident.proposal_history:
        lines += _history_table([asdict(past) for past in incident.proposal_history])
    return "\n".join(lines) + "\n"


def write_artifacts(
    directory: Path,
    result: RunResult,
    initial_context: JsonObject,
    system: str,
    descriptions: dict[ToolName, str],
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "trace.md").write_text(trace_markdown(result))
    (directory / "trace.json").write_text(json.dumps(asdict(result), indent=2) + "\n")
    context = initial_context["incident_card"]
    lines = [
        "# Initial model input",
        "",
        "## Supplied context",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ]
    fields = {
        "Incident": context["incident_id"],
        "Revision": context["revision"],
        "Agent run": "R" + str(context["run_number"]),
        "Tenant": context["scope"]["tenant_id"],
        "Environment": context["scope"]["environment"],
        "Region": context["scope"]["region"],
        "Service": context["alert"]["service_id"],
        "Original alert errors": str(context["alert"]["error_rate_percent"]) + "%",
        "Original alert p95": str(context["alert"]["p95_latency_ms"]) + " ms",
        "Observation window": context["observation_window"]["start"]
        + " → "
        + context["observation_window"]["end"],
    }
    for key, value in fields.items():
        lines.append(f"| {key} | {_cell(value)} |")
    lines += [
        "",
        "Initial evidence: "
        + ", ".join(context["evidence"])
        + ". Catalogue: "
        + (
            ", ".join(entry["reference"] for entry in context["catalogue"].values())
            or "empty"
        )
        + ".",
    ]
    if context["proposal_history"]:
        lines += _history_table(context["proposal_history"])
        lines += [
            "",
            "## Supplied observations",
            "",
            "| Reference | Kind | Window | Summary |",
            "| --- | --- | --- | --- |",
        ]
        for evidence in context["evidence"].values():
            window = evidence["window"]
            lines.append(
                f"| {evidence['reference']} | {evidence['kind']} | {window['start']} → {window['end']} | {_cell(evidence['summary'])} |"
            )
    lines += ["", "## System guidance", "", system]
    for name, description in descriptions.items():
        lines += ["", f"## Tool: {name.value}", "", description]
    (directory / "model-input.md").write_text("\n".join(lines))
