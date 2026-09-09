"""Guard the newcomer demo without modifying the repository's fixtures."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# The legacy randomness-lab job intentionally has no third-party dependencies.
# Match the other Phase 0 test modules there, but never skip in the required gate.
try:
    from scripts import demo
except ModuleNotFoundError as exc:
    if exc.name != "jsonschema" or os.environ.get("GITHUB_WORKFLOW") == "PR Gate":
        raise
    raise unittest.SkipTest(
        "contract demo tests require requirements-phase0.txt; run the full PR Gate"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "scripts" / "demo.py"
SELF_ACCEPTED = ROOT / "examples" / "results" / "invalid-self-acceptance.result-manifest.json"


def run_demo(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEMO), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


class DemoTests(unittest.TestCase):
    def test_quiet_run_succeeds_and_names_fixture_evidence(self) -> None:
        result = run_demo("--quiet")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3 accepted, 4 rejected", result.stdout)
        self.assertIn("synthetic fixtures only", result.stdout)

    def test_narrated_run_tells_the_whole_story(self) -> None:
        result = run_demo()
        self.assertEqual(result.returncode, 0, result.stderr)
        for act in range(1, 8):
            self.assertIn(f"  {act}. ", result.stdout, f"act {act} missing")
        lines = [line.lstrip() for line in result.stdout.splitlines()]
        # Result lines have two spaces after the label, unlike explanatory prose.
        self.assertEqual(sum(line.startswith("ACCEPTED  ") for line in lines), 1)
        self.assertEqual(sum(line.startswith("REJECTED  ") for line in lines), 4)
        self.assertIn("no live worker or verifier is executed", result.stdout)
        self.assertIn("not live identity or statistical independence", result.stdout)

    def test_demo_fails_when_self_acceptance_is_allowed(self) -> None:
        """Change a temporary fixture, never the shared working-tree original."""
        original = SELF_ACCEPTED.read_bytes()
        weakened = json.loads(original)
        self.assertIsNotNone(weakened.pop("accepted", None))
        original_resolver = demo.resolve_repo_path
        with tempfile.TemporaryDirectory() as directory:
            replacement = Path(directory) / "worker-result.json"
            replacement.write_text(json.dumps(weakened), encoding="utf-8")

            def resolve(path: str) -> Path:
                if path == demo.SELF_ACCEPTED:
                    return replacement
                return original_resolver(path)

            with patch.object(demo, "resolve_repo_path", side_effect=resolve):
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(demo.HarnessError, "DEMO FAILED"):
                        demo.run(quiet=True)
        self.assertEqual(SELF_ACCEPTED.read_bytes(), original)

    def test_only_contract_errors_count_as_expected_rejections(self) -> None:
        for error_type in (demo.HarnessError, demo.IntegrityError):
            with self.subTest(error_type=error_type):
                def reject() -> None:
                    raise error_type("expected contract rejection")
                self.assertEqual(demo.expect_rejection(reject), "expected contract rejection")

    def test_unexpected_errors_do_not_count_as_rejections(self) -> None:
        errors = (
            SystemExit(0), SystemExit(2), AssertionError("programming error"),
            FileNotFoundError("fixture unavailable"), RuntimeError("unexpected failure"),
        )
        for error in errors:
            with self.subTest(error=repr(error)):
                def crash() -> None:
                    raise error
                with self.assertRaises(type(error)) as raised:
                    demo.expect_rejection(crash)
                self.assertIs(raised.exception, error)

    def test_early_validator_exit_is_a_cli_failure_even_for_zero(self) -> None:
        for code in (0, 2):
            with self.subTest(code=code):
                stderr = io.StringIO()
                with patch.object(sys, "argv", ["demo.py", "--quiet"]):
                    with patch.object(demo, "run", side_effect=SystemExit(code)):
                        with contextlib.redirect_stderr(stderr):
                            self.assertEqual(demo.main(), 1)
                self.assertIn("unexpected validator exit", stderr.getvalue())

    def test_unexpected_acceptance_fails_the_demo(self) -> None:
        with self.assertRaisesRegex(demo.HarnessError, "DEMO FAILED"):
            demo.expect_rejection(lambda: None)

    def test_devcontainer_collects_both_test_roots(self) -> None:
        config = json.loads((ROOT / ".devcontainer/devcontainer.json").read_text(encoding="utf-8"))
        settings = config["customizations"]["vscode"]["settings"]
        self.assertTrue(settings["python.testing.pytestEnabled"])
        self.assertEqual(settings["python.testing.pytestArgs"], ["tests", "interop/tests"])


if __name__ == "__main__":
    unittest.main()
