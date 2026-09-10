from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Paths that carry local configuration, personal notes or secrets. This is a
# public repository, so a single `git add -A` that picked one of these up would
# publish it irreversibly. Measured on 2026-09-10: none of these were ignored,
# and `CLAUDE.md` was already present untracked in the working tree.
MUST_BE_IGNORED = (
    "CLAUDE.md",
    "GEMINI.md",
    ".note",
    ".note.md",
    ".env",
    ".env.local",
    "settings.local",
    ".vscode/settings.json",
    ".DS_Store",
    ".claude/memory/MEMORY.md",
)

# AGENTS.md is the public agents.md contributor standard and is deliberately
# tracked. Ignoring it alongside CLAUDE.md would silently drop the one file
# every coding agent reads, so the exception is asserted, not assumed.
MUST_NOT_BE_IGNORED = (
    "AGENTS.md",
    "README.md",
    "CONTRIBUTING.md",
)


def check_ignore(relative_path: str) -> bool:
    """Return whether git itself ignores ``relative_path``.

    The verdict comes from git rather than from parsing ``.gitignore``, because
    the question the repository actually cares about is what ``git add`` would
    do. A missing git binary raises instead of skipping: a privacy guard that
    quietly does not run is worse than no guard at all.
    """
    completed = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "--", relative_path],
        cwd=ROOT,
        capture_output=True,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(
            f"git check-ignore failed for {relative_path!r} "
            f"(exit {completed.returncode}): {completed.stderr.decode().strip()}"
        )
    return completed.returncode == 0


class PrivateFileIgnoreTests(unittest.TestCase):
    def test_private_paths_are_ignored(self) -> None:
        leaking = [path for path in MUST_BE_IGNORED if not check_ignore(path)]

        self.assertEqual(
            leaking,
            [],
            f"these private paths would be committed by `git add -A`: {leaking}",
        )

    def test_public_contributor_files_are_not_ignored(self) -> None:
        hidden = [path for path in MUST_NOT_BE_IGNORED if check_ignore(path)]

        self.assertEqual(
            hidden,
            [],
            f"these public files must stay committable: {hidden}",
        )


class GitignoreContentTests(unittest.TestCase):
    def test_agents_md_exception_is_documented(self) -> None:
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("CLAUDE.md", text)
        self.assertIn(
            "AGENTS.md is deliberately NOT ignored",
            text,
            "the reason AGENTS.md is excluded must stay next to the rule, or a "
            "future edit will 'tidy' it into the ignore list",
        )


if __name__ == "__main__":
    unittest.main()
