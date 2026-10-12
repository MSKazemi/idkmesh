"""Tests for deterministic C8-D bootstrap workflow-wrapper rendering (#596)."""

from __future__ import annotations

import contextlib
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from idkmesh import cli
import idkmesh.github_governance_preflight as preflight
from idkmesh.github_bootstrap import build_github_bootstrap_plan
from idkmesh.github_bootstrap_workflows import (
    DISPATCH_ENVIRONMENT,
    IDKMESH_REPOSITORY,
    PREVIEW_LABEL,
    RUNNER_COMMAND,
    render_github_bootstrap_workflows,
)
from idkmesh.github_bootstrap_render import BootstrapRenderError


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_FIXTURE = ROOT / "examples" / "github-governance" / "governance-pass-v0.1.json"
SHA = "1" * 40
WORKFLOW_PATHS = {
    ".github/workflows/idkmesh-dispatch.yml",
    ".github/workflows/idkmesh-preview.yml",
    ".github/workflows/idkmesh-status.yml",
    ".github/workflows/idkmesh-verify.yml",
}
# Same shape the repository's own workflow guard (test_security_automation)
# requires of every `uses:` line: an immutable 40-hex commit SHA.
FULL_SHA_USE = re.compile(
    r"^\s*uses:\s*([^\s@]+)@([0-9a-f]{40})(?:\s+#.*)?$", re.MULTILINE
)
USES_LINE = re.compile(r"^\s*uses:", re.MULTILINE)


def _by_name(rendered):
    return {item.path.rsplit("/", 1)[1]: item for item in rendered}


def _code(text: str) -> str:
    """Workflow text without comment lines, so prose cannot hide or fake a match."""

    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def _on_block(text: str) -> str:
    """The `on:` trigger mapping only (top-level keys until `permissions:`)."""

    match = re.search(r"(?ms)^on:\n(.*?)^permissions:", _code(text))
    assert match, "on: block missing"
    return match.group(1)


def _run_blocks(text: str) -> list[str]:
    """Every `run:` script body, so injection checks cannot miss a step."""

    lines = text.splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)run:\s*\|\s*$", line)
        if not match:
            continue
        indent = len(match.group(1))
        body: list[str] = []
        for later in lines[index + 1 :]:
            if later.strip() and len(later) - len(later.lstrip(" ")) <= indent:
                break
            body.append(later)
        blocks.append("\n".join(body))
    return blocks


def _job_permissions(text: str) -> dict[str, str]:
    match = re.search(
        r"(?m)^    permissions:\n((?:      [a-z-]+: [a-z]+\n)+)", text
    )
    assert match, "job-level permissions block missing"
    return dict(
        line.strip().split(": ")
        for line in match.group(1).splitlines()
    )


class GitHubBootstrapWorkflowRenderTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_github_bootstrap_plan(
            idkmesh_ref=SHA,
            default_branch="trunk",
        )
        self.rendered = render_github_bootstrap_workflows(self.plan)
        self.files = _by_name(self.rendered)

    def test_render_is_deterministic_and_exactly_c8_d(self):
        again = render_github_bootstrap_workflows(self.plan)
        self.assertEqual(self.rendered, again)
        self.assertEqual({item.path for item in self.rendered}, WORKFLOW_PATHS)
        specs = {item.path: item for item in self.plan.files}
        for item in self.rendered:
            spec = specs[item.path]
            self.assertEqual(spec.phase, "C8-D")
            self.assertEqual(item.ownership, "idkmesh_managed")
            self.assertEqual(item.overwrite_policy, spec.overwrite_policy)
            self.assertEqual(item.render_source, spec.render_source)
            self.assertTrue(item.content.endswith("\n"))
            self.assertNotIn("\t", item.content)
            self.assertEqual(
                item.content_digest,
                "sha256:" + hashlib.sha256(item.content.encode("utf-8")).hexdigest(),
            )
            self.assertEqual(item.size_bytes, len(item.content.encode("utf-8")))

    def test_every_remote_action_is_pinned_to_a_full_commit_sha(self):
        pins: dict[str, set[str]] = {}
        for item in self.rendered:
            uses = USES_LINE.findall(item.content)
            pinned = FULL_SHA_USE.findall(item.content)
            self.assertTrue(uses, item.path)
            self.assertEqual(len(uses), len(pinned), item.path)
            for action, sha in pinned:
                pins.setdefault(action, set()).add(sha)
        self.assertEqual(set(pins), {"actions/checkout", "actions/setup-python"})
        self.assertTrue(
            all(len(shas) == 1 for shas in pins.values()),
            "one Action must resolve to one reviewed commit across the pack",
        )

    def test_repository_governance_linter_finds_nothing_in_any_wrapper(self):
        for item in self.rendered:
            report = preflight.lint_workflow_text(item.content, label=item.path)
            self.assertEqual(report["findings"], [], item.path)
            source = report["workflow_source"]
            self.assertTrue(source["actions_default_contents_read"], item.path)
            self.assertTrue(source["checkout_persist_credentials_disabled"], item.path)
            self.assertTrue(source["immutable_security_actions"], item.path)
            self.assertTrue(source["untrusted_pr_secret_isolation"], item.path)
            self.assertFalse(source["oidc_token_permission"], item.path)

    def test_no_privileged_trigger_merge_or_broad_permission_exists(self):
        forbidden = (
            "pull_request",
            "workflow_run",
            "id-token",
            "write-all",
            "read-all",
            "contents: write",
            "pull-requests: write",
            "actions: write",
            "administration",
            "auto-merge",
            "automerge",
            "gh pr merge",
            "git push",
            "secrets: inherit",
        )
        for item in self.rendered:
            code = _code(item.content)
            for token in forbidden:
                self.assertNotIn(token, code, f"{item.path}: {token}")

    def test_job_permissions_match_each_declared_execution_effect(self):
        effects = {
            item.path.rsplit("/", 1)[1]: item.execution_effect
            for item in self.plan.files
            if item.phase == "C8-D"
        }
        self.assertEqual(
            effects,
            {
                "idkmesh-dispatch.yml": "candidate_dispatch",
                "idkmesh-preview.yml": "none",
                "idkmesh-status.yml": "publication",
                "idkmesh-verify.yml": "verification",
            },
        )
        self.assertEqual(
            _job_permissions(self.files["idkmesh-preview.yml"].content),
            {"contents": "read", "issues": "read"},
        )
        self.assertEqual(
            _job_permissions(self.files["idkmesh-dispatch.yml"].content),
            {"contents": "read", "issues": "read"},
        )
        self.assertEqual(
            _job_permissions(self.files["idkmesh-verify.yml"].content),
            {"contents": "read"},
        )
        self.assertEqual(
            _job_permissions(self.files["idkmesh-status.yml"].content),
            {"contents": "read", "issues": "write"},
        )
        writers = [
            name
            for name, item in self.files.items()
            if ": write" in item.content
        ]
        self.assertEqual(writers, ["idkmesh-status.yml"])

    def test_only_dispatch_is_environment_bound_and_secret_bearing(self):
        for name, item in self.files.items():
            code = _code(item.content)
            if name == "idkmesh-dispatch.yml":
                self.assertIn(f"    environment: {DISPATCH_ENVIRONMENT}\n", code)
                self.assertIn("${{ secrets.JULES_API_KEY }}", code)
                self.assertEqual(code.count("secrets."), 1)
            else:
                self.assertNotIn("environment:", code, name)
                self.assertNotIn("secrets.", code, name)

    def test_no_event_data_is_interpolated_into_a_shell_script(self):
        for item in self.rendered:
            blocks = _run_blocks(item.content)
            self.assertTrue(blocks, item.path)
            for block in blocks:
                self.assertNotIn("${{", block, item.path)
        # Issue text is untrusted: no workflow may even read it.
        for item in self.rendered:
            for token in ("issue.title", "issue.body", "head_ref", "comment.body"):
                self.assertNotIn(token, item.content, item.path)

    def test_idkmesh_runtime_is_pinned_to_the_bootstrap_ref(self):
        for item in self.rendered:
            self.assertIn(f'          repository: {IDKMESH_REPOSITORY}\n', item.content)
            self.assertIn(f'          ref: "{SHA}"\n', item.content)
            self.assertIn(f"# Pinned IDKMesh ref: {SHA}\n", item.content)

        tagged = render_github_bootstrap_workflows(
            build_github_bootstrap_plan(idkmesh_ref="v0.1.0", default_branch="trunk")
        )
        for item in tagged:
            self.assertIn('          ref: "v0.1.0"\n', item.content)
            self.assertNotIn(SHA, item.content)

    def test_runner_runs_from_the_pinned_runtime_and_is_probed_first(self):
        for item in self.rendered:
            text = item.content
            probe = text.index("Require the pinned IDKMesh GitHub workflow runner")
            run = text.rindex(f"          {RUNNER_COMMAND} ")
            self.assertLess(probe, run, item.path)
            self.assertIn(f"{RUNNER_COMMAND} --help", text[probe:run], item.path)
            # Running with the runtime as cwd keeps a same-named package in
            # the project checkout from shadowing the pinned IDKMesh.
            self.assertEqual(
                text.count("        working-directory: .idkmesh-runtime\n"),
                2,
                item.path,
            )
            self.assertIn("exit 1", text[probe:run])

    def test_jobs_run_only_from_the_protected_integration_branch(self):
        for item in self.rendered:
            self.assertIn("github.ref == 'refs/heads/trunk'", item.content, item.path)

        default = render_github_bootstrap_workflows(
            build_github_bootstrap_plan(idkmesh_ref=SHA)
        )
        for item in default:
            self.assertIn("github.ref == 'refs/heads/main'", item.content)
            self.assertNotIn("refs/heads/trunk", item.content)

    def test_preview_is_label_gated_and_dispatch_has_no_automatic_trigger(self):
        preview = self.files["idkmesh-preview.yml"].content
        self.assertEqual(
            re.findall(r"(?m)^  ([a-z_]+):", _on_block(preview)),
            ["issues", "workflow_dispatch"],
        )
        self.assertIn("  issues:\n    types: [labeled]\n", preview)
        self.assertIn(f"github.event.label.name == '{PREVIEW_LABEL}'", preview)
        for name in ("idkmesh-dispatch.yml", "idkmesh-verify.yml", "idkmesh-status.yml"):
            on_block = _on_block(self.files[name].content)
            self.assertEqual(
                re.findall(r"(?m)^  ([a-z_]+):", on_block),
                ["workflow_dispatch"],
                name,
            )

    def test_verify_treats_the_candidate_as_data_without_secrets_or_token(self):
        verify = self.files["idkmesh-verify.yml"].content
        self.assertIn("CANDIDATE_SHA: ${{ inputs.candidate_sha }}", verify)
        self.assertIn("^[0-9a-f]{40}$", verify)
        self.assertLess(
            verify.index("^[0-9a-f]{40}$"),
            verify.index("ref: ${{ inputs.candidate_sha }}"),
            "the SHA must be validated before the candidate is fetched",
        )
        candidate = verify[verify.index("exact candidate revision as data") :]
        candidate = candidate[: candidate.index("      - name: Set up Python")]
        self.assertIn("persist-credentials: false", candidate)
        self.assertIn("path: .idkmesh-candidate", candidate)
        code = _code(verify)
        self.assertNotIn("github.token", code)
        self.assertNotIn("secrets.", code)
        self.assertNotIn("TOKEN", code)

    def test_dispatch_requires_an_explicit_digest_and_connector(self):
        dispatch = self.files["idkmesh-dispatch.yml"].content
        for name in ("issue_number", "work_unit_digest", "connector_id"):
            self.assertRegex(
                dispatch,
                rf"(?m)^      {name}:\n        description: .+\n        required: true\n",
            )
        self.assertIn("IDKMESH_WORK_UNIT_DIGEST: ${{ inputs.work_unit_digest }}", dispatch)
        self.assertIn("IDKMESH_CONNECTOR_ID: ${{ inputs.connector_id }}", dispatch)

    def test_secret_references_are_derived_from_the_connector_seed(self):
        from idkmesh.github_bootstrap_render import render_github_bootstrap_config

        connections = next(
            item
            for item in render_github_bootstrap_config(self.plan)
            if item.path == ".idkmesh/connections.json"
        )
        refs = {
            entry["auth"]["secret_ref"].removeprefix("env:")
            for entry in json.loads(connections.content)
        }
        dispatch = self.files["idkmesh-dispatch.yml"].content
        used = set(re.findall(r"\$\{\{ secrets\.([A-Z0-9_]+) \}\}", dispatch))
        self.assertEqual(used, refs)
        self.assertTrue(refs)

    def test_plan_drift_fails_closed_instead_of_silently_dropping_wrappers(self):
        missing = replace(
            self.plan,
            files=tuple(
                item
                for item in self.plan.files
                if item.path != ".github/workflows/idkmesh-verify.yml"
            ),
        )
        with self.assertRaises(BootstrapRenderError) as raised:
            render_github_bootstrap_workflows(missing)
        self.assertEqual(raised.exception.code, "workflow_plan_mismatch")

        extra_spec = replace(
            next(
                item
                for item in self.plan.files
                if item.path == ".github/workflows/idkmesh-verify.yml"
            ),
            path=".github/workflows/idkmesh-extra.yml",
        )
        extra = replace(self.plan, files=self.plan.files + (extra_spec,))
        with self.assertRaises(BootstrapRenderError) as raised:
            render_github_bootstrap_workflows(extra)
        self.assertEqual(raised.exception.code, "workflow_plan_mismatch")

    def test_unsafe_connector_secret_reference_fails_closed(self):
        for bad in ("vault:JULES_API_KEY", "env:lower_case", "env:", "env:A B"):
            seed = [{"auth": {"secret_ref": bad}}]
            with mock.patch(
                "idkmesh.github_bootstrap_workflows._connections_document",
                return_value=seed,
            ), self.subTest(secret_ref=bad):
                with self.assertRaises(BootstrapRenderError) as raised:
                    render_github_bootstrap_workflows(self.plan)
                self.assertEqual(raised.exception.code, "invalid_secret_reference")

    def test_renderer_output_must_be_tab_free_and_newline_terminated(self):
        for bad in ("no trailing newline", "tab\there\n"):
            with mock.patch(
                "idkmesh.github_bootstrap_workflows._preview", return_value=bad
            ), self.subTest(content=bad):
                with self.assertRaises(BootstrapRenderError) as raised:
                    render_github_bootstrap_workflows(self.plan)
                self.assertEqual(raised.exception.code, "invalid_rendered_content")

    def test_non_plan_input_is_rejected(self):
        with self.assertRaises(TypeError):
            render_github_bootstrap_workflows({"files": []})  # type: ignore[arg-type]


