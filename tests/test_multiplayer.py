"""Atomic revision conflicts and preservation of human operational direction."""

import copy
import json
import multiprocessing
import fcntl
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from agent.collaboration import select_next_step
from agent.constants import ErrorCode, RunStatus, ToolName
from agent.investigation import Investigation
from agent.ports import RevisionConflict
from agent.storage import LocalIncidentStore
from agent.validation import selected_step
from evals import core01
from evals.mp01 import HUMAN_ACTOR, HUMAN_STEP, REVISED_STEP, assess, run_multiplayer
from evals.model import FixtureModelServer


def competing_writer(path, barrier, results, label):
    """Both processes read the same revision before either may commit."""
    store = LocalIncidentStore(Path(path))
    trusted = core01.new_incident()
    incident = store.load(trusted.incident_id, trusted.scope)
    expected = incident.revision
    incident.selected_next_step = selected_step(
        dict(
            HUMAN_STEP,
            owner=label,
            decision_maker=label,
            decided_at="2026-10-31T10:07:00Z",
        )
    )
    barrier.wait(timeout=10)
    try:
        store.save(incident, expected)
        results.put((label, True, incident.revision))
    except RevisionConflict as conflict:
        results.put((label, False, conflict.current.revision))


def hold_lock(path, ready, release):
    """Hold the real file lock until the parent explicitly releases this writer."""
    with Path(path).open("a") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        ready.set()
        try:
            if not release.wait(timeout=10):
                raise TimeoutError("Lock holder was not released by the test")
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class MultiplayerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "incident.json"
        self.store = LocalIncidentStore(self.path)
        self.agent = Investigation(
            core01.new_incident(), core01.SourceFixture(), self.store
        )
        self.store.create(self.agent.incident)
        for tool, service in (
            (ToolName.CATALOGUE, core01.CHECKOUT),
            (ToolName.HEALTH, core01.CHECKOUT),
            (ToolName.TRACES, core01.CHECKOUT),
            (ToolName.CATALOGUE, core01.PAYMENTS),
            (ToolName.HEALTH, core01.PAYMENTS),
        ):
            self.agent.apply(
                tool, {"service_id": service, "question": "Prepare findings"}
            )

    def human_update(self, value=HUMAN_STEP):
        return select_next_step(
            self.store,
            self.agent.incident.incident_id,
            self.agent.incident.scope,
            expected_revision=5,
            responder_id=HUMAN_ACTOR,
            value=value,
        )

    def test_stale_proposal_reloads_human_decision_before_reassessment(self):
        original = asdict(self.agent.incident)
        human = self.human_update()
        arguments = core01.model_reply(
            {"messages": [{"content": json.dumps(self.agent.context())}]}
        )["arguments"]
        with self.assertRaises(RevisionConflict) as captured:
            self.agent.apply(ToolName.PROPOSE, arguments)
        self.assertEqual(captured.exception.expected_revision, 5)
        self.assertEqual(captured.exception.current.revision, 6)
        self.assertEqual(self.agent.status, RunStatus.INVESTIGATING)
        self.assertIsNone(self.agent.incident.proposal)
        self.assertFalse(self.agent.steps[-1].accepted)
        self.assertEqual(
            self.agent.incident.selected_next_step, human.selected_next_step
        )
        for key in ("evidence", "catalogue", "completed_calls"):
            self.assertEqual(asdict(self.agent.incident)[key], original[key])
        arguments["proposal"]["next_step"] = REVISED_STEP
        self.agent.apply(ToolName.PROPOSE, arguments)
        saved = self.store.load(human.incident_id, human.scope)
        self.assertEqual(saved.revision, 7)
        self.assertEqual(saved.selected_next_step, human.selected_next_step)
        self.assertEqual(saved.proposal.next_step, REVISED_STEP)
        self.assertEqual(self.agent.status, RunStatus.PROPOSED)

    def test_model_cannot_replace_human_selection_or_forge_revision(self):
        human = self.human_update()
        self.agent = Investigation(human, core01.SourceFixture(), self.store)
        arguments = core01.model_reply(
            {"messages": [{"content": json.dumps(self.agent.context())}]}
        )["arguments"]
        for key, value in (("selected_next_step", None), ("revision", 5)):
            with self.subTest(field=key), self.assertRaises(ValueError):
                self.agent.apply(ToolName.PROPOSE, dict(arguments, **{key: value}))
        saved = self.store.load(human.incident_id, human.scope)
        self.assertEqual(saved.revision, 6)
        self.assertEqual(saved.selected_next_step, human.selected_next_step)

    def test_human_update_validates_references_and_protects_attribution(self):
        for invalid in (
            dict(HUMAN_STEP, evidence_ids=["C1"]),
            dict(HUMAN_STEP, decision_maker="forged"),
        ):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                self.human_update(invalid)
        self.assertEqual(
            self.store.load(
                self.agent.incident.incident_id, self.agent.incident.scope
            ).revision,
            5,
        )
        with self.assertRaisesRegex(ValueError, ErrorCode.INCIDENT_EXISTS.value):
            self.store.create(core01.new_incident())

    def test_atomic_compare_and_write_allows_only_one_process_to_commit(self):
        context = multiprocessing.get_context("spawn")
        barrier, results = context.Barrier(2), context.Queue()
        workers = [
            context.Process(
                target=competing_writer, args=(str(self.path), barrier, results, label)
            )
            for label in ("first", "second")
        ]
        try:
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=15)
                self.assertEqual(worker.exitcode, 0)
            outcomes = [results.get(timeout=2), results.get(timeout=2)]
            self.assertEqual(sorted(item[1] for item in outcomes), [False, True])
            self.assertEqual([item[2] for item in outcomes], [6, 6])
            current = self.store.load(
                self.agent.incident.incident_id, self.agent.incident.scope
            )
            self.assertEqual(current.revision, 6)
            self.assertEqual(current.evidence, self.agent.incident.evidence)
            winner = next(item[0] for item in outcomes if item[1])
            self.assertEqual(current.selected_next_step.owner, winner)
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                worker.join(timeout=2)
            results.close()
            results.join_thread()

    def test_held_lock_times_out_without_changing_incident_then_retry_succeeds(self):
        human = self.human_update()
        bounded_store = LocalIncidentStore(self.path, lock_timeout_seconds=0.03)
        agent = Investigation(human, core01.SourceFixture(), bounded_store)
        arguments = core01.model_reply(
            {"messages": [{"content": json.dumps(agent.context())}]}
        )["arguments"]
        before_file = self.path.read_bytes()
        before_card = asdict(agent.incident)
        context = multiprocessing.get_context("spawn")
        ready, release = context.Event(), context.Event()
        holder = context.Process(
            target=hold_lock, args=(str(self.store.lock_path), ready, release)
        )
        holder.start()
        try:
            self.assertTrue(ready.wait(timeout=5), "Other writer did not acquire lock")
            now = [0.0]

            def advance(seconds):
                now[0] += seconds

            with (
                patch("agent.storage.time.monotonic", side_effect=lambda: now[0]),
                patch("agent.storage.time.sleep", side_effect=advance),
            ):
                with self.assertRaisesRegex(ValueError, ErrorCode.LOCK_TIMEOUT.value):
                    agent.apply(ToolName.PROPOSE, arguments)
            self.assertAlmostEqual(now[0], 0.03)
            self.assertTrue(holder.is_alive())
            self.assertFalse(release.is_set())
            self.assertEqual(self.path.read_bytes(), before_file)
            self.assertEqual(asdict(agent.incident), before_card)
            self.assertEqual(agent.status, RunStatus.INVESTIGATING)
            self.assertEqual(agent.steps, [])
            self.assertIsNone(agent.incident.proposal)
            self.assertEqual(agent.incident.revision, 6)
        finally:
            release.set()
            holder.join(timeout=5)
            if holder.is_alive():
                holder.terminate()
                holder.join(timeout=2)
        self.assertEqual(holder.exitcode, 0)
        agent.apply(ToolName.PROPOSE, arguments)
        saved = bounded_store.load(human.incident_id, human.scope)
        self.assertEqual(saved.revision, 7)
        self.assertEqual(saved.selected_next_step, human.selected_next_step)
        self.assertEqual(agent.status, RunStatus.PROPOSED)

    def test_invalid_lock_wait_settings_are_rejected(self):
        for value in (0, -1, float("nan"), float("inf"), True, "invalid"):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, ErrorCode.INVALID_INPUT.value),
            ):
                LocalIncidentStore(self.path, lock_timeout_seconds=value)


class MultiplayerSDKTests(unittest.TestCase):
    def test_fixture_reads_card_when_sdk_appends_tool_result_annotations(self):
        card = {"revision": 6, "selected_next_step": HUMAN_STEP}
        content = (
            json.dumps({"incident_card": card})
            + "\n\n<system-reminder>SDK metadata</system-reminder>"
        )
        request = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "content": content}],
                }
            ]
        }
        self.assertEqual(FixtureModelServer.cards(request), [card])

    def test_mp01_reassesses_through_sdk_after_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_multiplayer(Path(directory))
            self.assertEqual(assess(result), [])
            self.assertEqual(result.runtime["result"]["subtype"], "success")
            self.assertEqual(result.runtime["model_mode"], "fixture")
            self.assertEqual(result.runtime["model_requests"], 3)
            trace = (Path(directory) / "trace.md").read_text()
            self.assertIn("Rejected stale update", trace)
            self.assertIn(HUMAN_STEP["next_step"], trace)
            self.assertIn(REVISED_STEP, trace)
            altered = copy.deepcopy(result)
            altered.incident.selected_next_step = None
            self.assertIn("human_selection_preserved", assess(altered))
