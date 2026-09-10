from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# Jekyll builds docs/ with Liquid, which expands these delimiters *before*
# Markdown runs. A fenced code block therefore does NOT protect them, and one
# unparseable expression fails the build for the entire site rather than for the
# page containing it.
LIQUID_TOKEN = re.compile(r"\{\{|\{%")
RAW_REGION = re.compile(r"\{%\s*raw\s*%\}.*?\{%\s*endraw\s*%\}", re.S)


def unprotected_tokens(text: str) -> list[tuple[int, str]]:
    """Liquid delimiters outside a raw region, with 1-based line numbers."""
    outside = RAW_REGION.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return [
        (outside[: m.start()].count("\n") + 1, outside[m.start() : m.start() + 60].split("\n")[0])
        for m in LIQUID_TOKEN.finditer(outside)
    ]


def markdown_sources() -> list[Path]:
    return sorted(DOCS.rglob("*.md"))


class PagesLiquidSafetyTests(unittest.TestCase):
    """No published Markdown page may carry an unwrapped Liquid delimiter.

    This is not hypothetical. `docs/architecture/REPOSITORY_MATHEMATICAL_PORTFOLIO_CONCURRENCY.md`
    documented a GitHub Actions concurrency expression inside a ```yaml fence.
    Liquid read the Actions interpolation as one of its own variables, could not
    find a terminator, and every Pages deployment from 2026-09-09T23:53Z onward
    failed -- six consecutive builds, 7307b41 through c798726 -- while every
    repository test stayed green. The last successful build was f4142f9.
    """

    def test_no_markdown_page_carries_an_unwrapped_liquid_delimiter(self) -> None:
        offenders: list[str] = []
        for path in markdown_sources():
            text = path.read_text(encoding="utf-8", errors="replace")
            for line, snippet in unprotected_tokens(text):
                offenders.append(f"{path.relative_to(ROOT)}:{line}: {snippet}")

        self.assertEqual(
            offenders,
            [],
            "these would fail the Jekyll build for the whole site; wrap the block "
            "in a Liquid raw region (and keep delimiters out of HTML comments, "
            f"which Liquid also parses):\n" + "\n".join(offenders),
        )

    def test_every_raw_region_is_closed(self) -> None:
        unbalanced: list[str] = []
        for path in markdown_sources():
            text = path.read_text(encoding="utf-8", errors="replace")
            opens = len(re.findall(r"\{%\s*raw\s*%\}", text))
            closes = len(re.findall(r"\{%\s*endraw\s*%\}", text))
            if opens != closes:
                unbalanced.append(f"{path.relative_to(ROOT)}: {opens} open, {closes} close")

        self.assertEqual(unbalanced, [], f"unbalanced raw regions: {unbalanced}")

    def test_the_scan_actually_reaches_the_published_tree(self) -> None:
        """Guard the guard: an empty file list would make both checks vacuous."""
        self.assertGreater(
            len(markdown_sources()),
            100,
            "docs/ Markdown scan found almost nothing; the checks above would pass "
            "while testing nothing",
        )


if __name__ == "__main__":
    unittest.main()