class GitHubBootstrapWorkflowCliIntegrationTests(unittest.TestCase):
    """Drive the real CLI entry and judge its output with the repo's own guards."""

    def run_cli(self, *args, cwd: Path | None = None):
        out, err = io.StringIO(), io.StringIO()
        context = contextlib.chdir(cwd) if cwd is not None else contextlib.nullcontext()
        with context, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def dry_run_payload(self, ref=SHA, branch="main"):
        code, stdout, stderr = self.run_cli(
            "init", "--github", "--dry-run",
            "--idkmesh-ref", ref,
            "--default-branch", branch,
            "--json",
        )
        self.assertEqual(code, 0, stderr)
        return json.loads(stdout)

    def test_cli_emits_exactly_the_planned_wrappers_with_matching_digests(self):
        payload = self.dry_run_payload()
        wrappers = payload["rendered_workflow_files"]
        planned = {
            item["path"]: item
            for item in payload["plan"]["files"]
            if item["phase"] == "C8-D"
        }
        self.assertEqual({item["path"] for item in wrappers}, set(planned))
        self.assertEqual(set(planned), WORKFLOW_PATHS)
        for item in wrappers:
            spec = planned[item["path"]]
            self.assertEqual(item["ownership"], spec["ownership"])
            self.assertEqual(item["overwrite_policy"], spec["overwrite_policy"])
            self.assertEqual(
                item["content_digest"],
                "sha256:" + hashlib.sha256(item["content"].encode("utf-8")).hexdigest(),
            )
            self.assertFalse(item["secret_values_accessed"])
            self.assertFalse(item["integration_authority"])
        self.assertFalse(payload["writes_performed"])
        self.assertFalse(payload["github_mutation_performed"])
        self.assertFalse(payload["secret_values_accessed"])

    def test_cli_output_is_byte_deterministic(self):
        args = ("init", "--github", "--dry-run", "--idkmesh-ref", "v0.1.0", "--json")
        self.assertEqual(self.run_cli(*args), self.run_cli(*args))

    def test_cli_wrappers_satisfy_the_repository_governance_guards(self):
        payload = self.dry_run_payload(branch="trunk")
        observation = json.loads(GOVERNANCE_FIXTURE.read_text(encoding="utf-8"))
        by_name = {
            item["path"].rsplit("/", 1)[1]: item["content"]
            for item in payload["rendered_workflow_files"]
        }
        for name, text in by_name.items():
            self.assertEqual(preflight.lint_workflow_text(text)["findings"], [], name)

        dispatch = preflight.merge_workflow_lints(
            observation,
            [preflight.lint_workflow_text(by_name["idkmesh-dispatch.yml"])],
        )
        for operation in ("secret_bearing_dispatch", "high_risk_dispatch"):
            report = preflight.evaluate_governance(operation, dispatch)
            self.assertTrue(report["operation_allowed"], (operation, report["status"]))

        read_only = preflight.merge_workflow_lints(
            observation,
            [
                preflight.lint_workflow_text(by_name[name])
                for name in (
                    "idkmesh-preview.yml",
                    "idkmesh-status.yml",
                    "idkmesh-verify.yml",
                )
            ],
        )
        report = preflight.evaluate_governance("read_only", read_only)
        self.assertTrue(report["operation_allowed"], report["status"])

    def test_cli_wrappers_agree_with_cli_rendered_connector_secret_references(self):
        payload = self.dry_run_payload()
        connections = next(
            item
            for item in payload["rendered_config_files"]
            if item["path"] == ".idkmesh/connections.json"
        )
        refs = {
            entry["auth"]["secret_ref"].removeprefix("env:")
            for entry in json.loads(connections["content"])
        }
        dispatch = next(
            item["content"]
            for item in payload["rendered_workflow_files"]
            if item["path"].endswith("idkmesh-dispatch.yml")
        )
        self.assertEqual(
            set(re.findall(r"secrets\.([A-Z0-9_]+)", dispatch)),
            refs,
        )

    def test_human_output_lists_wrappers_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = sorted(root.rglob("*"))
            code, stdout, stderr = self.run_cli(
                "init", "--github", "--dry-run", "--idkmesh-ref", "v0.1.0",
                cwd=root,
            )
            after = sorted(root.rglob("*"))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(before, after)
        self.assertIn("rendered C8-D workflow wrappers:", stdout)
        for path in WORKFLOW_PATHS:
            self.assertRegex(stdout, rf"- {re.escape(path)} \[sha256:[0-9a-f]{{64}}; \d+ bytes\]")
        self.assertNotIn("secrets.", stdout)

    def test_unpinned_ref_still_fails_before_any_wrapper_is_rendered(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["init", "--github", "--dry-run", "--idkmesh-ref", "main"])
        self.assertNotEqual(code, 0)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("unpinned_idkmesh_ref", err.getvalue())


if __name__ == "__main__":
    unittest.main()
