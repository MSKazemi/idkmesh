"""Guard the newcomer demo in ``scripts/demo.py``.

The demo is the first thing a new contributor runs, so a broken or silently
weakened demo is a contributor-facing regression. It is also the only place
where the three acceptance rules are asserted together as one story, so these
tests keep it honest: it must still reject a self-accepting worker, a verifier
that is the worker, and a verification whose provenance does not bind.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

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
    def test_quiet_run_succeeds(self) -> None:
        result = run_demo("--quiet")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3 accepted, 3 rejected", result.stdout)

    def test_narrated_run_tells_the_whole_story(self) -> None:
        result = run_demo()
        self.assertEqual(result.returncode, 0, result.stderr)
        # Every act must appear, so a silently truncated demo fails here.
        for act in range(1, 7):
            self.assertIn(f"  {act}. ", result.stdout, f"act {act} missing")
        self.assertEqual(result.stdout.count("ACCEPTED"), 1)
        self.assertEqual(result.stdout.count("REJECTED"), 3)

    def test_demo_fails_when_self_acceptance_is_allowed(self) -> None:
        """Red-green: if the contract stops rejecting self-acceptance, the demo must break."""
        original = SELF_ACCEPTED.read_text(encoding="utf-8")
        weakened = json.loads(original)
        removed = weakened.pop("accepted", None)
        self.assertIsNotNone(
            removed,
            "fixture no longer carries the 'accepted' key this test mutates",
        )
        try:
            SELF_ACCEPTED.write_text(
                json.dumps(weakened, indent=2) + "\n", encoding="utf-8"
            )
            result = run_demo("--quiet")
            self.assertNotEqual(
                result.returncode,
                0,
                "demo passed even though a self-accepting worker was accepted",
            )
        finally:
            SELF_ACCEPTED.write_text(original, encoding="utf-8")

        # The fixture must be byte-identical again, or the suite has a side effect.
        self.assertEqual(SELF_ACCEPTED.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
