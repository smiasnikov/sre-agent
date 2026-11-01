"""Fixture isolation checks; mixed-signal interpretation is scripted."""

import unittest

from agent.constants import ToolName
from agent.investigation import Investigation
from evals import CORE01, CORE02, SCENARIOS
from evals.core01 import CHECKOUT, PAYMENTS


class ScenarioDataTests(unittest.TestCase):
    def test_scenario_health_is_isolated_and_initial_context_is_unchanged(self):
        for name, expected in ((CORE02, 0.2), (CORE01, 9.0), (CORE02, 0.2)):
            with self.subTest(scenario=name):
                case = SCENARIOS[name]
                source = case.SourceFixture()
                agent = Investigation(case.new_incident(), source)
                self.assertEqual(set(agent.incident.evidence), {"A1", "A2"})
                self.assertEqual(agent.incident.catalogue, {})
                self.assertEqual(source.calls, [])
                for tool, service in (
                    (ToolName.CATALOGUE, CHECKOUT),
                    (ToolName.CATALOGUE, PAYMENTS),
                    (ToolName.HEALTH, PAYMENTS),
                ):
                    agent.apply(
                        tool, {"service_id": service, "question": "Check health"}
                    )
                self.assertEqual(
                    agent.incident.evidence["E1"].data["error_rate_percent"], expected
                )
