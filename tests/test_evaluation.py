"""Hard boundaries remain distinct from illustrative judgment fixtures."""

import copy
import unittest
from dataclasses import asdict, replace

from agent.constants import ErrorCode
from evals.eval01 import Verdict, candidates, checkout_context, evaluate, hard_check


class EvaluationTests(unittest.TestCase):
    def test_valid_references_do_not_prove_the_conclusion(self):
        incident = checkout_context()
        before = copy.deepcopy(incident)
        results = [evaluate(incident, candidate) for candidate in candidates()]
        self.assertTrue(all(result.hard_error is None for result in results))
        self.assertEqual(
            [result.verdict for result in results],
            [Verdict.ACCEPTABLE, Verdict.ACCEPTABLE, Verdict.UNACCEPTABLE],
        )
        self.assertEqual(incident, before)
        self.assertIsNone(incident.proposal)

    def test_recorded_positive_review_cannot_override_hard_failures(self):
        incident = checkout_context()
        original = candidates()[0]
        for refs in (["C1"], ["invented"], ["E1", "E2"]):
            with self.subTest(references=refs):
                candidate = replace(
                    original, proposal=replace(original.proposal, evidence_ids=refs)
                )
                result = evaluate(incident, candidate)
                self.assertIsNotNone(result.hard_error)
                self.assertEqual(result.candidate.review_verdict, Verdict.ACCEPTABLE)
                self.assertEqual(result.verdict, Verdict.BLOCKED)

    def test_external_proposal_schema_is_validated_before_review(self):
        incident = checkout_context()
        value = asdict(candidates()[0].proposal)
        value["unexpected"] = "not accepted"
        self.assertEqual(hard_check(incident, value), ErrorCode.INVALID_INPUT.value)
        value.pop("unexpected")
        value["uncertainty"] = ""
        self.assertEqual(hard_check(incident, value), ErrorCode.INVALID_INPUT.value)
