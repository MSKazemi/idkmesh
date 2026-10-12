"""C9-F: kill the coordinating workflow at every step; recovery finishes safely.

Issue #597's acceptance: "kill/fail the coordinating workflow after dispatch -> a
later recovery workflow reconstructs the run and continues observation safely".
This proves it exhaustively. A small coordinator drives one run from proposal to a
recorded human decision through a ledger and a fake provider, writing the *intent*
to dispatch before it contacts the provider. The test kills it at every
side-effect point (before and after each ledger append and provider call), starts
a brand-new coordinator that has only the ledger and the provider to go on, and
requires the run to finish with exactly one provider submission and a valid
chain. Double kills are covered for a sample. One real-Git pass runs in the slow
tier.

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from idkmesh.github_ledger_append import (
    EMPTY_HEAD,
    AppendResult,
    GitLedger,
    LedgerConflict,
    LedgerHead,
    LedgerSnapshot,
    ledger_ref_for_run,
)
from idkmesh.github_ledger_recovery import recover_run, reconstruct_run_state
from idkmesh.github_ledger_recovery_plan import ACTIONS, plan_recovery
from idkmesh.github_ledger_serialization import (
    serialize_github_ledger_chain,
    serialize_github_ledger_record,
)

if importlib.util.find_spec("pytest") is not None:
    import pytest

    slow = pytest.mark.slow
else:  # pragma: no cover - exercised only where pytest is absent

    def slow(obj):
        return obj


def _sibling(name):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_sibling_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


Chain = _sibling("test_github_ledger_recovery").Chain
GIT = shutil.which("git")


class Killed(Exception):
    """The coordinating workflow died here."""


class Killer:
    def __init__(self, at=None):
        self.at, self.count = at, 0

    def point(self, name):
        self.count += 1
        if self.at is not None and self.count == self.at:
            raise Killed(name)


class MemoryLedger:
    """The ledger interface the coordinator needs, with real chain verification.

    Every append verifies the whole chain, as the Git ledger does; reads reuse the
    head computed at append time so the harness stays cheap.
    """

    def __init__(self):
        self._records = []
        self._head = EMPTY_HEAD

    def snapshot(self):
        return LedgerSnapshot(self._head, tuple(self._records))

    def read_records(self):
        return tuple(self._records)

    def append_with_retry(self, build, *, max_attempts=4):
        snap = self.snapshot()
        record = build(snap.head, snap.records)
        if record is None:
            return AppendResult(False, snap.head, 1)
        last = serialize_github_ledger_chain([*snap.records, record])[-1]  # must extend the chain
        self._records.append(record)
        self._head = LedgerHead(f"c{len(self._records)}", last.sequence, last.record_digest)
        return AppendResult(True, self._head, 1)


class Provider:
    """Idempotent by dispatch key on lookup; counts every submit call."""

    def __init__(self):
        self.jobs, self.submit_calls = {}, 0

    def lookup(self, key):
        return self.jobs.get(key)

    def submit(self, key):
        self.submit_calls += 1
        return self.jobs.setdefault(key, f"job-{len(self.jobs) + 1}")


def _append(ledger, killer, label, **fields):
    def build(_head, records):
        chain = Chain()
        chain.records = list(records)
        return chain.add(**fields).records[-1]

    killer.point(f"before:{label}")
    result = ledger.append_with_retry(build)
    killer.point(f"after:{label}")
    return result


def coordinate(ledger, provider, killer):
    """Drive the run to a recorded human decision; safe to restart anywhere."""

    for _ in range(40):
        state = recover_run(ledger)
        if state is None:
            _append(ledger, killer, "proposed", state="proposed")
            continue
        plan = plan_recovery(state)
        key = state.dispatch_key
        action = plan.action
        last = state.attempts[-1].attempt_number if state.attempts else 0
        n = last + 1 if action in ("dispatch", "retry_attempt") else last
        if action == "none":
            return state
        if action == "preview":
            _append(ledger, killer, action, state="previewed")
        elif action == "admit":
            _append(ledger, killer, action, state="admitted")
        elif action == "dispatch":
            _append(ledger, killer, "dispatch-intent", state="dispatched", attempt=n, submission="not_submitted")
        elif action == "reconcile_provider":
            job = provider.lookup(key)
            if job is None:  # the provider demonstrably has nothing: submit now
                killer.point("before:submit")
                job = provider.submit(key)
                killer.point("after:submit")
            _append(ledger, killer, "dispatch-confirmed", state="dispatched", attempt=n,
                    submission="submitted", run=job)
        elif action == "observe_provider":
            if provider.lookup(key) is not None:
                _append(ledger, killer, action, state="candidate_observed", attempt=n,
                        submission="submitted", candidate="1")
        elif action == "normalize":
            _append(ledger, killer, action, state="normalized", attempt=n, manifest="2")
        elif action == "request_verification":
            _append(ledger, killer, action, state="verification_requested", attempt=n)
        elif action == "observe_verification":
            _append(ledger, killer, action, state="evidence_ready", attempt=n, verification=("3",))
        elif action == "request_human_decision":
            _append(ledger, killer, action, state="awaiting_human_decision", attempt=n,
                    human=("pending", None))
        elif action == "await_human_decision":  # the human decides
            _append(ledger, killer, action, state="decided", attempt=n, human=("recorded", "4"))
        else:  # pragma: no cover - a plan this coordinator cannot act on
            raise AssertionError(f"unhandled action {action}")
    raise AssertionError("coordinator did not converge")


def clean_run():
    ledger, provider, killer = MemoryLedger(), Provider(), Killer()
    coordinate(ledger, provider, killer)
    return killer.count


class KillMatrixTests(unittest.TestCase):
    def assert_finished_safely(self, ledger, provider):
        state = reconstruct_run_state(ledger.read_records())
        self.assertEqual(state.state, "decided")
        self.assertTrue(state.terminal)
        self.assertEqual(state.human_decision_state, "recorded")
        self.assertEqual(provider.submit_calls, 1, "the work reached the provider exactly once")
        self.assertEqual(len(state.attempts), 1)
        self.assertEqual(state.failures, ())
        self.assertFalse(state.needs_reconciliation)
        ids = [r["event"]["event_id"] for r in ledger.read_records()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_a_clean_run_reaches_a_recorded_decision_with_one_submission(self):
        ledger, provider = MemoryLedger(), Provider()
        coordinate(ledger, provider, Killer())
        self.assert_finished_safely(ledger, provider)

    def test_killed_at_every_side_effect_point_recovery_finishes_exactly_once(self):
        points = clean_run()
        self.assertGreater(points, 15)
        for kill_at in range(1, points + 1):
            with self.subTest(kill_at=kill_at):
                ledger, provider = MemoryLedger(), Provider()
                with self.assertRaises(Killed):
                    coordinate(ledger, provider, Killer(kill_at))
                coordinate(ledger, provider, Killer())  # a brand-new coordinator
                self.assert_finished_safely(ledger, provider)

    def double_kill(self, firsts, seconds):
        points = clean_run()
        for first in firsts(points):
            for second in seconds:
                with self.subTest(first=first, second=second):
                    ledger, provider = MemoryLedger(), Provider()
                    with self.assertRaises(Killed):
                        coordinate(ledger, provider, Killer(first))
                    try:
                        coordinate(ledger, provider, Killer(second))
                    except Killed:
                        pass
                    coordinate(ledger, provider, Killer())
                    self.assert_finished_safely(ledger, provider)

    def test_recovery_that_is_itself_killed_still_finishes_exactly_once(self):
        # A sample per PR: kills spread over the whole run, second kill early.
        self.double_kill(lambda points: range(2, points + 1, 4), (1, 4))

    @slow
    def test_every_pair_of_kills_still_finishes_exactly_once(self):
        self.double_kill(lambda points: range(1, points + 1), (1, 2, 3, 5, 8))

    def test_a_finished_run_is_left_alone_by_further_recovery(self):
        ledger, provider = MemoryLedger(), Provider()
        coordinate(ledger, provider, Killer())
        before = list(ledger.read_records())
        coordinate(ledger, provider, Killer())
        self.assertEqual(ledger.read_records(), tuple(before))

    def test_a_crash_between_intent_and_submit_is_found_by_lookup_not_resubmitted(self):
        ledger, provider = MemoryLedger(), Provider()
        # Kill right after the dispatch intent is recorded, before the provider call.
        probe = Killer()
        coordinate(MemoryLedger(), Provider(), probe)
        # Find the kill point that follows "after:dispatch-intent".
        names = []

        class Recording(Killer):
            def point(self, name):
                names.append(name)
                super().point(name)

        coordinate(MemoryLedger(), Provider(), Recording())
        at = names.index("after:dispatch-intent") + 1
        with self.assertRaises(Killed):
            coordinate(ledger, provider, Killer(at))
        self.assertEqual(provider.submit_calls, 0)
        state = recover_run(ledger)
        self.assertEqual(plan_recovery(state).action, "reconcile_provider")
        coordinate(ledger, provider, Killer())
        self.assert_finished_safely(ledger, provider)

    def test_a_crash_after_submit_is_adopted_not_resubmitted(self):
        ledger, provider = MemoryLedger(), Provider()
        names = []

        class Recording(Killer):
            def point(self, name):
                names.append(name)
                super().point(name)

        coordinate(MemoryLedger(), Provider(), Recording())
        at = names.index("after:submit") + 1
        with self.assertRaises(Killed):
            coordinate(ledger, provider, Killer(at))
        self.assertEqual(provider.submit_calls, 1)  # the work went out, the ledger does not know
        coordinate(ledger, provider, Killer())
        self.assert_finished_safely(ledger, provider)  # still exactly one submission


class PlannerTests(unittest.TestCase):
    def plan_for(self, build):
        chain = Chain()
        build(chain)
        return plan_recovery(reconstruct_run_state(chain.records))

    def test_every_lifecycle_state_has_a_known_plan(self):
        def to(*states):
            def build(chain):
                for s in states:
                    chain.add(s)
            return build

        for states, action in (
            (("proposed",), "preview"),
            (("proposed", "previewed"), "admit"),
            (("proposed", "previewed", "admission_blocked"), "none"),
            (("proposed", "previewed", "admitted"), "dispatch"),
            (("proposed", "cancelled"), "none"),
        ):
            with self.subTest(states=states):
                plan = self.plan_for(to(*states))
                self.assertEqual(plan.action, action)
                self.assertIn(plan.action, ACTIONS)

    def test_dispatch_requires_the_dispatch_gate_and_grants_nothing(self):
        plan = self.plan_for(lambda c: [c.add("proposed"), c.add("previewed"), c.add("admitted")])
        self.assertEqual((plan.action, plan.authority_required), ("dispatch", "dispatch"))
        self.assertFalse(plan.blind_resubmission_forbidden)

    def test_an_unconfirmed_dispatch_is_reconciled_never_resubmitted_blindly(self):
        for submission in ("not_submitted", "ambiguous"):
            with self.subTest(submission=submission):
                def build(c, submission=submission):
                    c.add("proposed").add("previewed").add("admitted")
                    c.add("dispatched", attempt=1, submission=submission)
                plan = self.plan_for(build)
                self.assertEqual(plan.action, "reconcile_provider")
                self.assertTrue(plan.blind_resubmission_forbidden)

    def test_a_confirmed_submission_is_observed(self):
        def build(c):
            c.add("proposed").add("previewed").add("admitted")
            c.add("dispatched", attempt=1, submission="submitted", run="r1")
        plan = self.plan_for(build)
        self.assertEqual(plan.action, "observe_provider")
        self.assertTrue(plan.blind_resubmission_forbidden)

    def test_failed_attempts_retry_only_when_retryable(self):
        for retryable, action in ((True, "retry_attempt"), (False, "await_operator")):
            with self.subTest(retryable=retryable):
                def build(c, retryable=retryable):
                    c.add("proposed").add("previewed").add("admitted")
                    c.add("dispatched", attempt=1, submission="submitted")
                    c.add("attempt_failed", attempt=1, submission="definite_failure",
                          failure=("boom", "provider", retryable))
                plan = self.plan_for(build)
                self.assertEqual(plan.action, action)
                self.assertFalse(plan.blind_resubmission_forbidden)

    def test_a_decided_run_needs_nothing(self):
        state = reconstruct_run_state(_sibling("test_github_ledger_recovery").happy_chain())
        self.assertEqual(plan_recovery(state).action, "none")


@unittest.skipUnless(GIT, "git is required")
class RealGitKilledWorkflowTests(unittest.TestCase):
    @slow
    def test_the_same_guarantee_holds_on_a_real_git_ledger(self):
        points = clean_run()
        for kill_at in (3, points // 2, points - 2):
            with self.subTest(kill_at=kill_at), tempfile.TemporaryDirectory(prefix="idkmesh-kill-") as tmp:
                repo = Path(tmp) / "ledger.git"
                subprocess.run([GIT, "init", "-q", "--bare", "--template=", str(repo)], check=True)
                provider = Provider()

                def ledger():
                    return GitLedger(repo, ledger_ref_for_run("run-kill"),
                                     author_name="IDKMesh ledger", author_email="l@idkmesh.invalid")

                with self.assertRaises(Killed):
                    coordinate(ledger(), provider, Killer(kill_at))
                coordinate(ledger(), provider, Killer())
                state = recover_run(ledger())
                self.assertEqual((state.state, provider.submit_calls), ("decided", 1))
                serialize_github_ledger_record(ledger().read_records()[-1])


if __name__ == "__main__":
    unittest.main()
