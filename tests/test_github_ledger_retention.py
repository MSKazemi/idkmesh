"""C9-H retention/reference policy (issue #597).

The policy is pure and advisory, so the tests are about what it refuses: a run
missing evidence its state requires, a reference that cannot be interpreted once
raw artifacts expire, a raw artifact that is the only copy of referenced
evidence, an unclassified kind, an active run, and any malformed policy or clock.

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import unittest

from idkmesh.github_ledger_recovery import reconstruct_run_state
from idkmesh.github_ledger_retention import (
    DEFAULT_RETENTION_POLICY,
    DURABLE_KINDS,
    SCHEMA_VERSION,
    TRANSIENT_KINDS,
    LedgerRetentionError,
    RawArtifact,
    RetentionPolicy,
    assess_ledger_size,
    check_run_retention,
    plan_artifact_expiry,
)


def _sibling(name):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_sibling_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_recovery_tests = _sibling("test_github_ledger_recovery")
Chain = _recovery_tests.Chain
D = _recovery_tests.D
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def _state(records):
    return reconstruct_run_state(records)


def _decided():
    return _state(_recovery_tests.happy_chain())


def _with_paths(state, **paths):
    """Give a recovered state repository-relative paths on its references."""

    def put(ref, path):
        return (ref[0], path)

    changes = {}
    if "candidate" in paths:
        changes["candidate_reference"] = put(state.candidate_reference, paths["candidate"])
    if "manifest" in paths:
        changes["result_manifest"] = put(state.result_manifest, paths["manifest"])
    if "verification" in paths:
        changes["verification_results"] = tuple(put(r, paths["verification"]) for r in state.verification_results)
    if "decision" in paths:
        changes["human_decision_record"] = put(state.human_decision_record, paths["decision"])
    return dataclasses.replace(state, **changes)


def _good_decided():
    return _with_paths(
        _decided(),
        candidate="evidence/run/candidate.json",
        manifest="evidence/run/manifest.json",
        verification="evidence/run/verification.json",
        decision="evidence/run/decision.json",
    )


def _codes(report):
    return sorted(f.code for f in report.findings)


class KindVocabularyTests(unittest.TestCase):
    def test_durable_and_transient_kinds_are_disjoint(self):
        self.assertFalse(DURABLE_KINDS & TRANSIENT_KINDS)

    def test_the_four_issue_evidence_kinds_are_durable(self):
        for kind in ("candidate_reference", "result_manifest", "verification_result", "human_decision_record"):
            self.assertIn(kind, DURABLE_KINDS)

    def test_actions_artifacts_logs_and_caches_are_transient(self):
        for kind in ("actions_artifact", "actions_log", "actions_cache"):
            self.assertIn(kind, TRANSIENT_KINDS)


class PolicyTests(unittest.TestCase):
    def test_defaults_are_valid_and_conservative(self):
        policy = DEFAULT_RETENTION_POLICY
        self.assertGreaterEqual(policy.transient_min_age_days, 1)
        self.assertLess(policy.ledger_warn_bytes, policy.ledger_limit_bytes)
        self.assertLessEqual(policy.require_storage_path, DURABLE_KINDS)

    def test_from_mapping_round_trips_overrides(self):
        policy = RetentionPolicy.from_mapping(
            {"schema_version": SCHEMA_VERSION, "transient_min_age_days": 7,
             "ledger_warn_bytes": 10, "ledger_limit_bytes": 20,
             "require_storage_path": ["result_manifest"], "transient_path_segments": ["tmp"]}
        )
        self.assertEqual(policy.transient_min_age_days, 7)
        self.assertEqual(policy.require_storage_path, frozenset({"result_manifest"}))

    def test_malformed_policies_are_refused(self):
        base = {"schema_version": SCHEMA_VERSION}
        bad = [
            "not-a-mapping",
            {},
            {"schema_version": "other"},
            {**base, "surprise": 1},
            {**base, "transient_min_age_days": 0},
            {**base, "transient_min_age_days": True},
            {**base, "transient_min_age_days": 1.5},
            {**base, "transient_min_age_days": 10**6},
            {**base, "ledger_warn_bytes": 20, "ledger_limit_bytes": 20},
            {**base, "ledger_warn_bytes": -1},
            {**base, "require_storage_path": "result_manifest"},
            {**base, "require_storage_path": ["actions_artifact"]},
            {**base, "require_storage_path": [3]},
            {**base, "transient_path_segments": ["a/b"]},
            {**base, "transient_path_segments": [""]},
        ]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(LedgerRetentionError):
                RetentionPolicy.from_mapping(data)

    def test_direct_construction_is_validated_too(self):
        with self.assertRaises(LedgerRetentionError):
            RetentionPolicy(transient_min_age_days=0)
        with self.assertRaises(LedgerRetentionError):
            RetentionPolicy(require_storage_path=frozenset({"nonsense"}))


class RunRetentionTests(unittest.TestCase):
    def test_a_fully_referenced_decided_run_is_ok(self):
        report = check_run_retention(_good_decided())
        self.assertTrue(report.ok, report.findings)
        self.assertEqual(report.state, "decided")

    def test_digest_only_references_are_unlocatable_where_the_policy_requires_a_path(self):
        report = check_run_retention(_decided())
        self.assertEqual(
            _codes(report),
            ["unlocatable_reference"] * 3,  # manifest, verification, decision; candidate is not required
        )
        self.assertEqual(
            sorted(f.slot for f in report.findings),
            ["human_decision_record", "result_manifest", "verification_result[1]"],
        )

    def test_the_path_requirement_is_configurable(self):
        relaxed = dataclasses.replace(DEFAULT_RETENTION_POLICY, require_storage_path=frozenset())
        self.assertTrue(check_run_retention(_decided(), relaxed).ok)

    def test_every_prefix_of_a_complete_run_satisfies_its_own_state(self):
        # A crash can land after any record: the evidence a state requires is
        # already present at that state, so no prefix reports a false finding.
        records = _recovery_tests.happy_chain()
        relaxed = dataclasses.replace(DEFAULT_RETENTION_POLICY, require_storage_path=frozenset())
        for n in range(1, len(records) + 1):
            state = _state(records[:n])
            with self.subTest(state=state.state):
                self.assertTrue(check_run_retention(state, relaxed).ok)

    def test_missing_evidence_is_reported_for_each_state(self):
        relaxed = dataclasses.replace(DEFAULT_RETENTION_POLICY, require_storage_path=frozenset())
        decided = _decided()
        cases = [
            ("candidate_observed", dict(candidate_reference=None), ["missing_candidate_reference"]),
            ("normalized", dict(result_manifest=None), ["missing_result_manifest"]),
            ("evidence_ready", dict(verification_results=()), ["missing_verification_result"]),
            ("decided", dict(human_decision_record=None), ["missing_human_decision_record"]),
            (
                "decided",
                dict(candidate_reference=None, result_manifest=None, verification_results=(),
                     human_decision_record=None),
                ["missing_candidate_reference", "missing_human_decision_record",
                 "missing_result_manifest", "missing_verification_result"],
            ),
        ]
        for state_name, changes, expected in cases:
            state = dataclasses.replace(decided, state=state_name, **changes)
            with self.subTest(state=state_name, changes=sorted(changes)):
                self.assertEqual(_codes(check_run_retention(state, relaxed)), expected)

    def test_a_cancelled_run_needs_no_progress_but_its_references_are_still_checked(self):
        records = _recovery_tests.happy_chain()[:4]
        chain = Chain()
        chain.records = list(records)
        chain.add("cancelled", attempt=1, submission="submitted", run="r1", session="s1")
        cancelled = _state(chain.records)
        self.assertTrue(check_run_retention(cancelled).ok)
        poisoned = dataclasses.replace(cancelled, candidate_reference=("sha256:xyz", None))
        self.assertEqual(_codes(check_run_retention(poisoned)), ["malformed_digest"])

    def test_failures_do_not_trigger_findings(self):
        chain = Chain()
        chain.add("proposed").add("previewed").add("admitted")
        chain.add("dispatched", attempt=1, submission="submitted", run="r1")
        chain.add("attempt_failed", attempt=1, submission="submitted", failure=("timeout", "provider", True))
        state = _state(chain.records)
        self.assertEqual(len(state.failures), 1)
        self.assertTrue(check_run_retention(state).ok)

    def test_malformed_digest_is_a_finding(self):
        good = _good_decided()
        for digest in ("", "sha256:abc", "md5:" + "a" * 32, "sha256:" + "G" * 64, "sha256:" + "A" * 64):
            state = dataclasses.replace(good, result_manifest=(digest, "evidence/m.json"))
            with self.subTest(digest=digest):
                self.assertIn("malformed_digest", _codes(check_run_retention(state)))

    def test_unsafe_paths_are_findings(self):
        for path in ("/abs/m.json", "a/../m.json", "a//m.json", "a\\m.json", "dir/", "a/./m.json", "a/\x00b"):
            state = dataclasses.replace(_good_decided(), result_manifest=(D("2"), path))
            with self.subTest(path=path):
                self.assertEqual(_codes(check_run_retention(state)), ["unsafe_path"])

    def test_transient_runner_locations_are_not_durable_evidence(self):
        for path in (
            "_temp/work/manifest.json",
            "evidence/artifacts/manifest.json",
            "runner/_work/m.json",
            "evidence/cache/m.json",
        ):
            state = dataclasses.replace(_good_decided(), result_manifest=(D("2"), path))
            with self.subTest(path=path):
                self.assertEqual(_codes(check_run_retention(state)), ["transient_locator"])

    def test_findings_do_not_echo_raw_values_beyond_the_slot(self):
        state = dataclasses.replace(_good_decided(), result_manifest=("sha256:SECRET-token", "ok/m.json"))
        text = repr(check_run_retention(state))
        self.assertNotIn("SECRET-token", text)


class ArtifactExpiryTests(unittest.TestCase):
    OLD = NOW - timedelta(days=200)

    def _plan(self, artifacts, **kwargs):
        kwargs.setdefault("referenced_digests", ())
        kwargs.setdefault("durable_digests", ())
        kwargs.setdefault("now", NOW)
        return plan_artifact_expiry(artifacts, **kwargs)

    def test_an_old_unreferenced_transient_artifact_may_expire(self):
        (decision,) = self._plan([RawArtifact("a1", "actions_log", self.OLD)])
        self.assertTrue(decision.may_expire)
        self.assertEqual(decision.decision, "may_expire")

    def test_a_young_artifact_is_retained_at_the_boundary(self):
        edge = NOW - timedelta(days=DEFAULT_RETENTION_POLICY.transient_min_age_days)
        almost = edge + timedelta(seconds=1)
        got = self._plan([RawArtifact("old", "actions_log", edge), RawArtifact("young", "actions_log", almost)])
        self.assertEqual([d.decision for d in got], ["may_expire", "retain_young"])

    def test_a_future_timestamp_is_retained(self):
        (decision,) = self._plan([RawArtifact("f", "actions_log", NOW + timedelta(days=1))])
        self.assertEqual(decision.decision, "retain_young")

    def test_the_sole_copy_of_referenced_evidence_is_retained(self):
        digest = D("7")
        artifact = RawArtifact("a1", "raw_candidate_bundle", self.OLD, digest=digest)
        (alone,) = self._plan([artifact], referenced_digests=[digest])
        self.assertEqual(alone.decision, "retain_sole_copy")
        (backed_up,) = self._plan([artifact], referenced_digests=[digest], durable_digests=[digest])
        self.assertEqual(backed_up.decision, "may_expire")

    def test_a_durable_digest_that_is_not_referenced_does_not_matter(self):
        digest = D("7")
        artifact = RawArtifact("a1", "actions_artifact", self.OLD, digest=digest)
        (decision,) = self._plan([artifact], durable_digests=[digest])
        self.assertEqual(decision.decision, "may_expire")

    def test_an_artifact_without_a_digest_cannot_be_a_sole_copy(self):
        (decision,) = self._plan([RawArtifact("a1", "actions_artifact", self.OLD)], referenced_digests=[D("1")])
        self.assertEqual(decision.decision, "may_expire")

    def test_durable_and_unknown_kinds_never_expire(self):
        got = self._plan(
            [RawArtifact(f"k{i}", kind, self.OLD) for i, kind in enumerate(sorted(DURABLE_KINDS) + ["mystery", ""])]
        )
        self.assertFalse(any(d.may_expire for d in got))
        self.assertEqual({d.decision for d in got}, {"retain_durable_kind", "retain_unclassified"})

    def test_artifacts_of_an_active_run_are_retained(self):
        artifact = RawArtifact("a1", "actions_log", self.OLD, run_id="run-1")
        (active,) = self._plan([artifact], active_run_ids=["run-1"])
        self.assertEqual(active.decision, "retain_active_run")
        (other,) = self._plan([artifact], active_run_ids=["run-2"])
        self.assertTrue(other.may_expire)

    def test_a_longer_policy_minimum_is_honoured(self):
        policy = dataclasses.replace(DEFAULT_RETENTION_POLICY, transient_min_age_days=365)
        (decision,) = self._plan([RawArtifact("a1", "actions_log", self.OLD)], policy=policy)
        self.assertEqual(decision.decision, "retain_young")

    def test_planning_does_not_mutate_or_consume_inputs_and_is_deterministic(self):
        artifacts = [RawArtifact("a1", "actions_log", self.OLD), RawArtifact("a2", "actions_cache", self.OLD)]
        first = self._plan(artifacts)
        self.assertEqual(first, self._plan(tuple(artifacts)))
        self.assertEqual([d.artifact_id for d in first], ["a1", "a2"])

    def test_naive_or_invalid_inputs_are_refused(self):
        with self.assertRaises(LedgerRetentionError):
            self._plan([], now=datetime(2026, 10, 14))
        with self.assertRaises(LedgerRetentionError):
            self._plan([], now="2026-10-14")
        for kwargs in (
            dict(artifact_id="", kind="actions_log", created_at=self.OLD),
            dict(artifact_id="x" * 257, kind="actions_log", created_at=self.OLD),
            dict(artifact_id="a", kind=None, created_at=self.OLD),
            dict(artifact_id="a", kind="actions_log", created_at=datetime(2026, 1, 1)),
            dict(artifact_id="a", kind="actions_log", created_at=self.OLD, digest="sha256:short"),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(LedgerRetentionError):
                RawArtifact(**kwargs)


class LedgerSizeTests(unittest.TestCase):
    def test_thresholds_and_the_only_remedy_named(self):
        policy = RetentionPolicy(ledger_warn_bytes=100, ledger_limit_bytes=200)
        cases = [
            (0, "ok", "none"),
            (99, "ok", "none"),
            (100, "warn", "plan_new_shard"),
            (199, "warn", "plan_new_shard"),
            (200, "exceeded", "operator_decision_new_shard"),
            (10**9, "exceeded", "operator_decision_new_shard"),
        ]
        for size, status, action in cases:
            result = assess_ledger_size(size, 5, policy)
            with self.subTest(size=size):
                self.assertEqual((result.status, result.action), (status, action))
                self.assertNotIn("delete", result.action)
                self.assertNotIn("compact", result.action)
                self.assertNotIn("rewrite", result.action)

    def test_invalid_measurements_are_refused(self):
        for total, count in ((-1, 0), (0, -1), (True, 0), (0, 1.5), ("1", 0)):
            with self.subTest(total=total, count=count), self.assertRaises(LedgerRetentionError):
                assess_ledger_size(total, count)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
