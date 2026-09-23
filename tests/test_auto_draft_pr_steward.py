from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tools import auto_draft_pr_steward as steward

ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    repo = "MSKazemi/idkmesh"

    def __init__(
        self,
        branches,
        pulls,
        commits,
        comparisons,
        *,
        remaining=5000,
        current_heads=None,
    ):
        self.branches = branches
        self.pulls = pulls
        self.commits = commits
        self.comparisons = comparisons
        self.compare_calls = []
        self.remaining = remaining
        self.current_heads = current_heads or {
            item["name"]: item["commit"]["sha"] for item in branches
        }
        self.created = []

    def rate_limit_remaining(self):
        return self.remaining

    def list_branches(self, max_pages):
        return self.branches

    def list_pulls(self, max_pages):
        return self.pulls

    def get_commit(self, sha):
        return self.commits[sha]

    def get_branch_head(self, name):
        return self.current_heads.get(name, "")

    def compare(self, base, head):
        self.compare_calls.append((base, head))
        return self.comparisons[(base, head)]

    def create_draft_pr(self, **kwargs):
        self.created.append(kwargs)
        number = 700 + len(self.created)
        return {
            "number": number,
            "html_url": f"https://github.com/MSKazemi/idkmesh/pull/{number}",
            "draft": True,
        }


def policy(**overrides):
    values = dict(
        enabled=True,
        not_before=datetime(2026, 9, 22, 14, 24, tzinfo=timezone.utc),
        default_base="main",
        managed_prefixes=("feat/", "docs/", "connector/"),
        excluded_prefixes=("scratch/",),
        infer_stacked_base=True,
        max_creations_per_run=3,
        max_branch_pages=5,
        max_pr_pages=20,
        max_untracked_branches_per_run=50,
        max_candidate_evaluations_per_run=6,
        max_open_pr_heads_for_stack_inference=50,
        minimum_rate_limit_remaining=1500,
    )
    values.update(overrides)
    return steward.Policy(**values)


def branch(name, sha):
    return {"name": name, "commit": {"sha": sha}}


def commit(when):
    return {"commit": {"committer": {"date": when}}}


def pr(head, state="open", repo="MSKazemi/idkmesh"):
    return {"state": state, "head": {"ref": head, "repo": {"full_name": repo}}}


