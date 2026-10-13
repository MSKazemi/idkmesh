"""C13-E regression suite: run labels are deterministic, bounded and powerless."""

from dataclasses import FrozenInstanceError
import json
import unittest

from idkmesh.github_run_label_projection import (
    MANAGED_RUN_LABEL_PREFIXES,
    _RUN_LABEL_STATES,
    plan_github_run_labels,
)
from idkmesh.product_spine import RUN_STATES


DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64


def _plan(state="proposed", labels=(), **overrides):
    params = {
        "run_id": "run/example-123",
        "run_state": state,
        "canonical_source_digest": DIGEST,
        "existing_labels": labels,
    }
    params.update(overrides)
    return plan_github_run_labels(**params)


class GitHubRunLabelProjectionTests(unittest.TestCase):
    def test_all_run_states_are_covered_explicitly(self):
        self.assertEqual(set(_RUN_LABEL_STATES), RUN_STATES)
        for state in sorted(RUN_STATES):
            with self.subTest(state=state):
                plan = _plan(state)
                self.assertEqual(len(plan.managed_labels), 3)
                self.assertEqual(len(set(plan.managed_labels)), 3)
                for label, prefix in zip(plan.managed_labels, MANAGED_RUN_LABEL_PREFIXES):
                    self.assertTrue(label.startswith(prefix))
                    self.assertLessEqual(len(label), 50)
                self.assertEqual(len(plan.add_labels), 3)
                self.assertFalse(plan.to_dict()["merge_authority"])
                self.assertFalse(plan.to_dict()["github_mutation_performed"])

    def test_state_labels_do_not_invent_acceptance(self):
        cases = {
            "proposed": ("proposal", "not-started", "unrecorded"),
            "admitted": ("dispatch-admitted", "not-started", "unrecorded"),
            "dispatched": ("dispatched", "not-started", "unrecorded"),
            "candidate_observed": ("candidate-observed", "not-started", "unrecorded"),
            "verification_requested": ("verification-pending", "pending", "unrecorded"),
            "verification_error": ("verification-error", "error", "unrecorded"),
            "evidence_ready": ("evidence-ready", "evidence-ready", "unrecorded"),
            "awaiting_human_decision": ("human-decision-pending", "evidence-ready", "pending"),
            "decided": ("human-decision-recorded", "evidence-ready", "recorded"),
            "cancelled": ("cancelled", "unknown", "unknown"),
        }
        for state, values in cases.items():
            with self.subTest(state=state):
                plan = _plan(state)
                self.assertEqual(plan.managed_labels, tuple(
                    prefix + value for prefix, value in zip(MANAGED_RUN_LABEL_PREFIXES, values)
                ))
                self.assertFalse(any(
                    "approved" in label or "accepted" in label or "merged" in label
                    for label in plan.managed_labels
                ))

    def test_untrusted_approval_label_is_replaced_not_interpreted(self):
        labels = (
            "idkmesh:work:approved",
            "IDKMESH:human:merged",
            "idkmesh:verify:verified",
            "idkmesh:route:blocked",
            "agent-ready",
        )
        plan = _plan("proposed", labels)
        self.assertEqual(len(plan.remove_labels), 3)
        self.assertIn("idkmesh:route:blocked", plan.target_labels)
        self.assertIn("agent-ready", plan.target_labels)
        self.assertIn("idkmesh:work:proposal", plan.target_labels)
        self.assertNotIn("idkmesh:work:approved", plan.target_labels)
        self.assertFalse(plan.to_dict()["dispatch_authority"])

    def test_noop_after_projection_and_case_insensitive_observation(self):
        first = _plan("candidate_observed", ("bug", "idkmesh:route:blocked"))
        second = _plan("candidate_observed", first.target_labels)
        self.assertTrue(second.noop)
        self.assertEqual(second.add_labels, ())
        self.assertEqual(second.remove_labels, ())
        self.assertEqual(second.target_labels, first.target_labels)
        mixed = _plan("candidate_observed", tuple(
            item.upper() if item.startswith("idkmesh:work:") else item
            for item in first.target_labels
        ))
        self.assertTrue(mixed.noop)

    def test_state_transition_removes_only_old_owned_labels(self):
        before = _plan("admitted", ("bug", "idkmesh:risk:high"))
        after = _plan("dispatched", before.target_labels)
        self.assertEqual(after.remove_labels, ("idkmesh:work:dispatch-admitted",))
        self.assertEqual(after.add_labels, ("idkmesh:work:dispatched",))
        self.assertIn("idkmesh:risk:high", after.target_labels)
        self.assertIn("bug", after.target_labels)
        self.assertTrue(_plan("dispatched", after.target_labels).noop)

    def test_permutation_independence_of_target_and_diff(self):
        labels = ("zeta", "idkmesh:verify:verified", "alpha", "idkmesh:route:blocked")
        first = _plan("proposed", labels)
        second = _plan("proposed", reversed(labels))
        self.assertEqual(first.target_labels, second.target_labels)
        self.assertEqual(first.add_labels, second.add_labels)
        self.assertEqual(first.remove_labels, second.remove_labels)

    def test_non_authority_report_is_stable_and_json_serializable(self):
        plan = _plan("decided", ("maintenance",))
        report = plan.to_dict()
        self.assertEqual(report["canonical_source_digest"], DIGEST)
        self.assertEqual(report["run_state"], "decided")
        self.assertFalse(report["verification_authority"])
        self.assertFalse(report["human_decision_authority"])
        self.assertFalse(report["integration_authority"])
        self.assertFalse(report["merge_authority"])
        self.assertIn('"noop": false', json.dumps(report, sort_keys=True))
        with self.assertRaises(FrozenInstanceError):
            plan.run_state = "proposed"

    def test_source_revision_mismatch_is_denied(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            _plan("admitted", expected_source_digest=OTHER_DIGEST)
        self.assertEqual(_plan("admitted", expected_source_digest=DIGEST).canonical_source_digest, DIGEST)

    def test_invalid_run_identity_state_and_digest_fail_closed(self):
        invalid = (
            {"run_id": "../sneaky"},
            {"run_id": ""},
            {"run_id": "n\nrun"},
            {"run_state": "APPROVED"},
            {"run_state": "accepted"},
            {"run_state": ""},
            {"run_state": None},
            {"canonical_source_digest": "sha256:" + "Z" * 64},
            {"canonical_source_digest": "sha256:" + "a" * 63},
            {"canonical_source_digest": None},
            {"expected_source_digest": "x"},
        )
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                _plan(**item)

    def test_invalid_label_sets_fail_closed(self):
        invalid = (
            "single-string",
            None,
            [""],
            ["bad\nlabel"],
            [" trailing "],
            ["x" * 51],
            ["bug", "BUG"],
            ["fine", None],
            ["tag"] * 2,
            (str(i) for i in range(1001)),
        )
        for item in invalid:
            with self.subTest(item=type(item).__name__), self.assertRaises(ValueError):
                _plan(labels=item)

    def test_input_list_is_not_mutated_and_no_external_effect(self):
        labels = ["help wanted", "idkmesh:work:decided"]
        snapshot = labels[:]
        plan = _plan("proposed", labels)
        self.assertEqual(labels, snapshot)
        self.assertFalse(plan.noop)
        self.assertEqual(plan.to_dict()["github_mutation_performed"], False)


if __name__ == "__main__":
    unittest.main()
