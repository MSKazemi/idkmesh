"""Tests for tools/schema_compat_check.py (issue #737's backward-compat gate).

``diff_schema`` is exercised directly against synthetic before/after pairs
(no git needed) to pin the exact rule set. ``check_file``/``check_tree`` are
exercised against this repository's own real git history -- two already-
committed breaking changes and one already-committed compatible widening --
so the test suite doubles as the evidence that justified the rule set,
not just an assertion against the implementation's own behavior.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import schema_compat_check as sc


def _base(**overrides) -> dict:
    doc = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://idkmesh.org/schemas/example-v0.1.schema.json",
        "title": "Example",
        "type": "object",
        "additionalProperties": False,
        "required": ["kind"],
        "properties": {
            "kind": {"const": "example"},
            "state": {"enum": ["a", "b"]},
        },
    }
    doc.update(overrides)
    return doc


class DiffSchemaTests(unittest.TestCase):
    def test_identical_documents_are_compatible(self) -> None:
        doc = _base()
        self.assertEqual(sc.diff_schema(doc, json.loads(json.dumps(doc))), [])

    def test_removed_top_level_property_is_breaking(self) -> None:
        old = _base()
        new = _base(properties={"kind": old["properties"]["kind"]})
        violations = sc.diff_schema(old, new)
        self.assertTrue(any("state" in v and "removed" in v for v in violations))

    def test_gained_required_field_is_breaking(self) -> None:
        old = _base()
        new = _base(required=["kind", "state"])
        violations = sc.diff_schema(old, new)
        self.assertTrue(any("required changed" in v for v in violations))
        self.assertTrue(any("gained required" in v for v in violations))

    def test_lost_required_field_is_breaking(self) -> None:
        old = _base(required=["kind", "state"])
        new = _base(required=["kind"])
        violations = sc.diff_schema(old, new)
        self.assertTrue(any("lost required" in v for v in violations))

    def test_additional_properties_flip_is_breaking(self) -> None:
        old = _base()
        new = _base(additionalProperties=True)
        violations = sc.diff_schema(old, new)
        self.assertTrue(any("additionalProperties changed" in v for v in violations))

    def test_const_change_is_breaking(self) -> None:
        old = _base()
        new = _base(
            properties={
                "kind": {"const": "example-renamed"},
                "state": old["properties"]["state"],
            }
        )
        violations = sc.diff_schema(old, new)
        self.assertTrue(any("properties/kind: schema changed" in v for v in violations))

    def test_enum_narrowing_is_breaking(self) -> None:
        old = _base()
        new = _base(
            properties={
                "kind": old["properties"]["kind"],
                "state": {"enum": ["a"]},
            }
        )
        violations = sc.diff_schema(old, new)
        self.assertTrue(any("properties/state: schema changed" in v for v in violations))

    def test_enum_widening_is_compatible(self) -> None:
        old = _base()
        new = _base(
            properties={
                "kind": old["properties"]["kind"],
                "state": {"enum": ["a", "b", "c"]},
            }
        )
        self.assertEqual(sc.diff_schema(old, new), [])

    def test_type_widening_is_compatible(self) -> None:
        old = _base(
            properties={"kind": _base()["properties"]["kind"], "note": {"type": "string"}}
        )
        new = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "note": {"type": ["string", "null"]},
            }
        )
        self.assertEqual(sc.diff_schema(old, new), [])

    def test_type_narrowing_is_breaking(self) -> None:
        old = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "note": {"type": ["string", "null"]},
            }
        )
        new = _base(
            properties={"kind": _base()["properties"]["kind"], "note": {"type": "string"}}
        )
        violations = sc.diff_schema(old, new)
        self.assertTrue(any("properties/note: schema changed" in v for v in violations))

    def test_new_optional_property_is_compatible(self) -> None:
        old = _base()
        new = _base(
            properties={**old["properties"], "extra": {"type": "string"}}
        )
        self.assertEqual(sc.diff_schema(old, new), [])

    def test_description_only_change_is_compatible(self) -> None:
        old = _base()
        new = _base()
        new["description"] = "a friendlier description"
        self.assertEqual(sc.diff_schema(old, new), [])

    def test_nested_object_required_change_is_breaking(self) -> None:
        old = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "budget": {
                    "type": "object",
                    "properties": {"wall_seconds": {"type": "number"}},
                },
            }
        )
        new = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "budget": {
                    "type": "object",
                    "properties": {"wall_seconds": {"type": "number"}},
                    "required": ["wall_seconds"],
                },
            }
        )
        violations = sc.diff_schema(old, new)
        self.assertTrue(
            any("properties/budget: required changed" in v for v in violations)
        )

    def test_nested_object_removed_entirely_is_breaking(self) -> None:
        old = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "budget": {
                    "type": "object",
                    "properties": {"wall_seconds": {"type": "number"}},
                },
            }
        )
        new = _base(properties={"kind": _base()["properties"]["kind"]})
        violations = sc.diff_schema(old, new)
        self.assertTrue(
            any("properties/budget" in v and "removed" in v for v in violations)
        )


    def test_anchor_hardening_is_compatible(self) -> None:
        old = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "slug": {"type": "string", "pattern": "^abc$"},
            }
        )
        new = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "slug": {"type": "string", "pattern": "^abc$" + sc.ANCHOR_SUFFIX},
            }
        )
        self.assertEqual(sc.diff_schema(old, new), [])

    def test_nested_anchor_hardening_is_compatible(self) -> None:
        old = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "tags": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^abc$"},
                },
                "ref": {
                    "anyOf": [
                        {"type": "string", "pattern": "^abc$"},
                        {"type": "integer"},
                    ]
                },
            }
        )
        new = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "tags": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": "^abc$" + sc.ANCHOR_SUFFIX,
                    },
                },
                "ref": {
                    "anyOf": [
                        {
                            "type": "string",
                            "pattern": "^abc$" + sc.ANCHOR_SUFFIX,
                        },
                        {"type": "integer"},
                    ]
                },
            }
        )
        self.assertEqual(sc.diff_schema(old, new), [])

    def test_hardening_plus_any_other_change_is_breaking(self) -> None:
        old = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "slug": {"type": "string", "pattern": "^abc$", "maxLength": 8},
            }
        )
        new = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "slug": {
                    "type": "string",
                    "pattern": "^abc$" + sc.ANCHOR_SUFFIX,
                    "maxLength": 9,
                },
            }
        )
        violations = sc.diff_schema(old, new)
        self.assertTrue(any("properties/slug: schema changed" in v for v in violations))

        # A recognized widening riding along with the hardening in the
        # same leaf stays breaking: the exact mechanical form, with
        # nothing else changing in that subschema, is the only thing
        # recognized.
        old = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "state": {
                    "type": "string",
                    "enum": ["a", "b"],
                    "pattern": "^abc$",
                },
            }
        )
        new = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "state": {
                    "type": "string",
                    "enum": ["a", "b", "c"],
                    "pattern": "^abc$" + sc.ANCHOR_SUFFIX,
                },
            }
        )
        violations = sc.diff_schema(old, new)
        self.assertTrue(any("properties/state: schema changed" in v for v in violations))

    def test_other_pattern_changes_are_still_breaking(self) -> None:
        changed_leaves = {
            "body changed": {
                "type": "string",
                "pattern": "^ab$" + sc.ANCHOR_SUFFIX,
            },
            "double hardened": {
                "type": "string",
                "pattern": "^abc$" + sc.ANCHOR_SUFFIX + sc.ANCHOR_SUFFIX,
            },
            "suffix without anchor": {
                "type": "string",
                "pattern": "^abc" + sc.ANCHOR_SUFFIX,
            },
        }
        for label, changed in changed_leaves.items():
            with self.subTest(label):
                old = _base(
                    properties={
                        "kind": _base()["properties"]["kind"],
                        "slug": {"type": "string", "pattern": "^abc$"},
                    }
                )
                new = _base(
                    properties={
                        "kind": _base()["properties"]["kind"],
                        "slug": changed,
                    }
                )
                violations = sc.diff_schema(old, new)
                self.assertTrue(
                    any("properties/slug: schema changed" in v for v in violations),
                    violations,
                )

    def test_escaped_literal_dollar_is_not_an_anchor(self) -> None:
        # "cost\\$" is a literal dollar sign, not an end anchor; appending
        # the guard would silently change what the pattern is anchored to,
        # so only a real end anchor may be hardened.
        old = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "price": {"type": "string", "pattern": "cost\\$"},
            }
        )
        new = _base(
            properties={
                "kind": _base()["properties"]["kind"],
                "price": {
                    "type": "string",
                    "pattern": "cost\\$" + sc.ANCHOR_SUFFIX,
                },
            }
        )
        violations = sc.diff_schema(old, new)
        self.assertTrue(any("properties/price: schema changed" in v for v in violations))


class RealHistoryTests(unittest.TestCase):
    """Exercise check_file against this repository's own committed history."""

    def _git_ok(self, *args: str) -> bool:
        return (
            subprocess.run(
                ["git", *args], cwd=ROOT, capture_output=True, check=False
            ).returncode
            == 0
        )

    def setUp(self) -> None:
        if not self._git_ok("cat-file", "-e", "c6ebb4b~1"):
            raise unittest.SkipTest("shallow clone: c6ebb4b~1 unavailable")

    def test_known_historical_required_narrowing_is_flagged(self) -> None:
        violations = sc.check_file(
            "schemas/work-unit-v0.2.schema.json", "c6ebb4b~1"
        )
        self.assertTrue(
            any("required changed" in v for v in violations), violations
        )

    def test_known_historical_enum_widening_is_not_flagged(self) -> None:
        if not self._git_ok("cat-file", "-e", "dcdab66~1"):
            self.skipTest("shallow clone: dcdab66~1 unavailable")
        violations = sc.check_file(
            "schemas/search-visibility-observation-v0.1.schema.json", "dcdab66~1"
        )
        self.assertEqual(violations, [])

    def test_new_file_at_base_has_no_violations(self) -> None:
        # A schema that did not exist at the base ref has nothing to
        # compare against; check_file must treat it as compatible, not
        # raise, matching "a brand-new file is never a violation."
        violations = sc.check_file(
            "schemas/idkmesh-control-tower-run-attempts-response-v0.1.schema.json",
            "c6ebb4b~1",
        )
        self.assertEqual(violations, [])


