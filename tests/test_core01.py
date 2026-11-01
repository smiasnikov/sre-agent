import copy
import unittest
from dataclasses import asdict

from agent.constants import ErrorCode, IncidentStatus, RunStatus, ToolName
from agent.investigation import Investigation
from evals.core01 import CHECKOUT, PAYMENTS, SourceFixture, new_incident


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.source = SourceFixture()
        self.agent = Investigation(new_incident(), self.source)

    def collect(self, tool, service):
        return self.agent.apply(
            tool, {"service_id": service, "question": "Check the incident"}
        )

    def observed(self):
        self.collect(ToolName.CATALOGUE, CHECKOUT)
        self.collect(ToolName.HEALTH, CHECKOUT)
        self.collect(ToolName.TRACES, CHECKOUT)
        self.collect(ToolName.CATALOGUE, PAYMENTS)
        self.collect(ToolName.HEALTH, PAYMENTS)

    def proposal(self, refs):
        return {
            "proposal": {
                "next_step": "Investigate Payments errors and changes",
                "reason": "Scoped observations support the lead",
                "evidence_ids": refs,
                "uncertainty": "Cause is unconfirmed; traces are a selected sample",
            }
        }

    def test_initial_context_has_only_alert_observations(self):
        self.assertEqual(set(self.agent.incident.evidence), {"A1", "A2"})
        self.assertEqual(self.agent.incident.catalogue, {})
        self.assertEqual(self.source.calls, [])

    def test_telemetry_requires_discovered_mapping(self):
        with self.assertRaisesRegex(ValueError, ErrorCode.UNKNOWN_MAPPING.value):
            self.collect(ToolName.HEALTH, CHECKOUT)
        self.assertEqual(self.source.calls, [])

    def test_model_cannot_override_tenant_or_select_unknown_service(self):
        with self.assertRaises(ValueError):
            self.agent.apply(
                ToolName.CATALOGUE,
                {"service_id": CHECKOUT, "question": "Check", "tenant_id": "other"},
            )
        with self.assertRaisesRegex(ValueError, ErrorCode.OUT_OF_SCOPE.value):
            self.collect(ToolName.CATALOGUE, "unrelated-service")
        self.assertEqual(self.source.calls, [])

    def test_wrong_tenant_response_does_not_become_evidence(self):
        base = self.source.call

        def wrong(request):
            result = base(request)
            result["scope"]["tenant_id"] = "other"
            return result

        self.source.call = wrong
        with self.assertRaisesRegex(ValueError, ErrorCode.OUT_OF_SCOPE.value):
            self.collect(ToolName.CATALOGUE, CHECKOUT)
        self.assertEqual(self.agent.incident.catalogue, {})

    def test_non_finite_or_boolean_health_is_rejected(self):
        self.collect(ToolName.CATALOGUE, CHECKOUT)
        base = self.source.call
        for value in (True, float("nan"), float("inf")):

            def malformed(request):
                result = base(request)
                result["data"]["error_rate_percent"] = value
                return result

            self.source.call = malformed
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.collect(ToolName.HEALTH, CHECKOUT)
        self.assertEqual(set(self.agent.incident.evidence), {"A1", "A2"})

    def test_catalogue_and_invented_references_are_rejected_without_mutation(self):
        self.observed()
        before = asdict(self.agent.incident)
        for refs in (["C1", "E1"], ["E999"], ["A1", "A2"]):
            with (
                self.subTest(refs=refs),
                self.assertRaisesRegex(ValueError, ErrorCode.INVALID_REFERENCES.value),
            ):
                self.agent.apply(ToolName.PROPOSE, self.proposal(refs))
            self.assertEqual(asdict(self.agent.incident), before)
        self.assertEqual(self.agent.status, RunStatus.INVESTIGATING)

    def test_proposal_ends_run_without_resolving_incident_or_calling_sources(self):
        self.observed()
        self.agent.apply(ToolName.PROPOSE, self.proposal(["E1", "E2", "E3"]))
        self.assertEqual(self.agent.status, RunStatus.PROPOSED)
        self.assertEqual(self.agent.incident.status, IncidentStatus.OPEN)
        with self.assertRaisesRegex(ValueError, ErrorCode.FINISHED.value):
            self.collect(ToolName.HEALTH, PAYMENTS)
        self.assertEqual(len(self.source.calls), 5)

    def test_returned_context_cannot_mutate_live_incident(self):
        response = self.collect(ToolName.CATALOGUE, CHECKOUT)
        response["incident_card"]["catalogue"][CHECKOUT]["owner"] = "Changed"
        self.assertEqual(self.agent.incident.catalogue[CHECKOUT].owner, "Checkout team")

    def test_invalid_hypothesis_does_not_partially_store_proposal(self):
        self.observed()
        value = self.proposal(["E1", "E2", "E3"])
        value["hypotheses"] = [{"statement": "Unknown", "evidence_ids": ["E999"]}]
        before = copy.deepcopy(self.agent.incident)
        with self.assertRaises(ValueError):
            self.agent.apply(ToolName.PROPOSE, value)
        self.assertEqual(self.agent.incident, before)

    def test_proposal_waits_for_implicated_dependency_health(self):
        self.collect(ToolName.CATALOGUE, CHECKOUT)
        self.collect(ToolName.HEALTH, CHECKOUT)
        self.collect(ToolName.TRACES, CHECKOUT)
        with self.assertRaisesRegex(ValueError, ErrorCode.INCOMPLETE_CONTEXT.value):
            self.agent.apply(ToolName.PROPOSE, self.proposal(["E1", "E2"]))
        self.assertIsNone(self.agent.incident.proposal)
        self.assertEqual(self.agent.status, RunStatus.INVESTIGATING)
