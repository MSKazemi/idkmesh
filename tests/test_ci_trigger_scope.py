"""Regression tests for PR workflow trigger scope.

These tests protect a repository-level backpressure invariant: the one required
PR Gate stays unfiltered, while product/research workflows do not wake up for
unrelated connector changes.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _event_block(text: str, event: str) -> str:
    lines = text.splitlines()
    marker = f"  {event}:"
    start = next(
        index for index, line in enumerate(lines) if line.rstrip() == marker
    )
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            break
        body.append(line)
    return "\n".join(body)


def _paths(block: str) -> tuple[str, ...]:
    lines = block.splitlines()
    try:
        start = next(
            index for index, line in enumerate(lines) if line.strip() == "paths:"
        )
    except StopIteration:
        return ()

    result: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith("- "):
            break
        value = stripped[2:].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result.append(value)
    return tuple(result)


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


class WorkflowTriggerScopeTests(unittest.TestCase):
    def read(self, name: str) -> str:
        return (WORKFLOWS / name).read_text(encoding="utf-8")

    def test_pr_gate_remains_unfiltered_required_surface(self):
        block = _event_block(self.read("pr-gate.yml"), "pull_request")
        self.assertEqual(
            _paths(block),
            (),
            "PR Gate must remain unfiltered so it can be the stable required check",
        )

    def test_ci_shadow_planner_remains_unfiltered_advisory_surface(self):
        block = _event_block(self.read("ci-shadow-planner.yml"), "pull_request")
        self.assertEqual(
            _paths(block),
            (),
            "CI Shadow Planner intentionally observes every PR",
        )

    def test_randomness_lab_does_not_wake_for_unrelated_connector_tests(self):
        block = _event_block(self.read("randomness-lab.yml"), "pull_request")
        patterns = _paths(block)
        self.assertNotIn("tests/**", patterns)
        self.assertFalse(_matches("tests/test_connector_profiles.py", patterns))
        self.assertFalse(_matches("idkmesh/connector_profiles.py", patterns))
        self.assertTrue(_matches("tests/test_randomness_lab.py", patterns))
        self.assertTrue(_matches("tests/test_r1_replay.py", patterns))
        self.assertTrue(_matches("tests/test_r2_scale.py", patterns))
        self.assertTrue(_matches("tests/test_r3.py", patterns))
        self.assertTrue(_matches("randomness_lab/r1.py", patterns))

    def test_randomness_lab_push_validation_is_main_only(self):
        push_block = _event_block(self.read("randomness-lab.yml"), "push")
        self.assertIn(
            "branches: [main]",
            push_block,
            "feature branches already receive PR validation; do not duplicate the matrix",
        )

    def test_randomness_lab_uses_pytest_for_focused_scope(self):
        text = self.read("randomness-lab.yml")
        self.assertNotIn("python -m unittest discover", text)
        self.assertIn("python -m pytest -q", text)
        self.assertIn("tests/test_randomness_lab.py", text)
        self.assertIn("tests/test_r1_*.py", text)
        self.assertIn("tests/test_r2*.py", text)
        self.assertIn("tests/test_r3*.py", text)

    def test_gate_audit_selftest_ignores_connector_core_files(self):
        block = _event_block(
            self.read("gate-audit-action-selftest.yml"),
            "pull_request",
        )
        patterns = _paths(block)
        self.assertNotIn("idkmesh/**", patterns)
        self.assertFalse(_matches("idkmesh/connector_profiles.py", patterns))
        self.assertTrue(_matches("idkmesh/gate_audit.py", patterns))
        self.assertTrue(_matches("idkmesh/cli.py", patterns))
        self.assertTrue(_matches("actions/gate-audit/action.yml", patterns))

    def test_evolution_pr_head_verification_is_path_scoped(self):
        text = self.read("evolution-loop.yml")
        pr_patterns = _paths(_event_block(text, "pull_request"))
        target_patterns = _paths(_event_block(text, "pull_request_target"))

        self.assertTrue(pr_patterns)
        self.assertFalse(_matches("idkmesh/connector_profiles.py", pr_patterns))
        self.assertFalse(_matches("tests/test_connector_profiles.py", pr_patterns))
        self.assertTrue(_matches("scripts/evolution_score.py", pr_patterns))
        self.assertTrue(_matches("tests/test_evolution_math.py", pr_patterns))
        self.assertTrue(_matches("state/evolution-state.json", pr_patterns))

        self.assertEqual(
            target_patterns,
            (),
            "trusted pull_request_target observation must remain repository-wide",
        )


if __name__ == "__main__":
    unittest.main()