class AutoDraftPrTests(unittest.TestCase):
    def _report_policy_file(self, directory: str) -> Path:
        path = Path(directory) / "policy.json"
        path.write_text('{"schema_version":"0.1"}\n', encoding="utf-8")
        return path

    def _report_result(self):
        head = "a" * 40
        return {
            "schema_version": "0.1",
            "candidate_count": 1,
            "planned": [
                {
                    "branch": "feat/report",
                    "base": "main",
                    "head_sha": head,
                    "ahead_by": 2,
                    "behind_by": 0,
                }
            ],
            "created": [
                {
                    "branch": "feat/report",
                    "base": "main",
                    "head_sha": head,
                    "ahead_by": 2,
                    "behind_by": 0,
                    "number": 701,
                    "url": "https://github.com/MSKazemi/idkmesh/pull/701",
                }
            ],
            "skipped": [],
            "dry_run": False,
            "rate_limit_remaining": 4321,
            "blocked_reason": None,
            "merge_authorized": False,
        }

    def test_report_binds_policy_and_trusted_workflow_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = self._report_policy_file(tmp)
            report = steward.build_report(
                self._report_result(),
                repo="MSKazemi/idkmesh",
                policy_path=policy_path,
                generated_at="2026-09-22T16:00:00Z",
                env={
                    "GITHUB_WORKFLOW": "Auto Draft PR Steward",
                    "GITHUB_RUN_ID": "12345",
                    "GITHUB_RUN_ATTEMPT": "2",
                    "GITHUB_SHA": "b" * 40,
                },
            )
            expected = hashlib.sha256(policy_path.read_bytes()).hexdigest()
        self.assertEqual(report["schema"], steward.REPORT_SCHEMA)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["policy"]["sha256"], expected)
        self.assertEqual(report["provenance"]["run_id"], "12345")
        self.assertEqual(report["provenance"]["trusted_head_sha"], "b" * 40)
        self.assertEqual(report["summary"], {"planned": 1, "created": 1, "skipped": 0})
        self.assertFalse(report["authority"]["merge"])
        self.assertTrue(report["authority"]["draft_pr_create"])

    def test_report_represents_disabled_and_low_budget_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = self._report_policy_file(tmp)
            disabled = steward.build_report(
                steward.disabled_result(False),
                repo="MSKazemi/idkmesh",
                policy_path=policy_path,
                generated_at="2026-09-22T16:00:00Z",
                env={},
            )
            blocked = steward.build_report(
                steward.blocked_result(1000, 1500, False),
                repo="MSKazemi/idkmesh",
                policy_path=policy_path,
                generated_at="2026-09-22T16:00:00Z",
                env={},
            )
        self.assertEqual(disabled["status"], "disabled")
        self.assertIsNone(disabled["candidate_count"])
        self.assertEqual(disabled["blocked_reason"], "policy_disabled")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("github_api_budget_low", blocked["blocked_reason"])

    @unittest.skipUnless(
        importlib.util.find_spec("jsonschema") is not None,
        "report instance validation requires jsonschema",
    )
    def test_report_validates_against_published_schema(self):
        from jsonschema import Draft202012Validator

        with tempfile.TemporaryDirectory() as tmp:
            policy_path = self._report_policy_file(tmp)
            report = steward.build_report(
                self._report_result(),
                repo="MSKazemi/idkmesh",
                policy_path=policy_path,
                generated_at="2026-09-22T16:00:00Z",
                env={"GITHUB_SHA": "c" * 40},
            )
        schema = json.loads(
            (
                ROOT
                / "schemas"
                / "auto-draft-pr-steward-report-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(report)

    def test_report_markdown_surfaces_created_and_skipped_work(self):
        result = self._report_result()
        result["created"] = []
        result["skipped"] = [
            {
                "branch": "feat/report",
                "base": "main",
                "head_sha": "a" * 40,
                "ahead_by": 2,
                "behind_by": 0,
                "reason": "head_moved",
                "current_head_sha": "d" * 40,
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = steward.build_report(
                result,
                repo="MSKazemi/idkmesh",
                policy_path=self._report_policy_file(tmp),
                generated_at="2026-09-22T16:00:00Z",
                env={},
            )
        rendered = steward.render_report_markdown(report)
        self.assertIn("# Auto Draft PR Steward Report", rendered)
        self.assertIn("## Planned candidates", rendered)
        self.assertIn("## Skipped candidates", rendered)
        self.assertIn("head_moved", rendered)
        self.assertIn("Merge authorized: **false**", rendered)

    def test_markdown_report_escapes_untrusted_ref_text(self):
        result = self._report_result()
        result["planned"][0]["branch"] = "feat/x|y#123<em>"
        result["created"] = []
        with tempfile.TemporaryDirectory() as tmp:
            report = steward.build_report(
                result,
                repo="MSKazemi/idkmesh",
                policy_path=self._report_policy_file(tmp),
                generated_at="2026-09-22T16:00:00Z",
                env={},
            )
        rendered = steward.render_report_markdown(report)
        self.assertNotIn("feat/x|y#123<em>", rendered)
        self.assertNotIn("<em>", rendered)
        self.assertIn("&#124;", rendered)
        self.assertIn("&lt;em&gt;", rendered)

    def test_report_output_paths_cannot_overwrite_each_other_or_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = self._report_policy_file(tmp)
            same = Path(tmp) / "same.txt"
            with self.assertRaisesRegex(ValueError, "different paths"):
                steward._validate_output_paths(
                    policy_path, same, same, None
                )
            with self.assertRaisesRegex(ValueError, "policy file"):
                steward._validate_output_paths(
                    policy_path, policy_path, None, None
                )

    def test_workflow_publishes_bounded_evidence_artifact(self):
        workflow = (
            ROOT / ".github" / "workflows" / "auto-draft-pr.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("--output-json", workflow)
        self.assertIn("--output-md", workflow)
        self.assertIn("actions/upload-artifact@", workflow)
        self.assertIn("retention-days: 14", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("auto-draft-pr-steward-${{ github.run_id }}", workflow)
        self.assertNotIn("actions: write", workflow)

    def test_workflow_pins_trusted_main_and_least_privilege(self):
        workflow = (
            ROOT / ".github" / "workflows" / "auto-draft-pr.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("branches:\n      - main", workflow)
        self.assertIn("ref: main", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("pull-requests: write", workflow)
        self.assertNotIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("actions: write", workflow)
        self.assertNotIn("id-token: write", workflow)

    def test_github_client_create_payload_is_always_draft(self):
        class RecordingClient(steward.GitHubClient):
            def __init__(self):
                super().__init__("MSKazemi/idkmesh", "token")
                self.record = None

            def _request(self, method, path, payload=None):
                self.record = (method, path, payload)
                return {"number": 1, "html_url": "https://example/pr"}

        client = RecordingClient()
        client.create_draft_pr("title", "feat/head", "main", "body")
        method, path, payload = client.record
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/repos/MSKazemi/idkmesh/pulls")
        self.assertIs(payload["draft"], True)
        self.assertEqual(payload["head"], "feat/head")
        self.assertEqual(payload["base"], "main")

    def test_repository_policy_loads_and_stays_bounded(self):
        loaded = steward.load_policy(ROOT / "config" / "auto-draft-pr.json")
        self.assertTrue(loaded.enabled)
        self.assertEqual(loaded.default_base, "main")
        self.assertLessEqual(loaded.max_creations_per_run, 3)
        self.assertGreaterEqual(loaded.minimum_rate_limit_remaining, 1500)
        self.assertLessEqual(loaded.max_untracked_branches_per_run, 50)
        self.assertLessEqual(loaded.max_candidate_evaluations_per_run, 6)
        self.assertLessEqual(loaded.max_open_pr_heads_for_stack_inference, 50)
        self.assertIn("jules-", loaded.excluded_prefixes)
        self.assertIn("feat/", loaded.managed_prefixes)
        self.assertFalse(
            set(loaded.managed_prefixes) & set(loaded.excluded_prefixes)
        )

    def test_policy_rejects_overlapping_prefixes(self):
        import json
        import tempfile

        raw = {
            "schema_version": "0.1",
            "enabled": True,
            "not_before": "2026-09-22T15:25:00Z",
            "default_base": "main",
            "managed_prefixes": ["feat/"],
            "excluded_prefixes": ["feat/"],
            "infer_stacked_base": True,
            "max_creations_per_run": 1,
            "max_branch_pages": 1,
            "max_pr_pages": 1,
            "max_untracked_branches_per_run": 1,
            "max_candidate_evaluations_per_run": 1,
            "max_open_pr_heads_for_stack_inference": 1,
            "minimum_rate_limit_remaining": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not overlap"):
                steward.load_policy(path)

    def test_old_or_excluded_or_historical_branches_are_not_candidates(self):
        client = FakeClient(
            branches=[
                branch("main", "m"),
                branch("feat/old", "old"),
                branch("scratch/test", "scratch"),
                branch("docs/closed", "closed"),
            ],
            pulls=[pr("docs/closed", state="closed")],
            commits={"old": commit("2026-09-22T13:00:00Z")},
            comparisons={},
        )
        self.assertEqual(steward.discover_candidates(client, policy()), [])

    def test_new_independent_branch_gets_draft_against_main(self):
        client = FakeClient(
            branches=[branch("feat/new-control", "n")],
            pulls=[],
            commits={"n": commit("2026-09-22T15:00:00Z")},
            comparisons={
                ("main", "feat/new-control"): {
                    "status": "diverged",
                    "ahead_by": 2,
                    "behind_by": 1,
                }
            },
        )
        result = steward.run_steward(client, policy())
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(client.created[0]["base"], "main")
        self.assertTrue(client.created[0]["title"].startswith("feat:"))
        self.assertIsNone(result["blocked_reason"])

    def test_nearest_open_pr_ancestor_becomes_stack_base(self):
        client = FakeClient(
            branches=[branch("connector/c1h", "h")],
            pulls=[pr("connector/c1b"), pr("connector/c1d")],
            commits={"h": commit("2026-09-22T15:00:00Z")},
            comparisons={
                ("connector/c1b", "connector/c1h"): {
                    "status": "ahead",
                    "ahead_by": 4,
                    "behind_by": 0,
                },
                ("connector/c1d", "connector/c1h"): {
                    "status": "ahead",
                    "ahead_by": 1,
                    "behind_by": 0,
                },
            },
        )
        candidates = steward.discover_candidates(client, policy())
        self.assertEqual(candidates[0].base, "connector/c1d")

    def test_fork_pr_with_same_branch_name_does_not_count_as_history(self):
        client = FakeClient(
            branches=[branch("docs/new", "d")],
            pulls=[pr("docs/new", state="closed", repo="someone/fork")],
            commits={"d": commit("2026-09-22T15:00:00Z")},
            comparisons={
                ("main", "docs/new"): {
                    "status": "ahead",
                    "ahead_by": 1,
                    "behind_by": 0,
                }
            },
        )
        self.assertEqual(len(steward.discover_candidates(client, policy())), 1)

    def test_generated_pr_text_does_not_emit_issue_refs_from_branch_names(self):
        candidate = steward.Candidate(
            "fix/fixes-#632",
            "abc123",
            "feat/base-#12",
            "ahead",
            1,
            0,
        )
        self.assertNotIn("#632", steward.title_for(candidate.branch))
        body = steward.body_for(candidate)
        self.assertNotIn("#632", body)
        self.assertNotIn("#12", body)
        self.assertIn("issue-632", body)

    def test_generated_title_is_bounded(self):
        title = steward.title_for("feat/" + "long-name-" * 40)
        self.assertLessEqual(len(title), steward.MAX_PR_TITLE_LENGTH)
        self.assertTrue(title.endswith("..."))

    def test_created_pr_response_must_have_reportable_identity(self):
        class BadResponseClient(FakeClient):
            def create_draft_pr(self, **kwargs):
                return {"number": None, "html_url": "https://example.invalid/pr"}

        client = BadResponseClient(
            [branch("feat/bad-response", "a" * 40)],
            [],
            {"a" * 40: commit("2026-09-22T15:00:00Z")},
            {
                ("main", "feat/bad-response"): {
                    "status": "ahead",
                    "ahead_by": 1,
                    "behind_by": 0,
                }
            },
        )
        with self.assertRaisesRegex(RuntimeError, "valid PR number"):
            steward.run_steward(client, policy())

    def test_duplicate_creation_race_is_benign_and_visible(self):
        class RacingClient(FakeClient):
            def create_draft_pr(self, **kwargs):
                raise steward.GitHubApiError(
                    422,
                    "Validation Failed",
                    '{"errors":[{"message":"A pull request already exists"}]}',
                )

        client = RacingClient(
            [branch("feat/race", "r")],
            [],
            {"r": commit("2026-09-22T15:00:00Z")},
            {
                ("main", "feat/race"): {
                    "status": "ahead",
                    "ahead_by": 1,
                    "behind_by": 0,
                }
            },
        )
        result = steward.run_steward(client, policy())
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["created"], [])
        self.assertEqual(result["skipped"][0]["reason"], "pr_already_exists")

    def test_head_move_between_plan_and_create_is_skipped(self):
        client = FakeClient(
            [branch("feat/moving", "old")],
            [],
            {"old": commit("2026-09-22T15:00:00Z")},
            {
                ("main", "feat/moving"): {
                    "status": "ahead",
                    "ahead_by": 1,
                    "behind_by": 0,
                }
            },
            current_heads={"feat/moving": "new"},
        )
        result = steward.run_steward(client, policy())
        self.assertEqual(client.created, [])
        self.assertEqual(result["skipped"][0]["reason"], "head_moved")
        self.assertEqual(result["skipped"][0]["current_head_sha"], "new")

    def test_disabled_policy_makes_no_github_calls(self):
        class NoTouchClient:
            repo = "MSKazemi/idkmesh"

            def __getattr__(self, name):
                raise AssertionError(f"disabled policy touched GitHub via {name}")

        result = steward.run_steward(NoTouchClient(), policy(enabled=False))
        self.assertIsNone(result["candidate_count"])
        self.assertEqual(result["blocked_reason"], "policy_disabled")
        self.assertEqual(result["planned"], [])
        self.assertFalse(result["merge_authorized"])

    def test_low_api_budget_blocks_before_mutation(self):
        client = FakeClient([], [], {}, {}, remaining=1499)
        result = steward.run_steward(client, policy())
        self.assertIsNone(result["candidate_count"])
        self.assertEqual(result["created"], [])
        self.assertIn("github_api_budget_low", result["blocked_reason"])
        self.assertFalse(result["merge_authorized"])

    def test_untracked_branch_limit_fails_closed_before_commit_reads(self):
        branches = [branch("feat/a", "a"), branch("feat/b", "b")]
        client = FakeClient(branches, [], {}, {})
        with self.assertRaisesRegex(RuntimeError, "untracked managed branch count"):
            steward.discover_candidates(
                client, policy(max_untracked_branches_per_run=1)
            )

    def test_open_pr_head_limit_fails_closed_before_stack_inference(self):
        pulls = [pr(f"feat/open-{n}") for n in range(3)]
        client = FakeClient([], pulls, {}, {})
        with self.assertRaisesRegex(RuntimeError, "open PR head count"):
            steward.discover_candidates(
                client, policy(max_open_pr_heads_for_stack_inference=2)
            )

    def test_candidate_evaluation_limit_bounds_compare_calls(self):
        branches = [branch(f"feat/work-{n}", str(n)) for n in range(4)]
        commits = {
            str(n): commit(f"2026-09-22T15:0{n}:00Z") for n in range(4)
        }
        comparisons = {
            ("main", f"feat/work-{n}"): {
                "status": "ahead",
                "ahead_by": 1,
                "behind_by": 0,
            }
            for n in range(4)
        }
        client = FakeClient(branches, [], commits, comparisons)
        candidates = steward.discover_candidates(
            client, policy(max_candidate_evaluations_per_run=2)
        )
        self.assertEqual(len(candidates), 2)
        self.assertEqual(len(client.compare_calls), 2)

    def test_candidates_are_ordered_oldest_first_before_creation_cap(self):
        client = FakeClient(
            [branch("feat/newer", "n"), branch("feat/older", "o")],
            [],
            {
                "n": commit("2026-09-22T15:30:00Z"),
                "o": commit("2026-09-22T15:00:00Z"),
            },
            {
                ("main", "feat/newer"): {
                    "status": "ahead",
                    "ahead_by": 1,
                    "behind_by": 0,
                },
                ("main", "feat/older"): {
                    "status": "ahead",
                    "ahead_by": 1,
                    "behind_by": 0,
                },
            },
        )
        result = steward.run_steward(client, policy(max_creations_per_run=1))
        self.assertEqual(result["planned"][0]["branch"], "feat/older")
        self.assertEqual(client.created[0]["head"], "feat/older")

    def test_creation_limit_caps_mutations(self):
        branches = [branch(f"feat/work-{n}", str(n)) for n in range(4)]
        commits = {str(n): commit("2026-09-22T15:00:00Z") for n in range(4)}
        comparisons = {
            ("main", f"feat/work-{n}"): {
                "status": "ahead",
                "ahead_by": 1,
                "behind_by": 0,
            }
            for n in range(4)
        }
        client = FakeClient(branches, [], commits, comparisons)
        result = steward.run_steward(client, policy(max_creations_per_run=2))
        self.assertEqual(result["candidate_count"], 4)
        self.assertEqual(len(client.created), 2)
        self.assertFalse(result["merge_authorized"])


if __name__ == "__main__":
    unittest.main()
