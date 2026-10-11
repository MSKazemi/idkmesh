"""C9-E recovery reader (issue #597): current run state from ledger records alone.

Pure-function tests over synthetic chains plus one pass through a real Git
ledger. The properties that matter for restart safety: reconstruction works from
*any* prefix (a crash can happen after any record), negative events are never
dropped, an ambiguous provider submission is surfaced, and a history no real run
could have produced is refused rather than papered over.

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from idkmesh.github_ledger_append import GitLedger, ledger_ref_for_run
from idkmesh.github_ledger_recovery import (
    RecoveryError,
    reconstruct_run_state,
    recover_run,
)
from idkmesh.github_ledger_serialization import (
    GitHubLedgerSerializationError,
    serialize_github_ledger_chain,
    serialize_github_ledger_record,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "github-ledger"
GIT = shutil.which("git")
D = lambda c: "sha256:" + c * 64  # noqa: E731


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class Chain:
    """Builds a valid record chain one observation at a time."""

    def __init__(self):
        self.records = []

    def add(self, state, *, attempt=None, submission=None, failure=None, candidate=None,
            manifest=None, verification=(), human=("not_recorded", None), **provider_ids):
        sequence = len(self.records) + 1
        record = copy.deepcopy(_fixture("00000000000000000002.json"))
        record["ledger_sequence"] = sequence
        record["previous_record_digest"] = (
            serialize_github_ledger_record(self.records[-1]).record_digest if self.records else None
        )
        record["record_id"] = f"ledger/run/{sequence:06d}"
        record["event"].update(event_id=f"event/{sequence}", state=state, event_type=f"run.{state}")
        record["attempt"] = None
        record["provider"] = None
        record["idempotency"]["attempt_number"] = attempt or 1
        if attempt is not None:
            record["attempt"] = {
                "attempt_id": f"attempt-{attempt}", "attempt_number": attempt,
                "connector_id": "jules-primary", "reason": "initial" if attempt == 1 else "retry",
            }
        if submission is not None:
            record["provider"] = {
                "driver": "jules", "driver_version": "0.1", "submission_state": submission,
                "external_run_id": provider_ids.get("run"), "external_session_id": provider_ids.get("session"),
                "external_job_id": provider_ids.get("job"),
            }
        if failure is not None:
            record["failure"] = {"code": failure[0], "classification": failure[1], "retryable": failure[2]}
        if candidate:
            record["candidate_reference"] = {"kind": "candidate_reference", "digest": D(candidate), "storage_path": None}
        if manifest:
            record["result_manifest"] = {"kind": "result_manifest", "digest": D(manifest), "storage_path": None}
        record["verification_results"] = [
            {"kind": "verification_result", "digest": D(v), "storage_path": None} for v in verification
        ]
        state_, rec = human
        record["human_decision"] = {
            "state": state_,
            "record": None if rec is None else {"kind": "human_decision_record", "digest": D(rec), "storage_path": None},
        }
        self.records.append(record)
        return self


def happy_chain():
    c = Chain()
    c.add("proposed").add("previewed").add("admitted")
    c.add("dispatched", attempt=1, submission="submitted", run="r1", session="s1")
    c.add("candidate_observed", attempt=1, submission="submitted", candidate="1")
    c.add("normalized", attempt=1, manifest="2")
    c.add("verification_requested", attempt=1)
    c.add("evidence_ready", attempt=1, verification=("3",))
    c.add("awaiting_human_decision", attempt=1, human=("pending", None))
    c.add("decided", attempt=1, human=("recorded", "4"))
    return c.records


class ReconstructionTests(unittest.TestCase):
    def test_the_c9b_fixture_is_a_valid_chain_but_not_a_legal_run_history(self):
        # The frozen C9-B fixture exercises serialization and linking only: it
        # goes proposed -> admitted, skipping `previewed`. As a chain it is fine;
        # as a history no Product Spine run could have produced it, and recovery
        # says so instead of reconstructing a state it could not have reached.
        records = [_fixture("00000000000000000001.json"), _fixture("00000000000000000002.json")]
        serialize_github_ledger_chain(records)  # the chain itself verifies
        with self.assertRaises(RecoveryError) as caught:
            reconstruct_run_state(records)
        self.assertEqual(caught.exception.reason, "illegal_transition")
        # The first record alone is a perfectly good one-record history.
        self.assertEqual(reconstruct_run_state(records[:1]).state, "proposed")

    def test_a_complete_run_is_terminal_and_carries_all_its_evidence(self):
        state = reconstruct_run_state(happy_chain())
        self.assertEqual(state.state, "decided")
        self.assertTrue(state.terminal)
        self.assertEqual(state.candidate_reference, (D("1"), None))
        self.assertEqual(state.result_manifest, (D("2"), None))
        self.assertEqual(state.verification_results, ((D("3"), None),))
        self.assertEqual(state.human_decision_state, "recorded")
        self.assertEqual(state.human_decision_record, (D("4"), None))
        (attempt,) = state.attempts
        self.assertEqual((attempt.attempt_id, attempt.submission_state, attempt.external_run_id),
                         ("attempt-1", "submitted", "r1"))
        self.assertFalse(state.needs_reconciliation)

    def test_reconstruction_works_from_every_prefix(self):
        # A crash can land after any record; each prefix must be readable.
        records = happy_chain()
        seen = []
        for n in range(1, len(records) + 1):
            state = reconstruct_run_state(records[:n])
            self.assertEqual(state.last_sequence, n)
            self.assertEqual(state.state, records[n - 1]["event"]["state"])
            seen.append(state.state)
        self.assertEqual(seen[0], "proposed")
        self.assertEqual(seen[-1], "decided")
        self.assertFalse(any(reconstruct_run_state(records[:n]).terminal for n in range(1, 10)))

    def test_it_is_deterministic_and_does_not_mutate_its_input(self):
        records = happy_chain()
        before = copy.deepcopy(records)
        self.assertEqual(reconstruct_run_state(records), reconstruct_run_state(records))
        self.assertEqual(records, before)


class NegativeEvidenceTests(unittest.TestCase):
    def retried_chain(self):
        c = Chain()
        c.add("proposed").add("previewed").add("admitted")
        c.add("dispatched", attempt=1, submission="submitted", run="r1")
        c.add("attempt_failed", attempt=1, submission="definite_failure",
              failure=("provider_rejected", "provider", True))
        c.add("dispatched", attempt=2, submission="submitted", run="r2")
        return c.records

    def test_a_failed_attempt_stays_visible_after_a_retry(self):
        state = reconstruct_run_state(self.retried_chain())
        self.assertEqual(state.state, "dispatched")
        self.assertEqual([a.attempt_number for a in state.attempts], [1, 2])
        self.assertEqual(state.attempts[0].submission_state, "definite_failure")
        self.assertEqual(state.attempts[0].failure, ("provider_rejected", "provider", True))
        self.assertEqual(len(state.failures), 1)
        self.assertEqual(state.failures[0].attempt_id, "attempt-1")
        self.assertEqual(state.failures[0].sequence, 5)

    def test_every_failure_observation_is_kept_in_order(self):
        c = Chain()
        c.add("proposed").add("previewed").add("admitted")
        c.add("dispatched", attempt=1, submission="submitted")
        c.add("attempt_failed", attempt=1, submission="definite_failure", failure=("a", "provider", True))
        c.add("attempt_failed", attempt=1, submission="definite_failure", failure=("b", "timeout", True))
        state = reconstruct_run_state(c.records)
        self.assertEqual([f.code for f in state.failures], ["a", "b"])

    def test_a_cancelled_run_is_terminal_and_keeps_its_failure(self):
        c = Chain()
        c.add("proposed").add("previewed").add("admitted")
        c.add("cancelled", failure=("operator_cancelled", "cancelled", False))
        state = reconstruct_run_state(c.records)
        self.assertTrue(state.terminal)
        self.assertEqual(state.failures[0].classification, "cancelled")

    def test_an_ambiguous_submission_is_a_reconciliation_hazard(self):
        c = Chain()
        c.add("proposed").add("previewed").add("admitted")
        c.add("dispatched", attempt=1, submission="ambiguous")
        state = reconstruct_run_state(c.records)
        self.assertTrue(state.needs_reconciliation)
        self.assertEqual(state.ambiguous_attempts, ("attempt-1",))

    def test_the_hazard_clears_once_a_later_record_resolves_it(self):
        c = Chain()
        c.add("proposed").add("previewed").add("admitted")
        c.add("dispatched", attempt=1, submission="ambiguous")
        c.add("dispatched", attempt=1, submission="submitted", run="r9")
        state = reconstruct_run_state(c.records)
        self.assertFalse(state.needs_reconciliation)
        self.assertEqual(state.attempts[0].external_run_id, "r9")


class InconsistentHistoryTests(unittest.TestCase):
    def assert_refused(self, chain, reason):
        with self.assertRaises(RecoveryError) as caught:
            reconstruct_run_state(chain.records)
        self.assertEqual(caught.exception.reason, reason)
        self.assertEqual(caught.exception.code, "recovery_inconsistent")

    def test_a_skipped_state_is_refused(self):
        self.assert_refused(Chain().add("proposed").add("dispatched", attempt=1), "illegal_transition")

    def test_nothing_follows_a_terminal_state(self):
        c = Chain().add("proposed").add("cancelled").add("previewed")
        self.assert_refused(c, "illegal_transition")

    def test_attempt_numbers_cannot_go_backwards(self):
        c = Chain().add("proposed").add("previewed").add("admitted")
        c.add("dispatched", attempt=2, submission="submitted")
        c.add("attempt_failed", attempt=1, submission="definite_failure")
        self.assert_refused(c, "attempt_number_regressed")

    def test_an_attempt_id_cannot_change_its_number(self):
        c = Chain().add("proposed").add("previewed").add("admitted")
        c.add("dispatched", attempt=1, submission="submitted")
        c.records[-1]["attempt"]["attempt_id"] = "attempt-9"
        c.add("attempt_failed", attempt=1, submission="definite_failure")
        c.records[-1]["attempt"]["attempt_id"] = "attempt-9"
        c.records[-1]["attempt"]["attempt_number"] = 2
        c.records[-1]["idempotency"]["attempt_number"] = 2
        self.assert_refused(c, "attempt_identity_changed")

    def test_a_recorded_human_decision_cannot_be_reverted_or_replaced(self):
        base = Chain()
        base.add("proposed").add("previewed").add("admitted")
        base.add("dispatched", attempt=1, submission="submitted").add("candidate_observed", attempt=1, candidate="1")
        base.add("normalized", attempt=1, manifest="2").add("verification_requested", attempt=1)
        base.add("evidence_ready", attempt=1, verification=("3",))
        base.add("awaiting_human_decision", attempt=1, human=("recorded", "4"))
        reverted = copy.deepcopy(base)
        reverted.add("awaiting_human_decision", attempt=1, human=("pending", None))
        self.assert_refused(reverted, "human_decision_changed")
        replaced = copy.deepcopy(base)
        replaced.add("awaiting_human_decision", attempt=1, human=("recorded", "5"))
        self.assert_refused(replaced, "human_decision_changed")

    def test_a_pending_decision_must_not_carry_a_record(self):
        c = Chain().add("proposed")
        c.records[0]["human_decision"] = {
            "state": "pending",
            "record": {"kind": "human_decision_record", "digest": D("4"), "storage_path": None},
        }
        self.assert_refused(c, "human_decision_inconsistent")

    def test_a_broken_chain_is_refused_before_any_replay(self):
        c = Chain().add("proposed").add("previewed")
        c.records[1]["previous_record_digest"] = D("0")
        with self.assertRaises(GitHubLedgerSerializationError):
            reconstruct_run_state(c.records)

    def test_an_empty_chain_is_refused(self):
        with self.assertRaises((GitHubLedgerSerializationError, IndexError)):
            reconstruct_run_state([])


@unittest.skipUnless(GIT, "git is required")
class RealLedgerTests(unittest.TestCase):
    def test_a_run_is_recovered_from_a_git_ledger_after_a_restart(self):
        with tempfile.TemporaryDirectory(prefix="idkmesh-recovery-") as tmp:
            repo = Path(tmp) / "ledger.git"
            subprocess.run([GIT, "init", "-q", "--bare", "--template=", str(repo)], check=True)
            ref = ledger_ref_for_run("run-recovery")

            def ledger():  # a fresh object each time: nothing but the repository survives
                return GitLedger(repo, ref, author_name="IDKMesh ledger", author_email="l@idkmesh.invalid")

            self.assertIsNone(recover_run(ledger()))
            head = ledger().head()
            for record in happy_chain()[:6]:
                head = ledger().append(record, expected=head)
            mid = recover_run(ledger())
            self.assertEqual((mid.state, mid.last_sequence), ("normalized", 6))
            for record in happy_chain()[6:]:
                head = ledger().append(record, expected=head)
            end = recover_run(ledger())
            self.assertEqual((end.state, end.terminal, end.last_sequence), ("decided", True, 10))
            self.assertEqual(end.head_digest, head.record_digest)


if __name__ == "__main__":
    unittest.main()
