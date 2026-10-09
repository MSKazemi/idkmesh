"""Pin issue #478's discoverability acceptance criterion for the paper artifacts.

The canonical manuscript source and its claim-to-evidence map live under
``paper/``, but a newcomer must be able to *find* them from an obvious project
index. That was the one acceptance criterion of issue #478 left unmet when the
artifacts landed: no document outside ``paper/`` linked to them. These tests
keep the index links in place so the manuscript cannot silently become
undiscoverable again.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = REPO_ROOT / "paper"
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

MANUSCRIPT = PAPER_DIR / "main.tex"
CLAIM_MAP = PAPER_DIR / "CLAIM_EVIDENCE_MAP.md"
PAPER_GUIDE = PAPER_DIR / "README.md"

# Project indexes that must link to the canonical manuscript artifacts,
# as (index file, link target) pairs. Relative targets are resolved relative to
# the index file, so a wrong number of ".." segments fails here too. A target
# under BLOB_PREFIX is resolved against the repository root instead: GitHub
# Pages publishes only docs/, so a relative link from docs/ to a non-Markdown
# file outside it (paper/main.tex) is a 404 on the site and must use the
# repository URL.
BLOB_PREFIX = "https://github.com/MSKazemi/idkmesh/blob/main/"
INDEX_LINKS = (
    (
        REPO_ROOT / "docs" / "research" / "README.md",
        BLOB_PREFIX + "paper/main.tex",
    ),
    (
        REPO_ROOT / "docs" / "research" / "README.md",
        "../../paper/CLAIM_EVIDENCE_MAP.md",
    ),
    (REPO_ROOT / "README.md", "paper/README.md"),
)


class PaperArtifactsExistTests(unittest.TestCase):
    def test_canonical_manuscript_artifacts_are_present(self):
        for path in (MANUSCRIPT, CLAIM_MAP, PAPER_GUIDE):
            with self.subTest(path=path.name):
                self.assertTrue(
                    path.is_file(),
                    f"{path.relative_to(REPO_ROOT)} is missing; the canonical "
                    f"manuscript artifacts must stay in paper/ (issue #478).",
                )


class PaperDiscoverabilityTests(unittest.TestCase):
    def test_project_indexes_link_to_the_manuscript(self):
        for index, target in INDEX_LINKS:
            with self.subTest(index=index.name, target=target):
                text = index.read_text(encoding="utf-8")
                self.assertIn(
                    f"]({target})",
                    text,
                    f"{index.relative_to(REPO_ROOT)} no longer links to "
                    f"{target}; issue #478 requires the canonical manuscript "
                    f"to be findable from a project index.",
                )
                if target.startswith(BLOB_PREFIX):
                    resolved = (REPO_ROOT / target[len(BLOB_PREFIX):]).resolve()
                else:
                    resolved = (index.parent / target).resolve()
                self.assertTrue(
                    resolved.is_file(),
                    f"{index.relative_to(REPO_ROOT)} links to {target} but it "
                    f"resolves to {resolved}, which is not a file.",
                )

    def test_claim_evidence_map_references_resolve(self):
        """Broken internal claim/evidence references must fail loudly.

        This is the lightweight maintenance check issue #478 asked for,
        scoped to the claim map: every repository-relative link it carries
        must point at a tracked file.
        """
        tracked = set(
            subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split("\0")
        )
        broken = []
        for target in LINK_RE.findall(CLAIM_MAP.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            resolved = (PAPER_DIR / target.split("#", 1)[0]).resolve()
            try:
                relative = resolved.relative_to(REPO_ROOT.resolve()).as_posix()
            except ValueError:
                broken.append(f"{target} (escapes the repository)")
                continue
            if relative not in tracked:
                broken.append(target)
        self.assertEqual(
            [],
            broken,
            f"paper/CLAIM_EVIDENCE_MAP.md references files not in the Git "
            f"index: {broken}",
        )


if __name__ == "__main__":
    unittest.main()
