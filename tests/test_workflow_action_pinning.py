"""Every third-party GitHub Action must be pinned to an immutable commit SHA.

A floating tag such as ``actions/checkout@v4`` resolves at run time to whatever
the tag points at *now*. Whoever controls the tag can change what runs in CI
without any change landing in this repository, and CI here has repository write
scope in some workflows. Issue 12's safety checklist names this directly:
"pin the action by immutable reviewed SHA".

The repository already pinned 104 of 134 action uses this way. This test exists
so the remaining 30 cannot quietly come back: a tag is easy to reintroduce by
copying an example from upstream documentation, and nothing else in the tree
would notice.
"""

from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

USES_RE = re.compile(r"uses:\s*(?P<ref>[^\s#]+)")
SHA_RE = re.compile(r"\A[0-9a-f]{40}\Z")


def _external_uses():
    """Yield ``(path, line_number, ref)`` for every non-local ``uses:``."""

    for path in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            match = USES_RE.search(line)
            if match is None:
                continue
            ref = match.group("ref")
            # A local action or reusable workflow is versioned by this commit.
            if ref.startswith("./") or ref.startswith("docker://"):
                continue
            yield path, number, ref


class WorkflowActionPinningTest(unittest.TestCase):
    def test_there_is_something_to_check(self):
        self.assertTrue(
            WORKFLOWS.is_dir(), f"{WORKFLOWS} is missing; the guard would pass vacuously"
        )
        self.assertGreater(
            len(list(_external_uses())),
            0,
            "no external action uses were found; the parser is probably broken",
        )

    def test_every_external_action_is_pinned_to_a_sha(self):
        unpinned = []
        for path, number, ref in _external_uses():
            version = ref.rpartition("@")[2]
            if "@" not in ref or not SHA_RE.match(version):
                unpinned.append(f"{path.relative_to(ROOT)}:{number}: {ref}")
        self.assertEqual(
            unpinned,
            [],
            "these action references are not pinned to an immutable commit SHA:\n  "
            + "\n  ".join(unpinned),
        )

    def test_one_action_is_not_pinned_to_conflicting_shas_for_one_version(self):
        """A version comment that maps to two SHAs means one of them is stale."""

        seen: dict[tuple[str, str], set[str]] = {}
        pattern = re.compile(
            r"uses:\s*(?P<name>[^\s@#]+)@(?P<sha>[0-9a-f]{40})\s*#\s*(?P<version>\S+)"
        )
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for line in path.read_text(encoding="utf-8").splitlines():
                match = pattern.search(line)
                if match is None:
                    continue
                key = (match.group("name"), match.group("version"))
                seen.setdefault(key, set()).add(match.group("sha"))
        conflicts = {k: sorted(v) for k, v in seen.items() if len(v) > 1}
        self.assertEqual(
            conflicts, {}, f"one version comment maps to several SHAs: {conflicts}"
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
