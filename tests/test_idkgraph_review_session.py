from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from tools import idkgraph_review_session as review_session


ROOT = Path(__file__).resolve().parents[1]


def make_valid_session() -> dict:
    reviews = []
    for rank, path in enumerate(review_session.COHORT, 1):
        label = review_session.REFERENCE_LABELS[path]
        recommend = label == "navigation_gap"
        reviews.append(
            {
                "rank": rank,
                "path": path,
                "label": label,
                "confidence": 0.8,
                "recommend_change": recommend,
                "proposed_change_type": "index" if recommend else "none",
                "evidence_note": f"Independent evidence note for frozen item {rank}.",
            }
        )
    return {
        "schema_version": review_session.SCHEMA_VERSION,
        "experiment": review_session.EXPERIMENT,
        "cohort": {
            "seed": review_session.SEED,
            "frozen_source_revision": review_session.FROZEN_SOURCE_REVISION,
            "candidate_count": len(review_session.COHORT),
        },
        "reviewer": {
            "public_id": "independent-reviewer-example",
            "independence_statement": "I did not generate the original PR #166 labels.",
            "anchoring_state": "blind_to_original_labels",
        },
        "timing": {
            "started_at": None,
            "completed_at": None,
            "active_review_minutes": 30,
            "interruption_minutes": 5,
        },
        "reviews": reviews,
        "notes": "Synthetic unit-test evidence only.",
    }


class ReviewSessionValidationTests(unittest.TestCase):
    def test_complete_reference_matching_session_is_valid(self) -> None:
        session = make_valid_session()
        self.assertEqual(review_session.validate_session(session), [])

        summary = review_session.summarize_session(session)
        metrics = summary["descriptive_metrics"]
        self.assertEqual(metrics["exact_label_matches"], 15)
        self.assertEqual(metrics["exact_label_agreement"], 1.0)
        self.assertEqual(metrics["recommended_change_count"], 6)
        self.assertEqual(metrics["minutes_per_candidate"], 2.0)
        self.assertEqual(metrics["minutes_per_recommended_change"], 5.0)
        self.assertEqual(
            metrics["action_confusion_matrix"],
            {
                "reference_action": {
                    "action": 6,
                    "no_immediate_action": 0,
                    "unresolved": 0,
                },
                "reference_no_immediate_action": {
                    "action": 0,
                    "no_immediate_action": 9,
                    "unresolved": 0,
                },
            },
        )

    def test_disagreement_and_uncertainty_remain_visible(self) -> None:
        session = make_valid_session()
        session["reviews"][1]["label"] = "intentional_memory"
        session["reviews"][1]["recommend_change"] = False
        session["reviews"][1]["proposed_change_type"] = "none"
        session["reviews"][2]["label"] = "uncertain"
        session["reviews"][2]["recommend_change"] = False
        session["reviews"][2]["proposed_change_type"] = "none"

        self.assertEqual(review_session.validate_session(session), [])
        summary = review_session.summarize_session(session)
        metrics = summary["descriptive_metrics"]
        self.assertEqual(metrics["exact_label_matches"], 13)
        self.assertEqual(metrics["disagreement_count"], 2)
        self.assertEqual(
            metrics["action_confusion_matrix"]["reference_action"],
            {"action": 4, "no_immediate_action": 1, "unresolved": 1},
        )
        self.assertEqual(len(summary["disagreements"]), 2)

    def test_example_template_is_intentionally_not_complete_evidence(self) -> None:
        example = json.loads(
            (ROOT / "examples/idkgraph-p1-review-session.example.json").read_text(
                encoding="utf-8"
            )
        )
        errors = review_session.validate_session(example)
        self.assertTrue(any("public_id" in error for error in errors))
        self.assertTrue(any("active_review_minutes" in error for error in errors))
        self.assertTrue(any("evidence_note" in error for error in errors))

    def test_reordered_or_replaced_cohort_is_rejected(self) -> None:
        session = make_valid_session()
        session["reviews"][0], session["reviews"][1] = (
            session["reviews"][1],
            session["reviews"][0],
        )
        errors = review_session.validate_session(session)
        self.assertTrue(any("rank must equal" in error for error in errors))
        self.assertTrue(any("path does not match frozen cohort" in error for error in errors))

    def test_wrong_frozen_source_revision_is_rejected(self) -> None:
        session = make_valid_session()
        session["cohort"]["frozen_source_revision"] = "not-the-frozen-revision"
        errors = review_session.validate_session(session)
        self.assertTrue(any("frozen_source_revision" in error for error in errors))

    def test_nonfinite_or_out_of_range_measurements_are_rejected(self) -> None:
        for value in (math.nan, math.inf, -0.1, 1.1):
            with self.subTest(confidence=value):
                session = make_valid_session()
                session["reviews"][0]["confidence"] = value
                errors = review_session.validate_session(session)
                self.assertTrue(any("confidence" in error for error in errors))

        session = make_valid_session()
        session["timing"]["active_review_minutes"] = math.inf
        errors = review_session.validate_session(session)
        self.assertTrue(any("active_review_minutes" in error for error in errors))

    def test_other_requires_an_explicit_other_label(self) -> None:
        session = make_valid_session()
        session["reviews"][0]["label"] = "other"
        errors = review_session.validate_session(session)
        self.assertTrue(any("other_label" in error for error in errors))

        session["reviews"][0]["other_label"] = "archive_policy_question"
        self.assertEqual(review_session.validate_session(session), [])

    def test_validator_does_not_mutate_session(self) -> None:
        session = make_valid_session()
        before = copy.deepcopy(session)
        review_session.validate_session(session)
        review_session.summarize_session(session)
        self.assertEqual(session, before)


if __name__ == "__main__":
    unittest.main()
