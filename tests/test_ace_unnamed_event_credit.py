from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ace-community-growth.yml"

# Events the dispatch chain names explicitly. Anything else must reach the
# terminal else.
CHAIN_RE = re.compile(r"event === '([a-z_]+)'")
SEED_RE = re.compile(r"let q = ([\d.]+), d = ([\d.]+), r = ([\d.]+);")
# The else body contains a template literal (``${event}``) whose closing brace
# defeats a naive "up to the next }" match, so scan a bounded window instead.
ELSE_RE = re.compile(
    r"\}\s*else\s*\{[^\n]*\n.{0,800}?"
    r"q\s*=\s*([\d.]+);\s*d\s*=\s*([\d.]+);\s*r\s*=\s*([\d.]+);",
    re.S,
)


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def declared_triggers(text: str) -> set[str]:
    """Event names in the workflow's ``on:`` block."""
    block = re.search(r"^on:\n(.*?)^\w", text, re.S | re.M)
    assert block, "no on: block found"
    return set(re.findall(r"^  ([a-z_]+):", block.group(1), re.M))


class UnnamedEventCreditTests(unittest.TestCase):
    """An event the dispatch chain does not name must not award credit.

    ``credit`` selects the controller's mode (EXPLORE at 2, GROW at 8), so an
    event that adds credit is voting on the repository's growth policy. The
    chain seeds ``q``/``d``/``r`` before branching, so before the terminal else
    existed a ``workflow_dispatch`` run -- and any ``schedule:`` trigger added
    later -- kept those seeds and both scored and opened its own row in the
    published counts table.
    """

    def test_the_chain_ends_in_a_zero_credit_else(self) -> None:
        match = ELSE_RE.search(workflow_text())

        self.assertIsNotNone(
            match,
            "the dispatch chain has no terminal else assigning q, d and r; an "
            "unnamed event would fall through carrying the seed values",
        )
        self.assertEqual(
            [float(g) for g in match.groups()],
            [0.0, 0.0, 0.0],
            "the terminal else must zero q, d and r so an unnamed event scores 0",
        )

    def test_every_declared_trigger_is_named_or_falls_through_to_zero(self) -> None:
        text = workflow_text()
        named = set(CHAIN_RE.findall(text))

        unnamed = sorted(declared_triggers(text) - named)

        # Unnamed triggers are allowed, but only because the else zeroes them.
        self.assertIsNotNone(
            ELSE_RE.search(text),
            f"these triggers are not named by the chain and there is no "
            f"zero-credit else to catch them: {unnamed}",
        )

    def test_the_seed_values_are_the_ones_the_else_protects_against(self) -> None:
        seed = SEED_RE.search(workflow_text())

        self.assertIsNotNone(seed, "the q/d/r seed assignment moved or changed shape")
        self.assertNotEqual(
            [float(g) for g in seed.groups()],
            [0.0, 0.0, 0.0],
            "the seed is now zero, so this guard no longer proves anything; either "
            "restore a non-zero seed or delete this test deliberately",
        )


if __name__ == "__main__":
    unittest.main()
