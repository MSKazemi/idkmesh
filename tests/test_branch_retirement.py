"""Offline negative controls for exact-SHA, superseded branch retirement."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import branch_retirement as retire  # noqa: E402

REPO = "MSKazemi/idkmesh"
HEAD = "a" * 40
MAIN = "b" * 40
MERGED = "c" * 40
OLD = retire.Candidate("agent/old-feature", HEAD, 101, 103)


class FakeClient:
    def __init__(self):
        self.calls = []
        self.overrides = {}

    def get(self, path):
        self.calls.append(path)
        if path in self.overrides:
            return self.overrides[path]
        if path.endswith("/branches/main"):
            return {"commit": {"sha": MAIN}, "protected": True}
        if path.endswith("/branches/agent%2Fold-feature"):
            return {"commit": {"sha": HEAD}, "protected": False}
        if "/pulls?" in path:
            return []
        if path.endswith("/pulls/101"):
            return {"state": "closed", "merged_at": None,
                    "head": {"ref": OLD.name, "sha": HEAD, "repo": {"full_name": REPO}}}
        if path.endswith("/pulls/103"):
            return {"state": "closed", "merged_at": "2026-10-13T00:00:00Z", "merge_commit_sha": MERGED}
        if path.endswith("/compare/" + MERGED + "...main"):
            return {"status": "ahead", "behind_by": 0}
        raise AssertionError(f"unexpected fetch: {path}")


class RetirementTests(unittest.TestCase):
    def test_manifest_rejects_duplicates_and_malformed_heads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            candidate = dict(name=OLD.name, head=HEAD, closed_pr=101, merged_replacement_pr=103)
            for candidates in (
                [candidate, candidate],
                [{**candidate, "head": "deadbeef"}],
                [{**candidate, "name": "main"}],
                [{**candidate, "name": "bad/../ref"}],
                [{**candidate, "closed_pr": True}],
                [{**candidate, "name": "-option"}],
            ):
                with self.subTest(candidates=candidates):
                    path.write_text(json.dumps({"repository": REPO, "default_branch": "main", "candidates": candidates}))
                    with self.assertRaises(retire.RetirementError):
                        retire.load_manifest(path)

    def test_dry_run_is_read_only_and_never_calls_git(self):
        api = FakeClient()
        with mock.patch.object(retire, "_git", side_effect=AssertionError("git must not be called")):
            result = retire.run(api, REPO, "main", (OLD,), execute=False, attestation=None, cwd=ROOT)
        self.assertEqual(result[0]["status"], "eligible_after_manual_evidence_review")
        self.assertTrue(any("/compare/" in url for url in api.calls))

    def test_branch_head_change_blocks_deletion(self):
        api = FakeClient()
        api.overrides["/repos/MSKazemi/idkmesh/branches/agent%2Fold-feature"] = {
            "commit": {"sha": "d" * 40}, "protected": False}
        with self.assertRaisesRegex(retire.RetirementError, "branch moved"):
            retire.verify(api, REPO, "main", OLD)

    def test_malformed_remote_responses_fail_closed(self):
        paths = (
            "/repos/MSKazemi/idkmesh/branches/agent%2Fold-feature",
            "/repos/MSKazemi/idkmesh/pulls/101",
            "/repos/MSKazemi/idkmesh/pulls/103",
            "/repos/MSKazemi/idkmesh/compare/" + MERGED + "...main",
        )
        for path in paths:
            with self.subTest(path=path):
                api = FakeClient()
                api.overrides[path] = ["not-an-object"]
                with self.assertRaises(retire.RetirementError):
                    retire.verify(api, REPO, "main", OLD)

    def test_protected_branch_blocks_deletion(self):
        api = FakeClient()
        api.overrides["/repos/MSKazemi/idkmesh/branches/agent%2Fold-feature"] = {
            "commit": {"sha": HEAD}, "protected": True}
        with self.assertRaisesRegex(retire.RetirementError, "protected"):
            retire.verify(api, REPO, "main", OLD)

    def test_open_pull_request_blocks_deletion(self):
        api = FakeClient()
        url = "/repos/MSKazemi/idkmesh/pulls?state=open&head=MSKazemi%3Aagent%2Fold-feature&per_page=100"
        api.overrides[url] = [{"number": 200}]
        with self.assertRaisesRegex(retire.RetirementError, "open PR"):
            retire.verify(api, REPO, "main", OLD)

    def test_reopened_original_pr_blocks_deletion(self):
        api = FakeClient()
        api.overrides["/repos/MSKazemi/idkmesh/pulls/101"] = {
            "state": "open", "merged_at": None,
            "head": {"ref": OLD.name, "sha": HEAD, "repo": {"full_name": REPO}}}
        with self.assertRaisesRegex(retire.RetirementError, "closed-PR evidence mismatch"):
            retire.verify(api, REPO, "main", OLD)

    def test_unmerged_replacement_blocks_deletion(self):
        api = FakeClient()
        api.overrides["/repos/MSKazemi/idkmesh/pulls/103"] = {
            "state": "open", "merged_at": None, "merge_commit_sha": MERGED}
        with self.assertRaisesRegex(retire.RetirementError, "no verified merged replacement"):
            retire.verify(api, REPO, "main", OLD)

    def test_replacement_not_ancestor_blocks_deletion(self):
        api = FakeClient()
        api.overrides["/repos/MSKazemi/idkmesh/compare/" + MERGED + "...main"] = {
            "status": "diverged", "behind_by": 2}
        with self.assertRaisesRegex(retire.RetirementError, "not in current main"):
            retire.verify(api, REPO, "main", OLD)

    def test_execute_requires_explicit_operator_attestation(self):
        with self.assertRaisesRegex(retire.RetirementError, "requires explicit"):
            retire.run(FakeClient(), REPO, "main", (OLD,), execute=True, attestation=None, cwd=ROOT)

    def test_execute_rechecks_then_uses_exact_lease_without_shell(self):
        api = FakeClient()
        calls = []
        def git(*args, cwd):
            calls.append(args)
            return ""
        with mock.patch.object(retire, "verify_local_checkout") as checkout, mock.patch.object(retire, "_git", side_effect=git):
            result = retire.run(api, REPO, "main", (OLD,), execute=True, attestation=retire.ACK, cwd=ROOT)
        self.assertEqual(checkout.call_count, 2)
        checkout.assert_any_call(REPO, MAIN, ROOT)
        self.assertEqual(result[0]["status"], "retired")
        self.assertEqual(calls, [("push", "--porcelain", f"--force-with-lease=refs/heads/{OLD.name}:{HEAD}",
                                  "origin", f":refs/heads/{OLD.name}")])
        self.assertEqual(sum("/branches/agent%2Fold-feature" in url for url in api.calls), 2)

    def test_main_move_between_checks_blocks_execution(self):
        api = FakeClient()
        original_get = api.get
        n = [0]
        def moving(path):
            if path.endswith("/branches/main"):
                n[0] += 1
                if n[0] > 1:
                    return {"commit": {"sha": "f" * 40}}
            return original_get(path)
        api.get = moving
        with mock.patch.object(retire, "verify_local_checkout"), mock.patch.object(retire, "_git") as git:
            with self.assertRaisesRegex(retire.RetirementError, "main moved"):
                retire.run(api, REPO, "main", (OLD,), execute=True, attestation=retire.ACK, cwd=ROOT)
        git.assert_not_called()

    def test_bad_git_remote_or_checkout_is_rejected(self):
        with mock.patch.object(retire, "_git", side_effect=["https://evil.example/x.git"]):
            with self.assertRaisesRegex(retire.RetirementError, "origin"):
                retire.verify_local_checkout(REPO, MAIN, ROOT)
        with mock.patch.object(retire, "_git", side_effect=[
            f"https://github.com/{REPO}.git",
            f"https://github.com/{REPO}.git",
            "false",
            "feature",
        ]):
            with self.assertRaisesRegex(retire.RetirementError, "checkout must be on main"):
                retire.verify_local_checkout(REPO, MAIN, ROOT)

    def test_origin_fetch_url_cannot_override_a_different_push_destination(self):
        """A clean-looking fetch remote must not authorize a malicious pushurl."""
        fetch_url = f"https://github.com/{REPO}.git"
        for target in ("https://github.com/other/repository.git", "ssh://git@evil.example/x.git"):
            with self.subTest(push_target=target):
                with mock.patch.object(retire, "_git", side_effect=[fetch_url, target]) as git:
                    with self.assertRaisesRegex(retire.RetirementError, "Git push destinations"):
                        retire.verify_local_checkout(REPO, MAIN, ROOT)
                self.assertEqual(git.call_count, 2)

    def test_multiple_origin_push_destinations_are_denied(self):
        """A single push can otherwise affect more than the approved repository."""
        approved = f"https://github.com/{REPO}.git"
        for resolved in ("", approved + "\n" + approved):
            with self.subTest(resolved=resolved):
                with mock.patch.object(retire, "_git", side_effect=[approved, resolved]) as git:
                    with self.assertRaisesRegex(retire.RetirementError, "Git push destinations"):
                        retire.verify_local_checkout(REPO, MAIN, ROOT)
                self.assertEqual(git.call_count, 2)

    def test_one_approved_effective_push_destination_reaches_remaining_checks(self):
        fetch_url = f"https://github.com/{REPO}.git"
        push_url = f"git@github.com:{REPO}.git"
        with mock.patch.object(retire, "_git", side_effect=[
            fetch_url, push_url, "false", "main", MAIN, "",
        ]) as git:
            retire.verify_local_checkout(REPO, MAIN, ROOT)
        self.assertEqual(git.call_count, 5)


    def test_origin_push_mirror_is_denied_even_with_approved_url(self):
        """An explicit mirror mode must never reach a deletion push."""
        approved = f"https://github.com/{REPO}.git"
        with mock.patch.object(retire, "_git", side_effect=[
            approved, approved, "true",
        ]) as git:
            with self.assertRaisesRegex(retire.RetirementError, "push mirror"):
                retire.verify_local_checkout(REPO, MAIN, ROOT)
        self.assertEqual(git.call_count, 3)

    def test_execute_rechecks_checkout_and_push_url_before_each_delete(self):
        """A pushurl changed after the first preflight must block the push."""
        api = FakeClient()
        with mock.patch.object(
            retire, "verify_local_checkout",
            side_effect=[None, retire.RetirementError("push destination moved")],
        ) as checkout, mock.patch.object(retire, "_git") as git:
            with self.assertRaisesRegex(retire.RetirementError, "push destination moved"):
                retire.run(api, REPO, "main", (OLD,), execute=True,
                           attestation=retire.ACK, cwd=ROOT)
        self.assertEqual(checkout.call_count, 2)
        git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
