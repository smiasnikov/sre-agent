"""Claude SDK adapter: native MCP tools, SDK turn cap, and timeout per run."""

import asyncio
import copy
import json
import math
import shutil
import tempfile
from typing import Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)

from .constants import (
    ANTHROPIC_API_URL,
    DEFAULT_MAX_TURNS,
    DEFAULT_TIMEOUT_SECONDS,
    ErrorCode,
    FIXTURE_API_KEY,
    FIXTURE_MODEL,
    MCP_PREFIX,
    MCP_SERVER,
    RunStatus,
    SOURCE_TOOLS,
    ToolName,
)
from .investigation import Investigation
from .schemas import JsonObject, RunResult
from .ports import RevisionConflict


async def run(
    investigation: Investigation,
    system: str,
    descriptions: dict[ToolName, str],
    *,
    model_url: str | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    emit: Callable[[str], None] = print,
) -> RunResult:
    if (
        not math.isfinite(timeout_seconds)
        or type(max_turns) is not int
        or max_turns < 1
        or timeout_seconds <= 0
    ):
        raise ValueError(ErrorCode.INVALID_INPUT.value)
    if model_url is not None and not model_url.startswith("http://127.0.0.1:"):
        raise ValueError(ErrorCode.INVALID_INPUT.value)
    runtime: JsonObject = {
        "model_mode": "fixture" if model_url else "live",
        "tool_errors": [],
        "max_turns": max_turns,
        "timeout_seconds": timeout_seconds,
    }

    def register(name: ToolName):
        properties: JsonObject
        if name in SOURCE_TOOLS:
            properties = {
                "service_id": {"type": "string"},
                "question": {"type": "string"},
            }
            required = list(properties)
        elif name == ToolName.PROPOSE:
            proposal_fields: JsonObject = {
                key: {"type": "string"}
                for key in ("next_step", "reason", "uncertainty")
            }
            proposal_fields["evidence_ids"] = {
                "type": "array",
                "items": {"type": "string"},
            }
            properties = {
                "proposal": {
                    "type": "object",
                    "properties": proposal_fields,
                    "required": list(proposal_fields),
                    "additionalProperties": False,
                },
                "hypotheses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "statement": {"type": "string"},
                            "evidence_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["statement", "evidence_ids"],
                        "additionalProperties": False,
                    },
                },
            }
            required = ["proposal"]
        else:
            properties, required = {"reason": {"type": "string"}}, ["reason"]

        @tool(
            name.value,
            descriptions[name],
            {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        )
        async def handler(arguments):
            try:
                response = investigation.apply(name, arguments)
                failed = False
            except Exception as error:
                code = (
                    str(error)
                    if isinstance(error, ValueError)
                    else ErrorCode.TOOL_FAILURE.value
                )
                runtime["tool_errors"].append({"tool": name.value, "error": code})
                response, failed = dict(investigation.context(), error=code), True
                if isinstance(error, RevisionConflict):
                    response.update(
                        expected_revision=error.expected_revision,
                        current_revision=error.current.revision,
                    )
            return {
                "content": [{"type": "text", "text": json.dumps(response)}],
                "is_error": failed,
            }

        return handler

    registered = [register(name) for name in ToolName]
    with tempfile.TemporaryDirectory(prefix="checkout-core-") as isolated:
        environment = {
            "ANTHROPIC_BASE_URL": model_url or ANTHROPIC_API_URL,
            "ANTHROPIC_API_KEY": FIXTURE_API_KEY if model_url else "",
            "ANTHROPIC_AUTH_TOKEN": "",
            "CLAUDE_CODE_OAUTH_TOKEN": "",
            "CLAUDE_CODE_USE_BEDROCK": "0",
            "CLAUDE_CODE_USE_VERTEX": "0",
            "CLAUDE_CODE_USE_FOUNDRY": "0",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1",
        }
        if model_url:
            environment["CLAUDE_CONFIG_DIR"] = isolated
        options = ClaudeAgentOptions(
            tools=[],
            allowed_tools=[MCP_PREFIX + item.name for item in registered],
            permission_mode="dontAsk",
            strict_mcp_config=True,
            setting_sources=[],
            skills=[],
            cwd=isolated,
            mcp_servers={
                MCP_SERVER: create_sdk_mcp_server(MCP_SERVER, tools=registered)
            },
            system_prompt=system,
            model=FIXTURE_MODEL if model_url else None,
            cli_path=shutil.which("claude") if model_url is None else None,
            max_turns=max_turns,
            env=environment,
        )

        async def consume():
            async with ClaudeSDKClient(options=options) as client:
                await client.query(json.dumps(investigation.context()))
                async for message in client.receive_response():
                    if isinstance(message, SystemMessage) and message.subtype == "init":
                        runtime["model"] = message.data.get("model")
                        runtime["tools"] = message.data.get("tools")
                    elif isinstance(message, AssistantMessage) and model_url is None:
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                emit(block.text)
                    elif isinstance(message, ResultMessage):
                        runtime["result"] = {
                            "subtype": message.subtype,
                            "is_error": message.is_error,
                            "sdk_turns": message.num_turns,
                        }
                        if (
                            message.is_error
                            and investigation.status == RunStatus.INVESTIGATING
                        ):
                            investigation.status = RunStatus.BLOCKED
                            investigation.stop_reason = (
                                ErrorCode.TURN_LIMIT.value
                                if message.subtype == "error_max_turns"
                                else ErrorCode.SDK_FAILURE.value
                            )

        try:
            await asyncio.wait_for(consume(), timeout=timeout_seconds)
        except Exception as error:
            runtime["error"] = type(error).__name__
            if investigation.status == RunStatus.INVESTIGATING:
                investigation.status = RunStatus.BLOCKED
                investigation.stop_reason = (
                    ErrorCode.TIMEOUT.value
                    if isinstance(error, asyncio.TimeoutError)
                    else ErrorCode.SDK_FAILURE.value
                )
    if investigation.status == RunStatus.INVESTIGATING:
        investigation.status = RunStatus.BLOCKED
        investigation.stop_reason = ErrorCode.NO_PROPOSAL.value
    return RunResult(
        copy.deepcopy(investigation.incident),
        copy.deepcopy(investigation.steps),
        runtime,
        investigation.status,
        investigation.stop_reason,
    )
