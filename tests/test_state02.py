"""Follow-up run transitions, historical evidence and persisted proposal history."""

import copy
import json
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from agent.collaboration import select_next_step
from agent.constants import ErrorCode, RunStatus, ToolName
from agent.investigation import Investigation
from agent.lifecycle import start_followup_run
from agent.storage import LocalIncidentStore
from evals import core01, core02
from evals.mp01 import HUMAN_ACTOR, HUMAN_STEP
from evals.state02 import NEW_ALERT, NEW_WINDOW, SOURCE_OPTIONS, assess, run_followup


class FollowupRunTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "incident.json"
        self.store = LocalIncidentStore(self.path)
        self.first = Investigation(
            core01.new_incident(), core01.SourceFixture(), self.store
        )
        self.store.create(self.first.incident)
        for tool, service in (
            (ToolName.CATALOGUE, core01.CHECKOUT),
            (ToolName.HEALTH, core01.CHECKOUT),
            (ToolName.TRACES, core01.CHECKOUT),
            (ToolName.CATALOGUE, core01.PAYMENTS),
            (ToolName.HEALTH, core01.PAYMENTS),
        ):
            self.first.apply(tool, {"service_id": service, "question": "Prepare R1"})
        self.original_arguments = core01.model_reply(self.request(self.first))[
            "arguments"
        ]
        self.first.apply(ToolName.PROPOSE, self.original_arguments)

    @staticmethod
    def request(agent):
        return {"messages": [{"content": json.dumps(agent.context())}]}

    def start(self, **overrides):
        current = self.store.load(
            self.first.incident.incident_id, self.first.incident.scope
        )
        args = dict(
            expected_revision=current.revision,
            alert=asdict(NEW_ALERT),
            observation_window=NEW_WINDOW,
        )
        args.update(overrides)
        return start_followup_run(
            self.store, current.incident_id, current.scope, **args
        )

    def test_transition_preserves_proposal_hypotheses_human_decision_and_findings(self):
        previous = copy.deepcopy(self.first.incident)
        human = select_next_step(
            self.store,
            previous.incident_id,
            previous.scope,
            expected_revision=previous.revision,
            responder_id=HUMAN_ACTOR,
            value=HUMAN_STEP,
        )
        current = self.start()
        self.assertEqual(current.run_number, 2)
        self.assertIsNone(current.proposal)
        self.assertEqual(current.hypotheses, [])
        self.assertEqual(current.selected_next_step, human.selected_next_step)
        self.assertEqual(current.alert, previous.alert)
        self.assertEqual(current.catalogue, previous.catalogue)
        self.assertEqual(current.completed_calls, previous.completed_calls)
        for ref, item in previous.evidence.items():
            self.assertEqual(current.evidence[ref], item)
        past = current.proposal_history[0]
        self.assertEqual(
            (past.run_number, past.window, past.proposal, past.hypotheses),
            (1, previous.observation_window, previous.proposal, previous.hypotheses),
        )
        self.assertEqual(current.evidence["A3"].data, {"error_rate_percent": 8.0})
        self.assertEqual(current.evidence["A4"].data, {"p95_latency_ms": 1800})
        self.assertEqual(
            asdict(self.store.load(current.incident_id, current.scope)), asdict(current)
        )
        self.assertEqual(
            Investigation(current, core01.SourceFixture()).status,
            RunStatus.INVESTIGATING,
        )

    def test_historical_telemetry_cannot_satisfy_current_readiness_or_citations(self):
        sources = core01.SourceFixture(**SOURCE_OPTIONS)
        agent = Investigation(self.start(), sources, self.store)
        for tool, service in (
            (ToolName.HEALTH, core01.CHECKOUT),
            (ToolName.TRACES, core01.CHECKOUT),
            (ToolName.HEALTH, core01.PAYMENTS),
        ):
            with self.assertRaisesRegex(ValueError, ErrorCode.INCOMPLETE_CONTEXT.value):
                agent.apply(ToolName.PROPOSE, self.original_arguments)
            agent.apply(tool, {"service_id": service, "question": "Refresh W2"})
        # Even with new data available, an old-only proposal must be rejected.
        with self.assertRaisesRegex(ValueError, ErrorCode.INCOMPLETE_CONTEXT.value):
            agent.apply(ToolName.PROPOSE, self.original_arguments)
        valid = core02.model_reply(self.request(agent))["arguments"]
        mixed = copy.deepcopy(valid)
        mixed["proposal"]["evidence_ids"] = ["E4", "E2", "E3"]
        with self.assertRaisesRegex(ValueError, ErrorCode.INCOMPLETE_CONTEXT.value):
            agent.apply(ToolName.PROPOSE, mixed)
        agent.apply(
            ToolName.HEALTH,
            {"service_id": core01.CHECKOUT, "question": "Repeat W2 query"},
        )
        self.assertTrue(agent.steps[-1].reused)
        self.assertEqual(len(sources.calls), 3)
        agent.apply(ToolName.PROPOSE, valid)
        self.assertEqual(agent.incident.proposal.evidence_ids, ["E4", "E5", "E6"])
        self.assertEqual(
            agent.incident.proposal_history[0].proposal, self.first.incident.proposal
        )

    def test_wrong_assignment_invalid_alert_and_non_advancing_window_do_not_commit(
        self,
    ):
        before = self.path.read_bytes()
        original = self.first.incident
        cases = (
            ("different-incident", original.scope, {}),
            (original.incident_id, replace(original.scope, tenant_id="other"), {}),
            (
                original.incident_id,
                original.scope,
                {"alert": dict(asdict(NEW_ALERT), service_id="other-service")},
            ),
            (
                original.incident_id,
                original.scope,
                {"alert": dict(asdict(NEW_ALERT), error_rate_percent=True)},
            ),
            (
                original.incident_id,
                original.scope,
                {"expected_revision": original.revision - 1},
            ),
            (
                original.incident_id,
                original.scope,
                {"observation_window": original.observation_window},
            ),
        )
        for incident_id, scope, changes in cases:
            with self.subTest(id=incident_id, changes=changes):
                args = dict(
                    expected_revision=original.revision,
                    alert=asdict(NEW_ALERT),
                    observation_window=NEW_WINDOW,
                )
                args.update(changes)
                with self.assertRaises(ValueError):
                    start_followup_run(self.store, incident_id, scope, **args)
                self.assertEqual(self.path.read_bytes(), before)
        active_store = LocalIncidentStore(self.path.parent / "active.json")
        active = Investigation(core01.new_incident(), core01.SourceFixture()).incident
        active_store.create(active)
        with self.assertRaisesRegex(ValueError, ErrorCode.RUN_NOT_FINISHED.value):
            start_followup_run(
                active_store,
                active.incident_id,
                active.scope,
                expected_revision=0,
                alert=asdict(NEW_ALERT),
                observation_window=NEW_WINDOW,
            )

    def test_corrupt_history_and_alert_observations_are_rejected_on_load(self):
        current = self.start()
        original = json.loads(self.path.read_text())
        for label in (
            "run_number",
            "past_reference",
            "alert_pair",
            "old_proposal_as_current",
        ):
            with self.subTest(case=label):
                body = copy.deepcopy(original)
                incident = body["incident"]
                if label == "run_number":
                    incident["run_number"] = True
                elif label == "past_reference":
                    incident["proposal_history"][0]["proposal"]["evidence_ids"] = [
                        "E999"
                    ]
                elif label == "alert_pair":
                    del incident["evidence"]["A4"]
                else:
                    incident["proposal"] = incident["proposal_history"][0]["proposal"]
                self.path.write_text(json.dumps(body))
                with self.assertRaisesRegex(ValueError, ErrorCode.INVALID_STATE.value):
                    self.store.load(current.incident_id, current.scope)


class FollowupSDKTests(unittest.TestCase):
    def test_state02_runs_both_bounded_runs_through_sdk_and_persists_history(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = run_followup(Path(directory))
            self.assertEqual(assess(first, second), [])
            self.assertEqual(
                (first.runtime["model_requests"], second.runtime["model_requests"]),
                (7, 5),
            )
            self.assertEqual(second.runtime["result"]["subtype"], "success")
            self.assertEqual(second.runtime["model_mode"], "fixture")
            trace = (Path(directory) / "trace.md").read_text()
            self.assertIn("Run R1", trace)
            self.assertIn("Run R2", trace)
            self.assertIn("E4, E5, E6", trace)
