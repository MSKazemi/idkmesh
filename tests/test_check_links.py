"""Exercise the unified gate on real temporary Git indexes, never the live tree."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from scripts import check_links as gate
from tools.idkgraph_link_check import check_links as markdown_check


class UnifiedLinkGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")

    def git(self, *args: str) -> bytes:
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True, check=True,
        ).stdout

    def write(self, name: str, text: str = "", *, tracked: bool = True) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if tracked:
            self.git("add", "--", name)

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(gate.ROOT / "scripts/check_links.py"), str(self.root), *args],
            cwd=self.root, capture_output=True, text=True, timeout=30,
        )

    def test_all_three_issue_probes_and_missing_directory_are_reported(self) -> None:
        targets = ["scripts/no_such_script_xyz.py", "schemas/no_such_schema_xyz.json",
                   "docs/no_such_doc_xyz.md", "missing-directory/"]
        self.write("SUPPORT.md", "# Support\n" + "".join(f"[probe]({t})\n" for t in targets))
        report = gate.check_repository_links(self.root)
        self.assertEqual({f["raw_target"] for f in report["findings"]}, set(targets))
        self.assertEqual(report["summary"]["findings"], 4)
        result = self.cli("--json")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout), report)
        # The new combined gate does not silently expand the T2 identity contract.
        self.assertEqual(markdown_check(self.root)["summary"]["ignored_non_markdown_links"], 3)

    def test_valid_assets_directories_root_and_markdown_anchor_pass(self) -> None:
        self.write("scripts/run.py", "pass\n")
        self.write("schemas/a.json", "{}\n")
        self.write("docs/a.md", "# Anchor\n")
        self.write("README.md", "[a](scripts/run.py) [b](schemas/a.json) [c](scripts/) "
                   "[root](.) [anchor](docs/a.md#anchor)\n")
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("non-fixture link findings: 0", result.stdout)

    def test_wrong_markdown_anchor_still_fails(self) -> None:
        self.write("README.md", "# Readme\n[bad](#absent)\n")
        self.assertEqual(self.cli().returncode, 1)
        self.assertEqual(gate.check_repository_links(self.root)["findings"][0]["category"],
                         "missing_markdown_anchor")

    def test_encoded_hash_and_query_cannot_hide_missing_filename_suffixes(self) -> None:
        self.write("scripts/report", "present prefix, not the requested file\n")
        for encoded in ("%23", "%3F"):
            with self.subTest(encoded=encoded):
                target = f"scripts/report{encoded}missing.py"
                self.write("README.md", f"[bad]({target})\n")
                rows = gate.collect_local_non_markdown_links(self.root)
                self.assertEqual(rows[0][3], "missing")
                # Reproduce the original collector's double-parse false negative.
                old_argument = unquote(urlsplit(target).path)
                self.assertEqual(gate.classify_link(self.root, "README.md", old_argument), "exists")

    def test_percent_encoded_filename_is_decoded_once(self) -> None:
        self.write("data/literal%20name.json", "{}\n")
        self.write("README.md", "[literal](data/literal%2520name.json)\n")
        self.assertEqual(gate.collect_local_non_markdown_links(self.root)[0][3], "exists")
        self.assertEqual(self.cli().returncode, 0)

    def test_double_decoding_cannot_alias_a_missing_file_to_a_real_one(self) -> None:
        self.write("data/has space.json", "{}\n")
        self.write("README.md", "[missing literal percent](data/has%2520space.json)\n")
        self.assertEqual(gate.collect_local_non_markdown_links(self.root)[0][3], "missing")

    def test_real_encoded_hash_and_space_filenames_resolve(self) -> None:
        self.write("data/hash#name.json", "{}\n")
        self.write("data/has space.json", "{}\n")
        self.write("README.md", "[a](data/hash%23name.json) [b](data/has%20space.json)\n")
        self.assertTrue(all(row[3] == "exists" for row in gate.collect_local_non_markdown_links(self.root)))

    def test_untracked_assets_do_not_pass_and_untracked_docs_do_not_add_findings(self) -> None:
        self.write("README.md", "[generated](generated/out.json)\n")
        self.write("generated/out.json", "{}", tracked=False)
        self.write("untracked.md", "[bad](ghost.py)\n", tracked=False)
        report = gate.check_repository_links(self.root)
        self.assertEqual([f["raw_target"] for f in report["findings"]], ["generated/out.json"])
        self.assertNotIn("generated", gate.tracked_paths(self.root))

    def test_only_root_fixture_prefix_is_excluded(self) -> None:
        self.write("README.md", "# Readme\n")
        self.write("tests/fixtures/broken.md", "[bad](missing.md) [bad](missing.json)\n")
        self.assertEqual(self.cli().returncode, 0)
        self.write("examples/tests/fixtures/not-exempt.md", "[bad](missing.md) [bad](missing.json)\n")
        findings = gate.check_repository_links(self.root)["findings"]
        self.assertEqual(len(findings), 2)
        self.assertTrue(all(f["source_path"].startswith("examples/") for f in findings))

    def test_external_and_code_links_are_not_checked(self) -> None:
        self.write("README.md", "[web](https://example.invalid/a.json)\n"
                   "[mail](mailto:test@example.invalid)\n`[code](absent.py)`\n"
                   "```md\n[code](absent.json)\n```\n")
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")):
            self.assertEqual(gate.check_repository_links(self.root)["summary"]["findings"], 0)

    def test_escape_is_reported_and_legacy_github_routes_are_preserved(self) -> None:
        self.write("docs/a.md", "[escape](../../outside.json) [issue](../../issues/24)\n")
        rows = gate.collect_local_non_markdown_links(self.root)
        self.assertEqual({r[3] for r in rows}, {"escapes", "github_route"})
        self.assertEqual(gate.check_repository_links(self.root)["findings"][0]["category"],
                         "asset_escapes_repository")

    def test_report_is_deterministic_and_tree_and_index_are_unchanged(self) -> None:
        self.write("README.md", "[bad](gone.json) [bad](gone.md)\n")
        before_files = {p.relative_to(self.root).as_posix(): p.read_bytes()
                        for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts}
        before_index = self.git("ls-files", "--stage", "-z")
        before_diff = self.git("diff", "--binary")
        first, second = self.cli("--json"), self.cli("--json")
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.returncode, 1)
        self.assertNotIn(str(self.root), first.stdout)
        self.assertEqual(before_index, self.git("ls-files", "--stage", "-z"))
        self.assertEqual(before_diff, self.git("diff", "--binary"))
        after_files = {p.relative_to(self.root).as_posix(): p.read_bytes()
                       for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts}
        self.assertEqual(before_files, after_files)
        self.assertFalse(any(json.loads(first.stdout)["authority"].values()))

    def test_non_git_directory_fails_instead_of_reporting_clean(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            result = subprocess.run([sys.executable, str(gate.ROOT / "scripts/check_links.py"), raw],
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 2)
        self.assertIn("inspection unavailable", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_git_unavailable_has_distinct_exit_code(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with patch.object(gate, "tracked_paths", side_effect=FileNotFoundError("git unavailable")):
            with redirect_stdout(out), redirect_stderr(err):
                code = gate.main([str(self.root), "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("git unavailable", err.getvalue())

    def test_unexpected_programming_error_is_not_swallowed(self) -> None:
        with patch.object(gate, "check_repository_links", side_effect=AssertionError("defect")):
            with self.assertRaisesRegex(AssertionError, "defect"):
                gate.main([str(self.root)])


class LinkGateIntegrationTests(unittest.TestCase):
    def test_ci_invokes_the_shared_command_without_an_inline_checker(self) -> None:
        workflow = (gate.ROOT / ".github/workflows/pr-gate.yml").read_text(encoding="utf-8")
        step = workflow.split("- name: Check deterministic Markdown link integrity", 1)[1]
        self.assertIn("run: python scripts/check_links.py", step)
        self.assertNotIn("python - <<", step)
        self.assertNotIn("json.loads(raw)", step)


if __name__ == "__main__":
    unittest.main()
