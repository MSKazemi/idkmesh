"""T1/E047: SWE-bench submission provenance parsing and the provenance-aware selectors."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import submission_provenance as e047  # noqa: E402

NEW_FORMAT = """assets:
  logs: s3://bucket/logs
info:
  model_release_date: 20251118
  logo:
  - https://example.org/logo.svg
  name: Gemini 3 Pro
tags:
  checked: null
  model:
  - gemini-3-pro-preview
  org: Google DeepMind
  os_model: false
  system:
    attempts: 1
  agent: mini-SWE-agent
  agent_org: SWE-agent
  model_display: Gemini 3 Pro
  model_org: Google DeepMind
"""

OLD_FORMAT = """info:
  name: Factory Code Droid
tags:
  checked: false
  org: ''
  system:
    attempts: 2+
  agent: Factory Code Droid
  model_display: Undisclosed
warning: true
"""


class ParseTests(unittest.TestCase):
    def test_new_format_reads_nested_lists_and_scalars(self) -> None:
        record = e047.parse_metadata(NEW_FORMAT)
        self.assertEqual(record["model"], ["gemini-3-pro-preview"])
        self.assertEqual(record["model_org"], "Google DeepMind")
        self.assertEqual(record["agent"], "mini-SWE-agent")
        self.assertEqual(record["attempts"], "1")

    def test_old_format_without_a_model_list_and_an_undisclosed_model(self) -> None:
        record = e047.parse_metadata(OLD_FORMAT)
        self.assertIsNone(record["model"])
        self.assertIsNone(record["org"])
        self.assertEqual(record["attempts"], "2+")
        self.assertIsNone(e047.primary_model(record))

    def test_model_aliases_collapse_to_one_identity(self) -> None:
        names = [
            {"model": ["claude-3-opus-20240229"]},
            {"model_display": "Claude 3 Opus"},
            {"model": ["anthropic/claude-3.opus"]},
            {"model": ["claude-opus-3-latest"]},
        ]
        self.assertEqual({e047.primary_model(n) for n in names}, {"3-claude-opus"})
        self.assertIsNone(e047.primary_model({"model": ["[]"]}))
        self.assertIsNone(e047.primary_model({"model_display": "mixed models"}))


class SelectionTests(unittest.TestCase):
    def test_one_per_model_keeps_the_first_name_and_every_unknown(self) -> None:
        provenance = {"b": {"model": ["m1"]}, "a": {"model": ["m1"]}, "c": {"model": ["m2"]}, "d": {}, "e": {}}
        kept, unknown = e047.one_per_model(["e", "d", "c", "b", "a"], provenance)
        self.assertEqual(kept, ["a", "c", "d", "e"])
        self.assertEqual(unknown, 2)

    def test_one_per_org_skips_a_second_submission_from_the_same_organisation(self) -> None:
        rows = {"x1": frozenset({1, 2, 3}), "x2": frozenset({1, 2}), "y": frozenset({4})}
        provenance = {"x1": {"model_org": "X"}, "x2": {"model_org": "x"}, "y": {"model_org": "Y"}}
        chosen = e047.select_top_k_one_per_org(rows, sorted(rows), frozenset({1, 2, 3, 4}), 2, provenance)
        self.assertEqual(chosen, ["x1", "y"])


if __name__ == "__main__":
    unittest.main()
