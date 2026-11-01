import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.adapters import load_guidance
from agent.cli import PROJECT_ROOT, run_scenario
from agent.constants import ErrorCode, MCP_PREFIX, RunStatus, ToolName
from agent.investigation import Investigation
from agent.runtime import run
from evals.core01 import SourceFixture, assess, new_incident
from evals import CORE02, core02


class SDKIntegrationTests(unittest.TestCase):
    def test_core01_runs_through_native_mcp_and_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_scenario(output=output)
            self.assertEqual(assess(result), [])
            self.assertEqual(result.runtime["result"]["subtype"], "success")
            self.assertEqual(result.runtime["model_requests"], 7)
            self.assertEqual(len(result.steps), 6)
            self.assertIn("payments-api", (output / "trace.md").read_text())
            self.assertIn("E3", (output / "trace.md").read_text())
            first = result.runtime["first_model_request"]
            system, descriptions, _ = load_guidance(PROJECT_ROOT / "harness")
            self.assertIn(system, "\n".join(block["text"] for block in first["system"]))
            advertised = {tool["name"]: tool for tool in first["tools"]}
            self.assertEqual(
                set(advertised), {MCP_PREFIX + name.value for name in ToolName}
            )
            for name, description in descriptions.items():
                self.assertIn(
                    description, advertised[MCP_PREFIX + name.value]["description"]
                )
            props = advertised[MCP_PREFIX + ToolName.HEALTH.value]["input_schema"][
                "properties"
            ]
            self.assertEqual(set(props), {"service_id", "question"})
            self.assertEqual(result.runtime["tool_errors"], [])
            self.assertTrue((output / "model-input.md").exists())
            json.dumps(result.runtime)

    def test_core02_preserves_mixed_evidence_and_scripted_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_scenario(CORE02, output=output)
            self.assertEqual(core02.assess(result), [])
            self.assertEqual(result.runtime["result"]["subtype"], "success")
            self.assertEqual(result.runtime["tool_errors"], [])
            self.assertEqual(result.runtime["model_mode"], "fixture")
            trace = (output / "trace.md").read_text()
            self.assertTrue(trace.startswith("# CORE-02 trace"))
            self.assertIn(core02.NORMAL_SUMMARY, trace)
            self.assertIn(core02.NEXT_STEP, trace)
            self.assertEqual(result.steps[-1].tool, ToolName.PROPOSE)
            # A stale CORE-01 conclusion must fail the scripted-output check,
            # even though the application accepts structurally valid text.
            from dataclasses import replace

            stale = copy.deepcopy(result)
            stale.incident.proposal = replace(
                stale.incident.proposal, reason="Payments health is degraded"
            )
            self.assertIn("scripted_proposal_preserved", core02.assess(stale))
            missing_citation = copy.deepcopy(result)
            missing_citation.incident.proposal.evidence_ids.remove("E3")
            self.assertIn("payment_lead_cited", core02.assess(missing_citation))

    def test_sdk_turn_limit_preserves_partial_findings(self):
        result = run_scenario(max_turns=2)
        self.assertEqual(result.status, RunStatus.BLOCKED)
        self.assertEqual(result.stop_reason, ErrorCode.TURN_LIMIT.value)
        self.assertIn("E1", result.incident.evidence)
        self.assertNotIn("E3", result.incident.evidence)
        self.assertIsNone(result.incident.proposal)

    def test_acceptance_does_not_depend_on_health_trace_order(self):
        investigation = Investigation(new_incident(), SourceFixture())
        for tool, service in (
            (ToolName.CATALOGUE, "checkout-api"),
            (ToolName.TRACES, "checkout-api"),
            (ToolName.HEALTH, "checkout-api"),
            (ToolName.CATALOGUE, "payments-api"),
            (ToolName.HEALTH, "payments-api"),
        ):
            investigation.apply(
                tool, {"service_id": service, "question": "Check incident"}
            )
        investigation.apply(
            ToolName.PROPOSE,
            {
                "proposal": {
                    "next_step": "Inspect Payments errors",
                    "reason": "Observed timeout path and degraded health",
                    "evidence_ids": ["E1", "E2", "E3"],
                    "uncertainty": "Cause remains unknown",
                }
            },
        )
        from agent.schemas import RunResult

        result = RunResult(
            investigation.incident, investigation.steps, {}, investigation.status
        )
        self.assertEqual(assess(result), [])


class RuntimeFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_sdk_failure_preserves_alert(self):
        class FailedClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                raise ConnectionError()

            async def __aexit__(self, *args):
                pass

        investigation = Investigation(new_incident(), SourceFixture())
        system, descriptions, _ = load_guidance(PROJECT_ROOT / "harness")
        with patch("agent.runtime.ClaudeSDKClient", FailedClient):
            result = await run(
                investigation, system, descriptions, model_url="http://127.0.0.1:1"
            )
        self.assertEqual(result.stop_reason, ErrorCode.SDK_FAILURE.value)
        self.assertEqual(set(result.incident.evidence), {"A1", "A2"})

    async def test_timeout_ends_current_run(self):
        class StalledClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def query(self, prompt):
                await asyncio.Event().wait()

        investigation = Investigation(new_incident(), SourceFixture())
        system, descriptions, _ = load_guidance(PROJECT_ROOT / "harness")
        with patch("agent.runtime.ClaudeSDKClient", StalledClient):
            result = await run(
                investigation,
                system,
                descriptions,
                model_url="http://127.0.0.1:1",
                timeout_seconds=0.01,
            )
        self.assertEqual(result.stop_reason, ErrorCode.TIMEOUT.value)
        self.assertIsNone(result.incident.proposal)
