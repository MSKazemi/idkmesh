"""C8-G: fresh-repository bootstrap -> deterministic work preview, no server (#596).

Every earlier C8 slice is tested against its own module. This fixture walks the
whole acceptance path of #596 as a newcomer would, on a bare directory that only
has a ``.git`` marker, using the public CLI entry points and nothing else:

    idkmesh init --github --apply        (install the generated files)
    owner chooses a write scope          (the one step the runner refuses to guess)
    idkmesh github-workflow preview      (environment read from the *installed* wrapper)
    idkmesh github-workflow status       (read-only ledger projection)

The environment handed to the runner is derived from the workflow file that was
written to disk, not from the renderer's in-memory output, so a wrapper/runner
drift that survives rendering but not installation is caught here. The whole walk
runs with the network blocked: "without an always-on IDKMesh server" is asserted,
not assumed. No test contacts GitHub.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import socket
import tempfile
import types
import unittest
from unittest import mock

from idkmesh import cli

ROOT = Path(__file__).resolve().parents[1]
LEDGER_FIXTURE = (
    ROOT / "tests" / "fixtures" / "github-ledger" / "00000000000000000001.json"
)
REF = "1" * 40
BASE_SHA = "2" * 40
REPOSITORY = "MSKazemi/idkmesh"
ISSUE_NUMBER = 77
TOKEN_SENTINEL = "ghs_token_sentinel_c8g"
SECRET_SENTINEL = "provider-secret-sentinel-c8g"

PLANNED_FILES = (
    ".github/workflows/idkmesh-dispatch.yml",
    ".github/workflows/idkmesh-preview.yml",
    ".github/workflows/idkmesh-status.yml",
    ".github/workflows/idkmesh-verify.yml",
    ".idkmesh/README.md",
    ".idkmesh/connections.json",
    ".idkmesh/domain-packs/software-engineering-v0.1.domain-pack.json",
    ".idkmesh/project.json",
)
STATE_FILE = ".idkmesh/bootstrap-state.json"
OWNER_SCOPE = {
    "allowed_paths": ["src/**", "tests/**"],
    "forbidden_paths": ["SECURITY.md"],
}

# Values for the expressions the wrappers pass, by environment variable name.
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


def _issue() -> dict:
    return {
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


def _wrapper_contract(content: str) -> tuple[str, tuple[str, ...]]:
    """The phase a wrapper runs and the env names its runner step passes."""

    phase = re.search(r"github-workflow (\w+)\n", content)
    assert phase, "installed wrapper has no runner command"
    step = content[content.index("- name: Run IDKMesh") :]
    env_block = step.split("        env:\n", 1)[1].split("        run:", 1)[0]
    names = re.findall(r"^          ([A-Z][A-Z0-9_]*):", env_block, re.MULTILINE)
    return phase.group(1), tuple(names)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FreshRepositoryBootstrapToPreviewTests(unittest.TestCase):
    """The #596 acceptance path on a repository that has never seen IDKMesh."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / "repo"
        # `.git` is the only marker the installer requires; a real `git init`
        # would only add host-specific templates and hooks to the fixture.
        (self.repo / ".git").mkdir(parents=True)

        # Block every outbound connection for the entire walk.
        for target in ("socket.socket.connect", "socket.create_connection"):
            patcher = mock.patch(target, side_effect=self._no_network)
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def _no_network(*args, **kwargs):
        raise AssertionError("the bootstrap-to-preview walk must not open a socket")

    # -- helpers ---------------------------------------------------------

    def run_cli(self, argv: list[str], environ: dict[str, str] | None = None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.chdir(self.repo):
            with mock.patch.dict(os.environ, environ or {}, clear=True):
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    try:
                        code = cli.main(argv)
                    except SystemExit as exc:
                        code = exc.code if isinstance(exc.code, int) else 1
        return types.SimpleNamespace(
            returncode=code, stdout=out.getvalue(), stderr=err.getvalue()
        )

    def bootstrap(self):
        return self.run_cli(
            ["init", "--github", "--apply", "--idkmesh-ref", REF, "--json"]
        )

    def installed_files(self) -> set[str]:
        return {
            path.relative_to(self.repo).as_posix()
            for path in self.repo.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(self.repo).parts
        }

    def owner_configures_scope(self) -> None:
        """The owner decision the runner refuses to guess (spec: no default)."""

        path = self.repo / ".idkmesh" / "project.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["metadata"]["github_issue_preview"] = OWNER_SCOPE
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def installed_env(self, wrapper: str) -> dict[str, str]:
        """Environment built from the wrapper that was written to disk."""

        content = (self.repo / ".github" / "workflows" / wrapper).read_text(
            encoding="utf-8"
        )
        _, names = _wrapper_contract(content)
        env = {}
        for name in names:
            if name == "IDKMESH_PROJECT_ROOT":
                env[name] = str(self.repo)
            elif name == "IDKMESH_CANDIDATE_DIR":
                env[name] = str(self.tmp / "candidate")
            elif name == "IDKMESH_EVENT_PATH":
                continue
            else:
                env[name] = SAMPLE_VALUES[name]
        return env

    def write_issue(self) -> Path:
        path = self.tmp / "issue.json"
        path.write_text(json.dumps(_issue()), encoding="utf-8")
        return path

    def preview(self):
        return self.run_cli(
            [
                "github-workflow",
                "preview",
                "--issue-json",
                str(self.write_issue()),
                "--json",
            ],
            self.installed_env("idkmesh-preview.yml"),
        )

    # -- the acceptance path --------------------------------------------

    def test_the_network_guard_actually_blocks_connections(self) -> None:
        # Positive control: the "no server" claims below mean nothing unless a
        # connection attempt would fail this fixture.
        with self.assertRaises(AssertionError):
            socket.create_connection(("127.0.0.1", 9), timeout=0.1)
        with self.assertRaises(AssertionError):
            socket.socket().connect(("127.0.0.1", 9))

    def test_bootstrap_installs_exactly_the_planned_files(self) -> None:
        result = self.bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["writes_performed"])
        self.assertFalse(report["github_mutation_performed"])
        self.assertFalse(report["secret_values_accessed"])
        self.assertEqual(
            {item["action"] for item in report["actions"]}, {"create"}
        )
        self.assertEqual(
            self.installed_files(), set(PLANNED_FILES) | {STATE_FILE}
        )

    def test_unconfigured_project_refuses_preview_and_names_the_owner_step(
        self,
    ) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        result = self.preview()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("preview_scope_unconfigured", result.stderr)
        self.assertIn("allowed_paths", result.stderr)

    def test_owner_scope_then_preview_is_deterministic_and_authority_free(
        self,
    ) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        self.owner_configures_scope()

        first = self.preview()
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.preview()
        self.assertEqual(second.stdout, first.stdout)
        self.assertEqual(len(first.stdout.splitlines()), 1)

        result = json.loads(first.stdout)
        self.assertEqual(result["phase"], "preview")
        self.assertEqual(result["repository"], REPOSITORY)
        self.assertEqual(result["base_sha"], BASE_SHA)
        self.assertEqual(result["issue_number"], ISSUE_NUMBER)
        self.assertIs(result["dispatch_performed"], False)
        self.assertIs(result["github_mutation_performed"], False)
        self.assertIs(result["secret_values_accessed"], False)

        # The owner's scope reached the WorkUnit, and the always-forbidden
        # control paths were added on top of it.
        encoded = json.dumps(result["preview"], sort_keys=True)
        for pattern in OWNER_SCOPE["allowed_paths"]:
            self.assertIn(pattern, encoded)
        for pattern in (*OWNER_SCOPE["forbidden_paths"], ".github/**", ".idkmesh/**"):
            self.assertIn(pattern, encoded)

        # No credential from the environment reaches the output.
        for sentinel in (TOKEN_SENTINEL, SECRET_SENTINEL):
            self.assertNotIn(sentinel, first.stdout + first.stderr)

    def test_status_projects_the_ledger_read_only(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        self.owner_configures_scope()
        ledger = self.tmp / "ledger.json"
        ledger.write_text(
            json.dumps([json.loads(LEDGER_FIXTURE.read_text(encoding="utf-8"))]),
            encoding="utf-8",
        )
        result = self.run_cli(
            [
                "github-workflow",
                "status",
                "--ledger-records",
                str(ledger),
                "--json",
            ],
            self.installed_env("idkmesh-status.yml"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["phase"], "status")
        self.assertIs(report["dispatch_performed"], False)
        self.assertIs(report["github_mutation_performed"], False)

    def test_dispatch_and_verify_stay_closed_on_a_bootstrapped_repository(
        self,
    ) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        self.owner_configures_scope()
        for phase, code in (
            ("dispatch", "dispatch_unavailable"),
            ("verify", "verify_unavailable"),
        ):
            with self.subTest(phase=phase):
                result = self.run_cli(
                    ["github-workflow", phase],
                    self.installed_env(f"idkmesh-{phase}.yml"),
                )
                self.assertEqual(result.returncode, 2)
                # An argparse usage error also exits 2, so match the refusal.
                self.assertRegex(result.stderr, rf"^error: {code}: ")
                self.assertEqual(result.stdout, "")

    # -- re-run safety ---------------------------------------------------

    def test_rerun_after_owner_edit_preserves_it_and_writes_nothing(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        self.owner_configures_scope()
        before = {name: _sha256(self.repo / name) for name in self.installed_files()}

        result = self.bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["writes_performed"])
        actions = {item["path"]: item["action"] for item in report["actions"]}
        self.assertEqual(actions[".idkmesh/project.json"], "preserve")
        self.assertEqual(actions[".idkmesh/connections.json"], "preserve")

        after = {name: _sha256(self.repo / name) for name in self.installed_files()}
        self.assertEqual(after, before)
        # ...and the preserved edit still previews.
        self.assertEqual(self.preview().returncode, 0)

    def test_rerun_refuses_a_hand_edited_workflow_and_leaves_it_alone(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        workflow = self.repo / ".github" / "workflows" / "idkmesh-preview.yml"
        workflow.write_text(
            workflow.read_text(encoding="utf-8") + "# local tweak\n",
            encoding="utf-8",
        )
        edited = _sha256(workflow)

        result = self.bootstrap()
        self.assertEqual(result.returncode, 2)
        self.assertIn("managed_file_modified", result.stderr)
        self.assertIn("idkmesh-preview.yml", result.stderr)
        self.assertEqual(_sha256(workflow), edited)

    def test_check_mode_reports_a_clean_tree_without_writing(self) -> None:
        self.assertEqual(self.bootstrap().returncode, 0)
        before = {name: _sha256(self.repo / name) for name in self.installed_files()}
        result = self.run_cli(
            ["init", "--github", "--check", "--idkmesh-ref", REF, "--json"]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["writes_performed"])
        self.assertNotIn("create", {item["action"] for item in report["actions"]})
        self.assertEqual(
            before, {name: _sha256(self.repo / name) for name in self.installed_files()}
        )


if __name__ == "__main__":
    unittest.main()
