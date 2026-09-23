import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.github_atomic_commit import (
    AtomicCommitError,
    build_plan,
    publish_atomic_commit,
)


HEAD = "1" * 40
TREE = "2" * 40
NEW_TREE = "3" * 40
COMMIT = "4" * 40


class FakeGitDataAPI:
    def __init__(self, heads=None, fail_at=None):
        self.heads = list(heads or [HEAD, HEAD])
        self.fail_at = fail_at
        self.calls = []

    def _record(self, name, *args):
        self.calls.append((name, *args))
        if self.fail_at == name:
            raise AtomicCommitError(f"synthetic {name} failure")

    def get_ref(self, branch):
        self._record("get_ref", branch)
        return self.heads.pop(0)

    def get_commit_tree(self, sha):
        self._record("get_commit_tree", sha)
        return TREE

    def create_blob(self, content):
        self._record("create_blob", content)
        return hashlib.sha1(content.encode()).hexdigest()

    def create_tree(self, base_tree, entries):
        self._record("create_tree", base_tree, entries)
        return NEW_TREE

    def create_commit(self, message, tree_sha, parent_sha):
        self._record("create_commit", message, tree_sha, parent_sha)
        return COMMIT

    def update_ref(self, branch, sha):
        self._record("update_ref", branch, sha)


class AtomicGitHubCommitTests(unittest.TestCase):
    def test_plan_is_deterministic_secret_free_and_sorted(self):
        first = build_plan(
            branch="agent/work",
            expected_head=HEAD,
            writes={"z.txt": "z", "a.txt": "a secret-ish content"},
            deletes=["old/z.txt", "old/a.txt"],
        )
        second = build_plan(
            branch="agent/work",
            expected_head=HEAD,
            writes={"a.txt": "a secret-ish content", "z.txt": "z"},
            deletes=["old/a.txt", "old/z.txt"],
        )
        self.assertEqual(first, second)
        self.assertEqual([row["path"] for row in first["writes"]], ["a.txt", "z.txt"])
        rendered = json.dumps(first, sort_keys=True)
        self.assertNotIn("secret-ish content", rendered)
        self.assertEqual(first["publication_commits"], 1)
        self.assertFalse(first["force_ref_update"])

    def test_many_changes_publish_as_one_tree_commit_and_ref_update(self):
        api = FakeGitDataAPI()
        result = publish_atomic_commit(
            api,
            branch="agent/work",
            expected_head=HEAD,
            message="agent: one batch",
            writes={"b.txt": "B", "a.txt": "A"},
            deletes=["old.txt"],
        )
        self.assertEqual(result["commit_sha"], COMMIT)
        names = [call[0] for call in api.calls]
        self.assertEqual(names.count("create_tree"), 1)
        self.assertEqual(names.count("create_commit"), 1)
        self.assertEqual(names.count("update_ref"), 1)
        tree_call = next(call for call in api.calls if call[0] == "create_tree")
        entries = tree_call[2]
        self.assertEqual([entry["path"] for entry in entries], ["a.txt", "b.txt", "old.txt"])
        self.assertIsNone(entries[-1]["sha"])

    def test_branch_mismatch_fails_before_any_mutation(self):
        moved = "9" * 40
        api = FakeGitDataAPI(heads=[moved])
        with self.assertRaisesRegex(AtomicCommitError, "changed before publication"):
            publish_atomic_commit(
                api,
                branch="agent/work",
                expected_head=HEAD,
                message="no",
                writes={"a.txt": "A"},
            )
        self.assertEqual(api.calls, [("get_ref", "agent/work")])

    def test_second_head_check_catches_race_before_ref_update(self):
        moved = "9" * 40
        api = FakeGitDataAPI(heads=[HEAD, moved])
        with self.assertRaisesRegex(AtomicCommitError, "changed before ref update"):
            publish_atomic_commit(
                api,
                branch="agent/work",
                expected_head=HEAD,
                message="no race overwrite",
                writes={"a.txt": "A"},
            )
        self.assertNotIn("update_ref", [call[0] for call in api.calls])

    def test_partial_object_creation_failure_never_moves_ref(self):
        api = FakeGitDataAPI(fail_at="create_tree")
        with self.assertRaisesRegex(AtomicCommitError, "synthetic create_tree failure"):
            publish_atomic_commit(
                api,
                branch="agent/work",
                expected_head=HEAD,
                message="partial",
                writes={"a.txt": "A", "b.txt": "B"},
            )
        self.assertNotIn("create_commit", [call[0] for call in api.calls])
        self.assertNotIn("update_ref", [call[0] for call in api.calls])

    def test_default_branch_is_refused_by_default(self):
        with self.assertRaisesRegex(AtomicCommitError, "refusing direct write"):
            build_plan(
                branch="main",
                expected_head=HEAD,
                writes={"a.txt": "A"},
            )

    def test_default_branch_requires_explicit_opt_in(self):
        plan = build_plan(
            branch="main",
            expected_head=HEAD,
            writes={"a.txt": "A"},
            allow_default_branch=True,
        )
        self.assertTrue(plan["allow_default_branch"])

    def test_write_delete_overlap_and_bad_paths_fail(self):
        with self.assertRaisesRegex(AtomicCommitError, "both written and deleted"):
            build_plan(
                branch="agent/work",
                expected_head=HEAD,
                writes={"a.txt": "A"},
                deletes=["a.txt"],
            )
        for path in ("/abs.txt", "../escape.txt", "a//b.txt", "a\\b.txt"):
            with self.subTest(path=path):
                with self.assertRaises(AtomicCommitError):
                    build_plan(
                        branch="agent/work",
                        expected_head=HEAD,
                        writes={path: "A"},
                    )

    def test_cli_plan_needs_no_token_and_performs_no_network(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "a.txt"
            local.write_text("hello", encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(root / "tools" / "github_atomic_commit.py"),
                    "plan",
                    "--branch",
                    "agent/work",
                    "--expected-head",
                    HEAD,
                    "--write",
                    f"a.txt={local}",
                    "--json",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                env={},
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["mutation_count"], 1)
        self.assertEqual(payload["writes"][0]["path"], "a.txt")

    def test_cli_publish_requires_token_without_echoing_any_value(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "a.txt"
            local.write_text("hello", encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(root / "tools" / "github_atomic_commit.py"),
                    "publish",
                    "--repository",
                    "owner/repo",
                    "--branch",
                    "agent/work",
                    "--expected-head",
                    HEAD,
                    "--message",
                    "test",
                    "--write",
                    f"a.txt={local}",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                env={},
            )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("GITHUB_TOKEN is required", proc.stderr)


if __name__ == "__main__":
    unittest.main()
