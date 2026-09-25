"""Every schema's `$id` and `title` must be a unique, checkable identity.

Issue #877/#878: `schemas/enterprise-control-profile-v0.1.schema.json` and
`schemas/enterprise-control-profile-baseline-v0.1.schema.json` shared the
title "IDKMesh Enterprise Control Profile v0.1" and `$id` values that
differed only in host (`idkmesh.org` vs. `idkmesh.dev`), while the two
contracts are mutually incompatible -- validating one schema's example
against the other schema produced 39 errors. Nothing in the repository
detected this: a search for '$id' across tests/*.py returned nothing
before this file, and `tests/test_example_contract_coverage.py` only ever
checks example -> schema pairs, never schema identity itself.

These checks need only the standard library, so unlike
`tests/test_schema_validity.py` they are not guarded behind a `jsonschema`
availability check and run in every test job.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"


def schema_files() -> list[Path]:
    return sorted(SCHEMA_DIR.glob("*.schema.json"))


class SchemaIdentityTests(unittest.TestCase):
    def test_the_schema_directory_is_not_empty(self) -> None:
        """Guard the guard: a bad glob would make every check below vacuous."""
        self.assertGreater(
            len(schema_files()),
            0,
            f"no schemas found in {SCHEMA_DIR}; this guard is checking nothing.",
        )

    def test_every_schema_declares_a_nonempty_id(self) -> None:
        for path in schema_files():
            with self.subTest(schema=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                schema_id = document.get("$id")
                self.assertTrue(
                    isinstance(schema_id, str) and schema_id.strip(),
                    f"{path.name} has no non-empty '$id'.",
                )

    def test_every_schema_id_is_globally_unique(self) -> None:
        by_id: dict[str, list[str]] = {}
        for path in schema_files():
            document = json.loads(path.read_text(encoding="utf-8"))
            schema_id = document.get("$id")
            by_id.setdefault(schema_id, []).append(path.name)

        collisions = {
            schema_id: names for schema_id, names in by_id.items() if len(names) > 1
        }
        self.assertEqual(
            collisions,
            {},
            f"multiple schemas share the same '$id': {collisions}. "
            "Two incompatible contracts must never claim the same identity.",
        )

    def test_every_schema_id_path_matches_its_filename(self) -> None:
        for path in schema_files():
            with self.subTest(schema=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                schema_id = document["$id"]
                id_basename = os.path.basename(urlparse(schema_id).path)
                self.assertEqual(
                    id_basename,
                    path.name,
                    f"{path.name} has '$id' {schema_id!r} whose path ends in "
                    f"{id_basename!r}, not the schema's own filename.",
                )

    def test_every_schema_title_is_unique(self) -> None:
        by_title: dict[str, list[str]] = {}
        for path in schema_files():
            document = json.loads(path.read_text(encoding="utf-8"))
            title = document.get("title")
            by_title.setdefault(title, []).append(path.name)

        collisions = {
            title: names for title, names in by_title.items() if len(names) > 1
        }
        self.assertEqual(
            collisions,
            {},
            f"multiple schemas share the same 'title': {collisions}. "
            "A title is how reviewers resolve 'the ... schema' by hand; it "
            "must not point at more than one contract.",
        )


if __name__ == "__main__":
    unittest.main()
