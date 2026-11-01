"""Local recovery, external-data validation and committed-call replay checks."""

import copy
import json
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from agent.constants import ErrorCode, ToolName
from agent.investigation import Investigation
from agent.schemas import Window
from agent.storage import LocalIncidentStore
from evals.core01 import CHECKOUT, SourceFixture, new_incident
from evals.state01 import run_restart


class IncidentRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "incident.json"
        self.store = LocalIncidentStore(self.path)
        self.source = SourceFixture()
        self.agent = Investigation(new_incident(), self.source, self.store)
        self.store.create(self.agent.incident)
        self.collect(ToolName.CATALOGUE)
        self.collect(ToolName.HEALTH)

    def collect(self, tool):
        return self.agent.apply(
            tool, {"service_id": CHECKOUT, "question": "Check incident"}
        )

    def load(self):
        trusted = new_incident()
        return self.store.load(trusted.incident_id, trusted.scope)

    def test_loaded_calls_reuse_findings_even_with_different_question(self):
        loaded = self.load()
        self.assertEqual(asdict(loaded), asdict(self.agent.incident))
        fresh_source = SourceFixture()
        fresh = Investigation(loaded, fresh_source, LocalIncidentStore(self.path))
        before = asdict(fresh.incident)
        for tool in (ToolName.CATALOGUE, ToolName.HEALTH):
            fresh.apply(tool, {"service_id": CHECKOUT, "question": "Different wording"})
        self.assertEqual(fresh_source.calls, [])
        self.assertEqual(asdict(fresh.incident), before)
        self.assertEqual([step.added_reference for step in fresh.steps], ["C1", "E1"])
        self.assertTrue(all(step.reused for step in fresh.steps))

    def test_scope_and_incident_identity_are_checked_against_caller(self):
        trusted = new_incident()
        for incident_id, scope in (
            ("different-incident", trusted.scope),
            (trusted.incident_id, replace(trusted.scope, tenant_id="other-tenant")),
        ):
            with (
                self.subTest(incident_id=incident_id, scope=scope),
                self.assertRaisesRegex(ValueError, ErrorCode.OUT_OF_SCOPE.value),
            ):
                self.store.load(incident_id, scope)

    def test_corrupt_records_are_rejected_before_recovery(self):
        original = json.loads(self.path.read_text())

        def version(body):
            body["format_version"] = True

        def missing_call(body):
            body["incident"]["completed_calls"].pop()

        def duplicate_call(body):
            body["incident"]["completed_calls"].append(
                copy.deepcopy(body["incident"]["completed_calls"][0])
            )

        def invalid_ref(body):
            body["incident"]["completed_calls"][1]["finding_ref"] = "E999"

        def invalid_health(body):
            body["incident"]["evidence"]["E1"]["data"]["error_rate_percent"] = True

        def unknown_field(body):
            body["incident"]["unexpected_field"] = 5

        def old_format(body):
            body["format_version"] = 1

        def invalid_revision(body):
            body["incident"]["revision"] = True

        for mutate in (
            version,
            missing_call,
            duplicate_call,
            invalid_ref,
            invalid_health,
            unknown_field,
            old_format,
            invalid_revision,
        ):
            with self.subTest(case=mutate.__name__):
                body = copy.deepcopy(original)
                mutate(body)
                self.path.write_text(json.dumps(body))
                with self.assertRaisesRegex(ValueError, ErrorCode.INVALID_STATE.value):
                    self.load()

    def test_failed_atomic_replace_keeps_saved_and_live_state_unchanged(self):
        before_file = self.path.read_bytes()
        before_card = asdict(self.agent.incident)
        before_steps = list(self.agent.steps)
        with patch("agent.storage.os.replace", side_effect=OSError("write failed")):
            with self.assertRaisesRegex(ValueError, ErrorCode.STORAGE_FAILURE.value):
                self.collect(ToolName.TRACES)
        self.assertEqual(self.path.read_bytes(), before_file)
        self.assertEqual(asdict(self.agent.incident), before_card)
        self.assertEqual(self.agent.steps, before_steps)
        self.assertEqual(asdict(self.load()), before_card)
        self.assertEqual(
            {path.resolve() for path in self.path.parent.iterdir()},
            {self.store.path, self.store.lock_path},
        )
        # The unsaved read can repeat; it was never marked completed.
        self.collect(ToolName.TRACES)
        self.assertEqual(len(self.source.calls), 4)
        self.assertIn("E2", self.load().evidence)

    def test_new_observation_window_is_not_a_completed_request(self):
        fresh_source = SourceFixture()
        base = fresh_source.call

        def shifted(request):
            original_window = new_incident().observation_window
            result = base(replace(request, window=original_window))
            result["window"] = asdict(request.window)
            return result

        fresh_source.call = shifted
        self.agent = Investigation(self.load(), fresh_source, self.store)
        self.agent.incident.observation_window = Window(
            "2026-10-31T10:02:00Z", "2026-10-31T10:07:00Z"
        )
        self.collect(ToolName.HEALTH)
        self.assertEqual(len(fresh_source.calls), 1)
        self.assertFalse(self.agent.steps[-1].reused)
        self.assertIn("E1", self.load().evidence)
        self.assertIn("E2", self.load().evidence)


class FreshProcessRecoveryTests(unittest.TestCase):
    def test_state01_resumes_in_a_different_process_without_history(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(run_restart(Path(directory)), [])