class CliTests(unittest.TestCase):
    def test_self_compare_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "schema_compat_check.py"), "--base", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no breaking changes", result.stdout)

    def test_json_output_is_well_formed(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "schema_compat_check.py"),
                "--base",
                "HEAD",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["violations"], {})
        self.assertEqual(payload["base"], "HEAD")

    def test_detects_a_real_breaking_change_end_to_end(self) -> None:
        # Mutates a real committed schema file on disk, in this worktree,
        # to exercise the exact on-disk path CI runs -- so it must restore
        # the original bytes in `finally` and then verify the restore
        # actually landed, not just trust that the write succeeded.
        schema_path = ROOT / "schemas" / "idkmesh-list-v0.1.schema.json"
        original = schema_path.read_text(encoding="utf-8")
        doc = json.loads(original)
        doc["required"] = [f for f in doc["required"] if f != "items"]
        try:
            schema_path.write_text(
                json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "schema_compat_check.py"),
                    "--base",
                    "HEAD",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("idkmesh-list-v0.1.schema.json", result.stdout)
            self.assertIn("required changed", result.stdout)
        finally:
            schema_path.write_text(original, encoding="utf-8")
        self.assertEqual(schema_path.read_text(encoding="utf-8"), original)

    def test_unresolvable_base_without_explicit_flag_fails_closed(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "schema_compat_check.py"),
                "--base",
                "not-a-real-ref-xyz",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        # A ref that does not resolve makes every git show fail the same way
        # a missing file would (returns None), which is silently wrong --
        # confirm this actually surfaces as a real argparse/git-level error
        # rather than a false "no breaking changes".
        self.assertNotIn("no breaking changes", result.stdout)


if __name__ == "__main__":
    unittest.main()
