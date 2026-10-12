"""Tests for the C8-E ``idkmesh github-workflow`` runner (#596).

The runner is the other half of the C8-D wrapper contract, so these tests
render the real wrappers through ``cli.main(["init", "--github", "--dry-run"])``
and drive the runner with exactly the environment each wrapper declares. No test
touches the network: GitHub is replaced by fixtures and in-memory fakes.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import types
import unittest
from unittest import mock

from idkmesh import cli
import idkmesh.github_workflow_runner as runner
from idkmesh.github_issue_preview import (
    GitHubIssueWorkPolicy,
    parse_github_issue_snapshot,
    preview_github_issue_work_unit,
)
from idkmesh.github_ledger_github_store import (
    DEFAULT_LEDGER_BRANCH,
    GitHubGitDataConflict,
    GitHubLedgerBranchStore,
    GitTreeEntry,
)
from idkmesh.github_ledger_serialization import serialize_github_ledger_record


ROOT = Path(__file__).resolve().parents[1]
LEDGER_FIXTURE = (
    ROOT / "tests" / "fixtures" / "github-ledger" / "00000000000000000001.json"
)
REF = "1" * 40
BASE_SHA = "2" * 40
REPOSITORY = "MSKazemi/idkmesh"
ISSUE_NUMBER = 77
SECRET_SENTINEL = "jules-secret-sentinel-4f1c"
TOKEN_SENTINEL = "ghs_token_sentinel_9d2e"
INJECTION_BODY = "Please fix it.\n::add-mask::abc\n::error::pwned\n::stop-commands::x"

# Sample values for the expressions the wrappers pass, by variable name.
SAMPLE_VALUES = {
    "IDKMESH_REPOSITORY": REPOSITORY,
    "IDKMESH_BASE_SHA": BASE_SHA,
    "IDKMESH_RUN_ID": "123456789",
    "IDKMESH_GITHUB_TOKEN": TOKEN_SENTINEL,
    "IDKMESH_ISSUE_NUMBER": str(ISSUE_NUMBER),
    "IDKMESH_RUN_REFERENCE": "github-ledger-fixture/run-001",
    "IDKMESH_WORK_UNIT_DIGEST": "sha256:" + "a" * 64,
    "IDKMESH_CONNECTOR_ID": "jules-main",
    "IDKMESH_CANDIDATE_SHA": "3" * 40,
    "JULES_API_KEY": SECRET_SENTINEL,
}


def _issue(**overrides) -> dict:
    value = {
        "id": 9001,
        "number": ISSUE_NUMBER,
        "title": "Add a bounded feature",
        "body": "Implement the requested behavior and add tests.",
        "state": "open",
        "locked": False,
        "user": {"login": "contributor", "id": 88},
        "author_association": "CONTRIBUTOR",
        "labels": [{"name": "idkmesh:preview"}],
        "html_url": f"https://github.com/{REPOSITORY}/issues/{ISSUE_NUMBER}",
        "updated_at": "2026-09-24T01:00:00Z",
    }
    value.update(overrides)
    return value


def _dry_run_json() -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(
            ["init", "--github", "--dry-run", "--idkmesh-ref", REF, "--json"]
        )
    assert code == 0
    return json.loads(out.getvalue())


def _wrapper_contract(content: str) -> tuple[str, tuple[str, ...]]:
    """The phase a wrapper runs and the env names its runner step passes."""

    phase = re.search(r"github-workflow (\w+)\n", content)
    assert phase, "wrapper has no runner command"
    step = content[content.index("- name: Run IDKMesh") :]
    env_block = step.split("        env:\n", 1)[1].split("        run:", 1)[0]
    names = re.findall(r"^          ([A-Z][A-Z0-9_]*):", env_block, re.MULTILINE)
    return phase.group(1), tuple(names)


class RecordingEnviron(dict):
    """An environment that remembers every key the runner looked at."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.accessed: set[str] = set()

    def get(self, key, default=None):
        self.accessed.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self.accessed.add(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        self.accessed.add(key)
        return super().__contains__(key)


class RunnerHarness(unittest.TestCase):
    """Shared fixtures: a rendered project tree and an environment builder."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.dry_run = _dry_run_json()
        cls.config = {
            item["path"]: item["content"]
            for item in cls.dry_run["rendered_config_files"]
        }
        cls.wrappers = {
            item["path"].rsplit("/", 1)[1]: item["content"]
            for item in cls.dry_run["rendered_workflow_files"]
        }

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.project = self.tmp / "project"

    def write_project(self, *, scoped: bool = True, mutate=None) -> Path:
        manifest = json.loads(self.config[".idkmesh/project.json"])
        if scoped:
            manifest["metadata"]["github_issue_preview"] = {
                "allowed_paths": ["idkmesh/**", "tests/**"],
                "forbidden_paths": ["SECURITY.md"],
            }
        if mutate is not None:
            mutate(manifest)
        target = self.project / ".idkmesh" / "project.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest), encoding="utf-8")
        return self.project

    def write_json(self, name: str, value) -> Path:
        path = self.tmp / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def wrapper_env(self, wrapper: str, **extra: str) -> dict[str, str]:
        """Environment built from the names the real wrapper declares."""

        _, names = _wrapper_contract(self.wrappers[wrapper])
        env = {}
        for name in names:
            if name == "IDKMESH_PROJECT_ROOT":
                env[name] = str(self.project)
            elif name == "IDKMESH_CANDIDATE_DIR":
                env[name] = str(self.tmp / "candidate")
            elif name == "IDKMESH_EVENT_PATH":
                continue
            else:
                env[name] = SAMPLE_VALUES[name]
        env.update(extra)
        return env

    def run_cli(self, environ: dict[str, str], *argv: str):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, environ, clear=True):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = cli.main(["github-workflow", *argv])
                except SystemExit as exc:
                    code = exc.code if isinstance(exc.code, int) else 1
        return types.SimpleNamespace(
            returncode=code, stdout=out.getvalue(), stderr=err.getvalue()
        )


class WrapperContractTests(RunnerHarness):
    """The runner accepts exactly the environment the wrappers declare."""

    def test_every_wrapper_runs_a_phase_the_cli_parses(self) -> None:
        phases = {
            _wrapper_contract(content)[0] for content in self.wrappers.values()
        }
        self.assertEqual(phases, set(runner.PHASES))
        for phase in phases:
            with self.subTest(phase=phase):
                args = cli.build_parser().parse_args(["github-workflow", phase])
                self.assertEqual(args.github_workflow_command, phase)

    def test_wrapper_probe_command_succeeds(self) -> None:
        # The wrappers' first runner step is `github-workflow --help`.
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as caught:
            cli.build_parser().parse_args(["github-workflow", "--help"])
        self.assertEqual(caught.exception.code, 0)
        for phase in runner.PHASES:
            self.assertIn(phase, out.getvalue())

    def test_preview_consumes_only_declared_variables(self) -> None:
        self.write_project()
        issue = self.write_json("issue.json", _issue())
        environ = RecordingEnviron(self.wrapper_env("idkmesh-preview.yml"))
        _, declared = _wrapper_contract(self.wrappers["idkmesh-preview.yml"])
        result = runner.run_preview(environ, issue_json=issue)
        self.assertEqual(result["phase"], "preview")
        self.assertLessEqual(
            environ.accessed, set(declared) | {"GITHUB_STEP_SUMMARY"}
        )

    def test_status_consumes_only_declared_variables(self) -> None:
        self.write_project()
        ledger = self.write_json("ledger.json", [self.ledger_record()])
        environ = RecordingEnviron(self.wrapper_env("idkmesh-status.yml"))
        _, declared = _wrapper_contract(self.wrappers["idkmesh-status.yml"])
        result = runner.run_status(environ, ledger_records=ledger)
        self.assertEqual(result["phase"], "status")
        self.assertLessEqual(
            environ.accessed, set(declared) | {"GITHUB_STEP_SUMMARY"}
        )

    def ledger_record(self, **overrides) -> dict:
        record = json.loads(LEDGER_FIXTURE.read_text(encoding="utf-8"))
        record.update(overrides)
        return record

    def test_each_required_variable_is_enforced_by_name(self) -> None:
        self.write_project()
        issue = self.write_json("issue.json", _issue())
        ledger = self.write_json("ledger.json", [self.ledger_record()])
        optional = {"IDKMESH_GITHUB_TOKEN", "IDKMESH_EVENT_PATH"}
        cases = (
            ("idkmesh-preview.yml", lambda e: runner.run_preview(e, issue_json=issue)),
            ("idkmesh-status.yml", lambda e: runner.run_status(e, ledger_records=ledger)),
        )
        for wrapper, call in cases:
            _, names = _wrapper_contract(self.wrappers[wrapper])
            for name in names:
                if name in optional:
                    continue
                with self.subTest(wrapper=wrapper, missing=name):
                    environ = self.wrapper_env(wrapper)
                    del environ[name]
                    with self.assertRaises(runner.GitHubWorkflowError) as caught:
                        call(environ)
                    self.assertEqual(caught.exception.code, "invalid_environment")
                    self.assertIn(name, caught.exception.message)

    def test_malformed_values_are_refused(self) -> None:
        self.write_project()
        issue = self.write_json("issue.json", _issue())
        for name, value in (
            ("IDKMESH_REPOSITORY", "not-a-repo"),
            ("IDKMESH_BASE_SHA", "ABC"),
            ("IDKMESH_BASE_SHA", "main"),
            ("IDKMESH_RUN_ID", "12 34"),
            ("IDKMESH_ISSUE_NUMBER", "0"),
            ("IDKMESH_ISSUE_NUMBER", "7; rm -rf /"),
            ("IDKMESH_ISSUE_NUMBER", "1\n2"),
        ):
            with self.subTest(name=name, value=value):
                environ = self.wrapper_env("idkmesh-preview.yml", **{name: value})
                with self.assertRaises(runner.GitHubWorkflowError) as caught:
                    runner.run_preview(environ, issue_json=issue)
                self.assertEqual(caught.exception.code, "invalid_environment")

    def test_error_codes_are_the_documented_set(self) -> None:
        self.assertEqual(
            runner.ERROR_CODES,
            {
                "invalid_environment",
                "project_policy_missing",
                "project_policy_invalid",
                "preview_scope_unconfigured",
                "event_issue_mismatch",
                "issue_unavailable",
                "preview_refused",
                "ledger_unavailable",
                "ledger_invalid",
                "ledger_run_not_found",
                "read_only_violation",
                "dispatch_unavailable",
                "verify_unavailable",
            },
        )
        with self.assertRaises(ValueError):
            runner.GitHubWorkflowError("made_up_code", "x")

    def test_runner_is_stdlib_only(self) -> None:
        # The wrappers run `setup-python` and nothing else: no pip install.
        tree = ast.parse(Path(runner.__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        third_party = imported - set(__import__("sys").stdlib_module_names) - {
            "idkmesh"
        }
        self.assertEqual(third_party, set())


class PreviewTests(RunnerHarness):
    def test_fresh_bootstrap_seed_needs_an_explicit_write_scope(self) -> None:
        self.write_project(scoped=False)
        issue = self.write_json("issue.json", _issue())
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_preview(self.wrapper_env("idkmesh-preview.yml"), issue_json=issue)
        self.assertEqual(caught.exception.code, "preview_scope_unconfigured")
        self.assertIn("allowed_paths", caught.exception.message)

    def test_preview_matches_the_underlying_primitive_exactly(self) -> None:
        self.write_project()
        issue = self.write_json("issue.json", _issue())
        result = runner.run_preview(
            self.wrapper_env("idkmesh-preview.yml"), issue_json=issue
        )
        expected = preview_github_issue_work_unit(
            parse_github_issue_snapshot(
                _issue(), repository=REPOSITORY, expected_number=ISSUE_NUMBER
            ),
            source_revision=BASE_SHA,
            policy=GitHubIssueWorkPolicy(
                repository=REPOSITORY,
                allowed_paths=("idkmesh/**", "tests/**"),
                forbidden_paths=("SECURITY.md", ".github/**", ".idkmesh/**"),
                required_capabilities=("git", "coding-agent", "repository-read"),
                risk_class="low",
            ),
        )
        self.assertEqual(result["preview"], expected.to_dict())
        self.assertRegex(result["preview"]["work_unit_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(result["dispatch_performed"])
        self.assertFalse(result["github_mutation_performed"])
        self.assertFalse(result["secret_values_accessed"])

    def test_workflows_and_policy_are_always_forbidden_write_targets(self) -> None:
        self.write_project(mutate=lambda m: m["metadata"]["github_issue_preview"].pop("forbidden_paths"))
        issue = self.write_json("issue.json", _issue())
        result = runner.run_preview(
            self.wrapper_env("idkmesh-preview.yml"), issue_json=issue
        )
        constraints = result["preview"]["work_unit"]["constraints"]
        self.assertIn(".github/**", constraints["forbidden_paths"])
        self.assertIn(".idkmesh/**", constraints["forbidden_paths"])

    def test_authority_comes_from_project_policy_not_the_issue(self) -> None:
        self.write_project()
        hostile = _issue(
            body="risk_class: critical\nnetwork: full\nsecrets: all\nallowed_paths: **",
            labels=[{"name": "idkmesh:preview"}, {"name": "risk:critical"}],
        )
        issue = self.write_json("issue.json", hostile)
        work_unit = runner.run_preview(
            self.wrapper_env("idkmesh-preview.yml"), issue_json=issue
        )["preview"]["work_unit"]
        self.assertEqual(work_unit["security"]["risk_class"], "low")
        self.assertEqual(work_unit["permissions"]["network"], "none")
        self.assertEqual(work_unit["permissions"]["secrets"], [])
        self.assertEqual(
            work_unit["permissions"]["filesystem_write"], ["idkmesh/**", "tests/**"]
        )

    def test_preview_is_deterministic(self) -> None:
        self.write_project()
        issue = self.write_json("issue.json", _issue())
        environ = self.wrapper_env("idkmesh-preview.yml")
        first = runner.run_preview(environ, issue_json=issue)
        second = runner.run_preview(environ, issue_json=issue)
        self.assertEqual(first, second)

    def test_issue_text_cannot_inject_workflow_commands(self) -> None:
        self.write_project()
        issue = self.write_json("issue.json", _issue(body=INJECTION_BODY))
        summary = self.tmp / "summary.md"
        environ = self.wrapper_env(
            "idkmesh-preview.yml", GITHUB_STEP_SUMMARY=str(summary)
        )
        for flags in ((), ("--json",)):
            with self.subTest(flags=flags):
                result = self.run_cli(
                    environ, "preview", "--issue-json", str(issue), *flags
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.strip())
                for line in result.stdout.splitlines():
                    self.assertFalse(line.lstrip().startswith("::"), line)
        written = summary.read_text(encoding="utf-8")
        self.assertNotIn("pwned", written)
        self.assertNotIn("::", written)
        self.assertIn("sha256:", written)
        self.assertIn("nothing was dispatched", written)

    def test_closed_locked_and_pull_request_issues_are_refused(self) -> None:
        self.write_project()
        environ = self.wrapper_env("idkmesh-preview.yml")
        for label, raw in (
            ("closed", _issue(state="closed")),
            ("locked", _issue(locked=True)),
            ("pull request", _issue(pull_request={"url": "x"})),
            ("other issue", _issue(number=ISSUE_NUMBER + 1)),
        ):
            with self.subTest(label):
                issue = self.write_json("issue.json", raw)
                with self.assertRaises(runner.GitHubWorkflowError) as caught:
                    runner.run_preview(environ, issue_json=issue)
                self.assertIn(
                    caught.exception.code, {"preview_refused", "issue_unavailable"}
                )

    def test_project_that_allows_automatic_merge_is_refused(self) -> None:
        def allow_merge(manifest):
            manifest["integration_policy"]["automatic_merge_allowed"] = True

        self.write_project(mutate=allow_merge)
        issue = self.write_json("issue.json", _issue())
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_preview(self.wrapper_env("idkmesh-preview.yml"), issue_json=issue)
        self.assertEqual(caught.exception.code, "project_policy_invalid")

    def test_missing_unsafe_and_oversized_project_policy_is_refused(self) -> None:
        issue = self.write_json("issue.json", _issue())
        environ = self.wrapper_env("idkmesh-preview.yml")
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_preview(environ, issue_json=issue)  # no checkout at all
        self.assertEqual(caught.exception.code, "invalid_environment")
        self.project.mkdir()
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_preview(environ, issue_json=issue)  # no .idkmesh/project.json
        self.assertEqual(caught.exception.code, "project_policy_missing")

        self.write_project(
            mutate=lambda m: m["metadata"]["github_issue_preview"].update(
                allowed_paths=["../outside"]
            )
        )
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_preview(environ, issue_json=issue)
        self.assertEqual(caught.exception.code, "project_policy_invalid")

        self.write_project(
            mutate=lambda m: m["risk_policy"].update(maximum_autonomous_risk="none")
        )
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_preview(environ, issue_json=issue)
        self.assertEqual(caught.exception.code, "project_policy_invalid")

        path = self.project / ".idkmesh" / "project.json"
        path.write_text(" " * (runner._MAX_JSON_BYTES + 1), encoding="utf-8")
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_preview(environ, issue_json=issue)
        self.assertEqual(caught.exception.code, "project_policy_invalid")

    def test_symlinked_project_policy_is_refused(self) -> None:
        self.write_project()
        real = self.project / ".idkmesh" / "project.json"
        moved = self.tmp / "elsewhere.json"
        real.rename(moved)
        real.symlink_to(moved)
        issue = self.write_json("issue.json", _issue())
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_preview(self.wrapper_env("idkmesh-preview.yml"), issue_json=issue)
        self.assertEqual(caught.exception.code, "project_policy_invalid")

    def test_event_for_a_different_issue_is_refused(self) -> None:
        self.write_project()
        issue = self.write_json("issue.json", _issue())
        event = self.write_json("event.json", {"issue": {"number": ISSUE_NUMBER + 5}})
        environ = self.wrapper_env("idkmesh-preview.yml", IDKMESH_EVENT_PATH=str(event))
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_preview(environ, issue_json=issue)
        self.assertEqual(caught.exception.code, "event_issue_mismatch")

        matching = self.write_json("event2.json", {"issue": {"number": ISSUE_NUMBER}})
        environ["IDKMESH_EVENT_PATH"] = str(matching)
        self.assertEqual(
            runner.run_preview(environ, issue_json=issue)["phase"], "preview"
        )

    def test_live_read_uses_the_token_and_never_echoes_it(self) -> None:
        self.write_project()
        seen = {}

        class FakeSource:
            def __init__(self, *, token=None):
                seen["token"] = token

            def get_issue_snapshot(self, *, repository, issue_number):
                seen["call"] = (repository, issue_number)
                return parse_github_issue_snapshot(
                    _issue(),
                    repository=repository,
                    expected_number=issue_number,
                )

        environ = self.wrapper_env("idkmesh-preview.yml")
        with mock.patch.object(runner, "GitHubRestIssueSource", FakeSource):
            result = self.run_cli(environ, "preview", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(seen["token"], TOKEN_SENTINEL)
        self.assertEqual(seen["call"], (REPOSITORY, ISSUE_NUMBER))
        self.assertNotIn(TOKEN_SENTINEL, result.stdout + result.stderr)

    def test_offline_mode_never_reads_the_token(self) -> None:
        self.write_project()
        issue = self.write_json("issue.json", _issue())
        environ = RecordingEnviron(self.wrapper_env("idkmesh-preview.yml"))
        runner.run_preview(environ, issue_json=issue)
        self.assertNotIn("IDKMESH_GITHUB_TOKEN", environ.accessed)

    def test_unavailable_issue_surfaces_a_stable_code(self) -> None:
        from idkmesh.connector_errors import ConnectorError

        self.write_project()

        class Down:
            def get_issue_snapshot(self, **_):
                raise ConnectorError(
                    code="provider_unavailable", message="GitHub is unavailable."
                )

        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_preview(
                self.wrapper_env("idkmesh-preview.yml"), issue_source=Down()
            )
        self.assertEqual(caught.exception.code, "issue_unavailable")
        self.assertIn("provider_unavailable", caught.exception.message)


class MemoryGitData:
    """Writable in-memory Git object database for populating a ledger branch."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.trees: dict[str, dict[str, str]] = {}
        self.commits: dict[str, tuple[str, tuple[str, ...]]] = {}
        self.branches: dict[str, str] = {}
        self.calls: list[str] = []
        self._n = 0

    def _sha(self, kind: str) -> str:
        self._n += 1
        return hashlib.sha1(f"{kind}:{self._n}".encode()).hexdigest()

    def get_branch_head(self, *, repository, branch):
        self.calls.append("get_branch_head")
        return self.branches.get(branch)

    def get_commit_tree(self, *, repository, commit_sha):
        self.calls.append("get_commit_tree")
        return self.commits[commit_sha][0]

    def get_tree(self, *, repository, tree_sha):
        self.calls.append("get_tree")
        return tuple(
            GitTreeEntry(path, "100644", "blob", sha)
            for path, sha in sorted(self.trees[tree_sha].items())
        )

    def get_blob(self, *, repository, blob_sha):
        self.calls.append("get_blob")
        return self.blobs[blob_sha]

    def create_blob(self, *, repository, content):
        self.calls.append("create_blob")
        sha = self._sha("blob")
        self.blobs[sha] = content
        return sha

    def create_tree(self, *, repository, base_tree_sha, files):
        self.calls.append("create_tree")
        tree = dict(self.trees.get(base_tree_sha, {}))
        tree.update(files)
        sha = self._sha("tree")
        self.trees[sha] = tree
        return sha

    def create_commit(self, *, repository, message, tree_sha, parents):
        self.calls.append("create_commit")
        sha = self._sha("commit")
        self.commits[sha] = (tree_sha, tuple(parents))
        return sha

    def create_branch(self, *, repository, branch, commit_sha):
        self.calls.append("create_branch")
        if branch in self.branches:
            raise GitHubGitDataConflict("exists")
        self.branches[branch] = commit_sha

    def update_branch(self, *, repository, branch, commit_sha):
        self.calls.append("update_branch")
        self.branches[branch] = commit_sha


class StatusTests(RunnerHarness):
    def records(self) -> list[dict]:
        first = json.loads(LEDGER_FIXTURE.read_text(encoding="utf-8"))
        second = copy.deepcopy(first)
        second["ledger_sequence"] = 2
        second["previous_record_digest"] = serialize_github_ledger_record(
            first
        ).record_digest
        second["record_id"] = "ledger/github-ledger-fixture/run-001/2"
        second["event"]["event_id"] = "event/github-ledger-fixture/run-001/2"
        second["event"]["state"] = "previewed"
        second["event"]["event_type"] = "run.previewed"
        return [first, second]

    def setUp(self) -> None:
        super().setUp()
        self.write_project()

    def test_projects_the_latest_record_and_appends_a_summary(self) -> None:
        ledger = self.write_json("ledger.json", self.records())
        summary = self.tmp / "summary.md"
        environ = self.wrapper_env(
            "idkmesh-status.yml", GITHUB_STEP_SUMMARY=str(summary)
        )
        result = runner.run_status(environ, ledger_records=ledger)
        self.assertEqual(result["state"], "previewed")
        self.assertEqual(result["ledger_records"], 2)
        self.assertFalse(result["comment_published"])
        self.assertTrue(result["summary_written"])
        self.assertFalse(result["github_mutation_performed"])
        body = summary.read_text(encoding="utf-8")
        self.assertEqual(body, result["body"] + "\n")
        self.assertIn("`previewed`", body)
        self.assertIn("github/mskazemi/idkmesh/issue-597", body)
        self.assertIn("Authority remains blocked", body)

    def test_status_cli_human_and_json_output(self) -> None:
        ledger = self.write_json("ledger.json", self.records())
        environ = self.wrapper_env("idkmesh-status.yml")
        human = self.run_cli(environ, "status", "--ledger-records", str(ledger))
        self.assertEqual(human.returncode, 0, human.stderr)
        self.assertIn("state: previewed", human.stdout)
        self.assertIn("GitHub mutations: no", human.stdout)
        machine = self.run_cli(
            environ, "status", "--ledger-records", str(ledger), "--json"
        )
        payload = json.loads(machine.stdout)
        self.assertEqual(payload["kind"], runner.RESULT_KIND)
        self.assertEqual(payload["state"], "previewed")

    def test_unknown_run_broken_chain_and_foreign_repository_are_refused(self) -> None:
        environ = self.wrapper_env("idkmesh-status.yml")

        other_run = self.write_json("a.json", self.records())
        missing = dict(environ, IDKMESH_RUN_REFERENCE="no-such-run")
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_status(missing, ledger_records=other_run)
        self.assertEqual(caught.exception.code, "ledger_run_not_found")

        gap = self.records()
        gap[1]["ledger_sequence"] = 3
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_status(environ, ledger_records=self.write_json("b.json", gap))
        self.assertEqual(caught.exception.code, "ledger_invalid")

        tampered = self.records()
        tampered[1]["previous_record_digest"] = "sha256:" + "0" * 64
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_status(environ, ledger_records=self.write_json("c.json", tampered))
        self.assertEqual(caught.exception.code, "ledger_invalid")

        foreign = dict(environ, IDKMESH_REPOSITORY="someone/else")
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_status(foreign, ledger_records=self.write_json("d.json", self.records()))
        self.assertEqual(caught.exception.code, "ledger_invalid")

        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_status(
                environ, ledger_records=self.write_json("e.json", {"not": "a list"})
            )
        self.assertEqual(caught.exception.code, "ledger_invalid")

    def populated_transport(self) -> MemoryGitData:
        transport = MemoryGitData()
        store = GitHubLedgerBranchStore(
            repository=REPOSITORY, transport=transport, default_branch="main"
        )
        for record in self.records():
            store.append_record(record)
        transport.calls.clear()
        return transport

    def test_live_read_goes_through_the_ledger_branch_without_writing(self) -> None:
        transport = self.populated_transport()
        result = runner.run_status(
            self.wrapper_env("idkmesh-status.yml"), transport=transport
        )
        self.assertEqual(result["state"], "previewed")
        self.assertEqual(result["ledger_records"], 2)
        self.assertTrue(transport.calls)
        self.assertEqual(
            {call for call in transport.calls if call.startswith(("create", "update"))},
            set(),
        )

    def test_missing_ledger_branch_is_reported_not_created(self) -> None:
        transport = MemoryGitData()
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_status(self.wrapper_env("idkmesh-status.yml"), transport=transport)
        self.assertEqual(caught.exception.code, "ledger_unavailable")
        self.assertIn(DEFAULT_LEDGER_BRANCH, caught.exception.message)
        self.assertEqual(transport.branches, {})
        self.assertEqual(transport.calls, ["get_branch_head"])

    def test_read_only_transport_refuses_every_mutation(self) -> None:
        guarded = runner._ReadOnlyGitData(self.populated_transport())
        for name in (
            "create_blob",
            "create_tree",
            "create_commit",
            "create_branch",
            "update_branch",
            "delete_ref",
        ):
            with self.subTest(name=name):
                with self.assertRaises(runner.GitHubWorkflowError) as caught:
                    getattr(guarded, name)
                self.assertEqual(caught.exception.code, "read_only_violation")
        self.assertTrue(callable(guarded.get_blob))

    def test_live_read_without_a_token_is_refused(self) -> None:
        environ = self.wrapper_env("idkmesh-status.yml")
        del environ["IDKMESH_GITHUB_TOKEN"]
        with self.assertRaises(runner.GitHubWorkflowError) as caught:
            runner.run_status(environ)
        self.assertEqual(caught.exception.code, "invalid_environment")


class ExecutionAuthorityTests(RunnerHarness):
    def test_dispatch_and_verify_fail_closed_without_reading_anything(self) -> None:
        for wrapper, phase, code in (
            ("idkmesh-dispatch.yml", "dispatch", "dispatch_unavailable"),
            ("idkmesh-verify.yml", "verify", "verify_unavailable"),
        ):
            with self.subTest(phase=phase):
                with self.assertRaises(runner.GitHubWorkflowError) as caught:
                    runner.run_unavailable(phase)
                self.assertEqual(caught.exception.code, code)

                # Through the real CLI, with the process environment replaced
                # by a recording mapping that holds the wrapper's secret.
                environ = RecordingEnviron(self.wrapper_env(wrapper))
                out, err = io.StringIO(), io.StringIO()
                with mock.patch.object(os, "environ", environ):
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                        returncode = cli.main(["github-workflow", phase])
                result = types.SimpleNamespace(
                    returncode=returncode, stdout=out.getvalue(), stderr=err.getvalue()
                )
                # argparse/gettext may consult locale and terminal variables.
                project_reads = {
                    name
                    for name in environ.accessed
                    if name.startswith(("IDKMESH_", "GITHUB_")) or name in SAMPLE_VALUES
                }
                self.assertEqual(project_reads, set())
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr.startswith(f"error: {code}:"))
                for sentinel in (SECRET_SENTINEL, TOKEN_SENTINEL):
                    self.assertNotIn(sentinel, result.stderr)

    def test_dispatch_wrapper_declares_the_secret_the_runner_never_reads(self) -> None:
        _, names = _wrapper_contract(self.wrappers["idkmesh-dispatch.yml"])
        self.assertIn("JULES_API_KEY", names)
        with self.assertRaises(ValueError):
            runner.run_unavailable("preview")

    def test_no_phase_can_dispatch_or_mutate(self) -> None:
        self.write_project()
        issue = self.write_json("issue.json", _issue())
        result = runner.run_preview(
            self.wrapper_env("idkmesh-preview.yml"), issue_json=issue
        )
        self.assertEqual(
            (
                result["dispatch_performed"],
                result["github_mutation_performed"],
                result["secret_values_accessed"],
            ),
            (False, False, False),
        )
        source = Path(runner.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "dispatch_github_run_once",
            "authorize_github_dispatch",
            "sync_github_run_status_comment",
            "create_issue_comment",
        ):
            self.assertNotIn(forbidden, source, forbidden)

    def test_cli_exits_two_with_a_stable_code_on_refusal(self) -> None:
        result = self.run_cli({}, "preview")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            result.stderr.strip(),
            "error: invalid_environment: IDKMESH_PROJECT_ROOT is required",
        )


if __name__ == "__main__":
    unittest.main()
