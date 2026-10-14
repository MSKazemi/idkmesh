"""Tests for judging a recovery drill against the profile's RPO/RTO (E6, #673)."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from idkmesh.enterprise_recovery_drill import (
    DRILL_KIND,
    DRILL_VERSION,
    EVALUATION_KIND,
    OUTCOMES,
    RecoveryDrill,
    RecoveryDrillError,
    evaluate_recovery_drill,
)

ROOT = Path(__file__).resolve().parents[1]
G1 = json.loads(
    (ROOT / "examples" / "enterprise" / "g1-github-native.example.json").read_text("utf-8")
)
G2 = json.loads(
    (ROOT / "examples" / "enterprise" / "g2-self-hosted.example.json").read_text("utf-8")
)
DIGEST = "sha256:" + "ab" * 32
FAILURE = 1_790_000_000
RPO_G2 = G2["reliability"]["rpo_minutes"] * 60  # 900
RTO_G2 = G2["reliability"]["rto_minutes"] * 60  # 3600
NOW = FAILURE + RTO_G2 + 600


def drill(profile=G2, *, loss=0, recovery=600, **overrides) -> dict:
    """A well-formed drill record with the given measured loss and recovery."""

    value = {
        "kind": DRILL_KIND,
        "schema_version": DRILL_VERSION,
        "drill_id": "drill:2026-10-14-restore",
        "profile_id": profile["profile_id"],
        "last_acknowledged_write_epoch": FAILURE - 5,
        "last_recovered_write_epoch": FAILURE - 5 - loss,
        "failure_injected_at_epoch": FAILURE,
        "service_restored_at_epoch": FAILURE + recovery,
        "integrity_verified": True,
        "evidence_digest": DIGEST,
    }
    value.update(overrides)
    return value


def evaluate(record, profile=G2, **kwargs):
    kwargs.setdefault("evaluated_at_epoch", NOW)
    return evaluate_recovery_drill(profile, record, **kwargs)


class ObjectiveTests(unittest.TestCase):
    def test_the_example_profiles_declare_what_these_tests_assume(self) -> None:
        self.assertEqual((RPO_G2, RTO_G2), (900, 3600))
        self.assertEqual(G1["reliability"]["rpo_minutes"], 0)

    def test_a_drill_inside_both_objectives_passes(self) -> None:
        result = evaluate(drill(loss=120, recovery=1200))
        self.assertEqual((result.outcome, result.code), ("PASS", "objectives_met"))
        self.assertEqual(result.measured, {"data_loss_seconds": 120, "recovery_seconds": 1200})
        self.assertEqual(result.objectives, {"rpo_seconds": 900, "rto_seconds": 3600})
        self.assertEqual(result.checks, {"integrity": "pass", "rpo": "pass", "rto": "pass"})

    def test_objectives_are_inclusive_and_one_second_over_fails(self) -> None:
        self.assertEqual(evaluate(drill(loss=RPO_G2)).outcome, "PASS")
        over = evaluate(drill(loss=RPO_G2 + 1))
        self.assertEqual((over.outcome, over.code), ("FAIL", "rpo_exceeded"))
        self.assertEqual(evaluate(drill(recovery=RTO_G2)).outcome, "PASS")
        slow = evaluate(drill(recovery=RTO_G2 + 1))
        self.assertEqual((slow.outcome, slow.code), ("FAIL", "rto_exceeded"))

    def test_a_zero_rpo_profile_tolerates_no_data_loss(self) -> None:
        self.assertEqual(evaluate(drill(G1, loss=0), G1).outcome, "PASS")
        lost = evaluate(drill(G1, loss=1), G1)
        self.assertEqual((lost.outcome, lost.code), ("FAIL", "rpo_exceeded"))

    def test_idle_time_before_the_failure_is_not_data_loss(self) -> None:
        # Last write an hour before the failure, fully recovered: loss is zero.
        record = drill(
            last_acknowledged_write_epoch=FAILURE - 3600,
            last_recovered_write_epoch=FAILURE - 3600,
        )
        self.assertEqual(evaluate(record).measured["data_loss_seconds"], 0)
        self.assertEqual(evaluate(record).outcome, "PASS")

    def test_recovering_more_than_was_acknowledged_is_zero_loss_not_negative(self) -> None:
        record = drill(
            last_acknowledged_write_epoch=FAILURE - 100,
            last_recovered_write_epoch=FAILURE - 50,
        )
        self.assertEqual(evaluate(record).measured["data_loss_seconds"], 0)

    def test_unverified_integrity_fails_even_with_perfect_timings(self) -> None:
        result = evaluate(drill(integrity_verified=False))
        self.assertEqual((result.outcome, result.code), ("FAIL", "integrity_not_verified"))
        self.assertEqual(result.checks["integrity"], "fail")

    def test_every_failing_check_is_reported_not_just_the_first(self) -> None:
        result = evaluate(
            drill(loss=RPO_G2 + 1, recovery=RTO_G2 + 1, integrity_verified=False)
        )
        self.assertEqual(result.code, "integrity_not_verified")
        self.assertEqual(result.checks, {"integrity": "fail", "rpo": "fail", "rto": "fail"})

    def test_a_drill_object_is_accepted_as_well_as_a_mapping(self) -> None:
        parsed = RecoveryDrill.from_dict(drill())
        self.assertEqual(evaluate(parsed).outcome, "PASS")


class UnknownTests(unittest.TestCase):
    """Nothing trustworthy to judge is UNKNOWN, never a pass."""

    def assert_unknown(self, result, code: str) -> None:
        self.assertEqual((result.outcome, result.code), ("UNKNOWN", code))
        self.assertEqual(result.measured, {"data_loss_seconds": None, "recovery_seconds": None})
        self.assertEqual(set(result.checks.values()), {"unknown"})

    def test_no_drill_is_unknown(self) -> None:
        result = evaluate(None)
        self.assert_unknown(result, "no_drill_evidence")
        self.assertEqual(result.objectives, {"rpo_seconds": 900, "rto_seconds": 3600})

    def test_an_invalid_profile_is_unknown(self) -> None:
        broken = deepcopy(G2)
        broken["reliability"]["rpo_minutes"] = -1
        self.assert_unknown(evaluate(drill(), broken), "invalid_profile")
        self.assert_unknown(evaluate(drill(), {"kind": "nope"}), "invalid_profile")
        self.assert_unknown(evaluate(drill(), None), "invalid_profile")

    def test_a_drill_for_another_profile_is_unknown(self) -> None:
        result = evaluate(drill(profile_id="someone-elses-profile"))
        self.assert_unknown(result, "profile_mismatch")

    def test_a_drill_that_finished_after_the_evaluation_is_unknown(self) -> None:
        record = drill(recovery=600)
        self.assert_unknown(
            evaluate(record, evaluated_at_epoch=FAILURE + 599), "drill_from_future"
        )
        self.assertEqual(
            evaluate(record, evaluated_at_epoch=FAILURE + 600).outcome, "PASS"
        )

    def test_freshness_is_checked_only_when_asked_and_is_inclusive(self) -> None:
        record = drill(recovery=600)
        restored = FAILURE + 600
        self.assertEqual(evaluate(record, evaluated_at_epoch=restored + 10**7).outcome, "PASS")
        self.assertEqual(
            evaluate(record, evaluated_at_epoch=restored + 86_400, max_drill_age_seconds=86_400).outcome,
            "PASS",
        )
        self.assert_unknown(
            evaluate(record, evaluated_at_epoch=restored + 86_401, max_drill_age_seconds=86_400),
            "stale_drill",
        )

    def test_a_stale_failing_drill_is_unknown_not_fail(self) -> None:
        # Old evidence, whatever it said, is not a current measurement.
        record = drill(loss=RPO_G2 + 1)
        result = evaluate(record, evaluated_at_epoch=NOW + 10**7, max_drill_age_seconds=3600)
        self.assert_unknown(result, "stale_drill")


class ParsingTests(unittest.TestCase):
    def rejected(self, value) -> str:
        with self.assertRaises(RecoveryDrillError) as caught:
            RecoveryDrill.from_dict(value)
        return caught.exception.code

    def test_unknown_and_missing_fields_are_rejected(self) -> None:
        extra = drill()
        extra["note"] = "free text"
        self.assertEqual(self.rejected(extra), "invalid_fields")
        missing = drill()
        del missing["evidence_digest"]
        self.assertEqual(self.rejected(missing), "invalid_fields")
        self.assertEqual(self.rejected([]), "invalid_record")
        self.assertEqual(self.rejected({1: "x"}), "invalid_record")

    def test_kind_and_version_are_pinned(self) -> None:
        self.assertEqual(self.rejected(drill(kind="other")), "invalid_kind")
        self.assertEqual(self.rejected(drill(schema_version="9.9")), "invalid_version")

    def test_values_are_not_coerced(self) -> None:
        for field in (
            "last_acknowledged_write_epoch",
            "last_recovered_write_epoch",
            "failure_injected_at_epoch",
            "service_restored_at_epoch",
        ):
            for bad in (True, 1.5, "1790000000", -1, 4_102_444_801, None):
                with self.subTest(field=field, value=repr(bad)):
                    self.assertEqual(self.rejected(drill(**{field: bad})), "invalid_epoch")
        for bad in (1, 0, "true", None):
            with self.subTest(integrity=repr(bad)):
                self.assertEqual(self.rejected(drill(integrity_verified=bad)), "invalid_boolean")
        for bad in ("sha256:" + "AB" * 32, "sha256:abc", "md5:" + "a" * 32, "", None):
            with self.subTest(digest=repr(bad)):
                self.assertEqual(self.rejected(drill(evidence_digest=bad)), "invalid_digest")
        for field in ("drill_id", "profile_id"):
            for bad in ("", " lead", "has space", "x" * 300, None, 7):
                with self.subTest(field=field, value=repr(bad)):
                    self.assertEqual(self.rejected(drill(**{field: bad})), "invalid_identifier")

    def test_time_cannot_run_backwards_inside_a_drill(self) -> None:
        self.assertEqual(
            self.rejected(drill(last_acknowledged_write_epoch=FAILURE + 1)),
            "acknowledged_write_after_failure",
        )
        self.assertEqual(
            self.rejected(drill(last_recovered_write_epoch=FAILURE + 1)),
            "recovered_write_after_failure",
        )
        self.assertEqual(
            self.rejected(drill(service_restored_at_epoch=FAILURE - 1)),
            "restored_before_failure",
        )

    def test_a_rejected_record_is_unknown_when_evaluated(self) -> None:
        result = evaluate(drill(integrity_verified="yes"))
        self.assertEqual((result.outcome, result.code), ("UNKNOWN", "invalid_drill"))
        self.assertIn("invalid_boolean", result.message)

    def test_invalid_call_arguments_raise_instead_of_passing(self) -> None:
        for bad in (True, -1, 1.5, "1", 4_102_444_801):
            with self.subTest(evaluated_at=repr(bad)), self.assertRaises(ValueError):
                evaluate_recovery_drill(G2, drill(), evaluated_at_epoch=bad)
        for bad in (0, -5, True, 1.5):
            with self.subTest(max_age=repr(bad)), self.assertRaises(ValueError):
                evaluate(drill(), max_drill_age_seconds=bad)


class OutputHygieneTests(unittest.TestCase):
    def test_untrusted_text_is_never_echoed(self) -> None:
        hostile = "drill\n::error::pwned ghp_secret"
        for record in (
            drill(drill_id=hostile),
            drill(profile_id=hostile),
            drill(note=hostile),
        ):
            blob = json.dumps(evaluate(record).to_dict())
            self.assertNotIn("pwned", blob)
            self.assertNotIn("ghp_secret", blob)
        # A mismatched but well-formed profile id is an identifier, so it is shown.
        shown = evaluate(drill(profile_id="other-profile")).to_dict()
        self.assertEqual(shown["drill_id"], "drill:2026-10-14-restore")

    def test_the_projection_has_a_fixed_shape_and_no_authority(self) -> None:
        body = evaluate(drill()).to_dict()
        self.assertEqual(
            set(body),
            {
                "kind", "schema_version", "outcome", "code", "message", "profile_id",
                "drill_id", "objectives", "measured", "checks", "authority",
            },
        )
        self.assertEqual(body["kind"], EVALUATION_KIND)
        self.assertIn(body["outcome"], OUTCOMES)
        self.assertEqual(
            body["authority"],
            {"runs_drill": False, "restores_data": False, "grants_runtime_authority": False},
        )

    def test_evaluation_is_deterministic(self) -> None:
        self.assertEqual(evaluate(drill(loss=30)).to_dict(), evaluate(drill(loss=30)).to_dict())


if __name__ == "__main__":
    unittest.main()
