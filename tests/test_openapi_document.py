"""The checked-in OpenAPI document stays complete and resolvable.

Issue #737 / API_CONVENTIONS_V0_1.md section 19: OpenAPI references the
canonical JSON Schemas instead of redefining them, and unresolved references
must fail CI. `openapi.yaml` is that checked-in document; these tests keep it
present, structured, and covering every public contract in `schemas/`.

Deliberately text-based rather than YAML-parsed, the same constraint recorded in
``tests/test_evolution_observer_concurrency.py`` and
``tests/test_ci_local_gate_parity.py``: the PR Gate installs only ``pytest`` and
``requirements-phase0.txt`` (jsonschema alone), so ``import yaml`` would pass
locally and silently skip in the gate -- and a whole-tree job that skips a check
is exactly the coverage loss ``tests/test_full_suite_jobs_install_requirements.py``
exists to prevent. An earlier form of this file guarded ``import yaml`` and was
therefore skipped in every CI job while reporting green; these checks now run
wherever the tree runs.

Structure is read through ``parse_block_mapping``, the standard-library
block-mapping parser that ``tests/test_api_contract_conformance.py`` already
uses to read this same document in CI. Reusing that parser rather than
``tools/openapi_ref_check.py`` is deliberate: the two scan the document
differently, so they fail differently rather than agreeing by construction.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_api_contract_conformance import parse_block_mapping

OPENAPI = ROOT / "openapi.yaml"
SCHEMAS = ROOT / "schemas"

EXTERNAL_REF = re.compile(r"https://idkmesh\.org/schemas/([A-Za-z0-9._-]+\.schema\.json)")
# Any internal JSON pointer this document declares, from any nesting.
INTERNAL_REF_VALUE = re.compile(r"\$ref\s*:\s*[\"']?(#/[^^\s\"'\}]+)")


def schema_filenames() -> set[str]:
    return {path.name for path in SCHEMAS.glob("*.schema.json")}


def load_document() -> dict:
    return parse_block_mapping(OPENAPI.read_text(encoding="utf-8"))


class OpenapiDocumentPresenceTests(unittest.TestCase):
    def test_openapi_document_exists_at_the_repository_root(self) -> None:
        self.assertTrue(OPENAPI.is_file(), "openapi.yaml is missing from the repository root")

    def test_every_public_schema_is_referenced(self) -> None:
        text = OPENAPI.read_text(encoding="utf-8")
        missing = sorted(name for name in schema_filenames() if name not in text)
        self.assertEqual(
            [], missing,
            f"openapi.yaml does not reference these schemas/: {missing}. "
            "Every public schema must be reachable from the catalog.",
        )

    def test_every_referenced_schema_resolves_to_a_file(self) -> None:
        text = OPENAPI.read_text(encoding="utf-8")
        referenced = set(EXTERNAL_REF.findall(text))
        unresolved = sorted(referenced - schema_filenames())
        self.assertEqual(
            [], unresolved,
            f"openapi.yaml references schemas that do not exist: {unresolved}. "
            "An unresolved reference must fail here, not at consumer build time.",
        )

    def test_the_schema_directory_scan_is_not_vacuous(self) -> None:
        self.assertGreaterEqual(
            len(schema_filenames()), 40,
            "the schemas/ glob matched almost nothing; this guard is checking nothing",
        )


class OpenapiDocumentStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = load_document()

    def test_document_declares_openapi_3_1_with_info_and_paths(self) -> None:
        self.assertEqual("3.1.0", self.document.get("openapi"))
        self.assertTrue(self.document.get("info", {}).get("title"))
        self.assertIn("paths", self.document)

    def test_component_entries_cover_the_schema_directory_exactly(self) -> None:
        components = self.document.get("components", {}).get("schemas", {})
        self.assertTrue(components, "components.schemas is empty; this guard is vacuous")
        expected = {name[: -len(".schema.json")] for name in schema_filenames()}
        self.assertEqual(expected, set(components))
        for key, entry in components.items():
            with self.subTest(schema=key):
                # A block-mapping entry is a ``$ref`` mapping; the one-line flow
                # form this document uses is returned as its raw text instead.
                raw = entry.get("$ref", "") if isinstance(entry, dict) else str(entry)
                match = EXTERNAL_REF.search(raw)
                self.assertIsNotNone(
                    match,
                    f"components.schemas[{key!r}] carries no schemas/ $ref: {raw!r}",
                )
                self.assertEqual(
                    f"{key}.schema.json",
                    match.group(1),
                    "component key and referenced schema file must agree",
                )

    def test_idempotency_contract_is_in_the_catalog(self) -> None:
        self.assertIn(
            "idkmesh-idempotency-v0.1",
            self.document.get("components", {}).get("schemas", {}),
        )

    def test_every_internal_reference_resolves(self) -> None:
        # Collected from the raw text rather than the parsed tree on purpose:
        # the block-mapping parser skips YAML list items, and `parameters:`
        # entries are referenced from lists (`- $ref: "#/components/..."`), so
        # a tree walk would silently miss exactly those. Text collection keeps
        # every internal pointer under review, whichever nesting it sits in.
        text = OPENAPI.read_text(encoding="utf-8")
        refs = sorted(INTERNAL_REF_VALUE.findall(text))
        self.assertTrue(refs, "no internal references found; this guard is vacuous")
        for ref in refs:
            with self.subTest(ref=ref):
                target: object = self.document
                for part in ref[2:].split("/"):
                    self.assertIn(part, target, f"unresolved internal reference {ref}")
                    target = target[part]


if __name__ == "__main__":
    unittest.main()
