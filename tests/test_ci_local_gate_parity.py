"""Guard the PR Gate against re-inlining logic that developers cannot run locally.

The Markdown link check once lived inside `.github/workflows/pr-gate.yml` as an
inline `python - <<'PY'` heredoc. That shape has two defects: nobody can execute
it before pushing, so the first feedback is a red PR; and nothing keeps it in
step with whatever a developer checks by hand, so the two drift apart silently.

It now lives in `scripts/check_links.py`, which both CI and
`scripts/testkit.py integration` invoke. This test pins that arrangement so the
heredoc cannot quietly come back.

Deliberately text-based rather than YAML-parsed: the PR Gate installs only
`pytest` and `requirements-phase0.txt`, which does not include PyYAML, so an
`import yaml` here would pass locally and fail in the very gate it describes.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PR_GATE = ROOT / ".github" / "workflows" / "pr-gate.yml"

# The scripts the PR Gate is expected to delegate to rather than inline.
SHARED_GATE_SCRIPTS = ("scripts/check_links.py",)

HEREDOC = re.compile(r"python3?\s+-\s+<<", re.M)


class CiLocalGateParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(PR_GATE.is_file(), f"missing workflow: {PR_GATE}")
        self.text = PR_GATE.read_text(encoding="utf-8")

    def test_pr_gate_delegates_to_the_shared_scripts(self) -> None:
        for script in SHARED_GATE_SCRIPTS:
            with self.subTest(script=script):
                self.assertIn(
                    script,
                    self.text,
                    f"pr-gate.yml no longer invokes {script}; CI and the local "
                    f"gate must run the same file, not two copies of the logic.",
                )
                self.assertTrue(
                    (ROOT / script).is_file(),
                    f"pr-gate.yml references {script}, which does not exist.",
                )

    def test_pr_gate_contains_no_inline_python_heredoc(self) -> None:
        matches = HEREDOC.findall(self.text)
        self.assertEqual(
            matches,
            [],
            "pr-gate.yml contains an inline Python heredoc. Logic in the "
            "required check must live in a script under scripts/ so it can be "
            "run locally before pushing.",
        )

    def test_shared_scripts_are_runnable_without_third_party_packages(self) -> None:
        """The gate runs before `pip install`, so these must be stdlib-only."""
        third_party = {"yaml", "jsonschema", "pytest", "numpy", "scipy", "requests"}
        for script in SHARED_GATE_SCRIPTS:
            source = (ROOT / script).read_text(encoding="utf-8")
            imported = set(
                re.findall(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", source, re.M)
            )
            with self.subTest(script=script):
                self.assertEqual(
                    imported & third_party,
                    set(),
                    f"{script} imports a third-party package; it must stay "
                    f"stdlib-only so it runs on a bare checkout.",
                )


if __name__ == "__main__":
    unittest.main()
