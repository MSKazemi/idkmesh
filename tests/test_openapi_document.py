"""The checked-in OpenAPI document stays complete and resolvable.

Issue #737 / API_CONVENTIONS_V0_1.md section 19: OpenAPI references the
canonical JSON Schemas instead of redefining them, and unresolved references
must fail CI. `openapi.yaml` is that checked-in document; these tests keep it
present, valid, and covering every public contract in `schemas/`.

Two layers, deliberately. The text scan needs only the standard library and
runs in every test job — the PR Gate installs jsonschema but no YAML parser,
and `tests/test_workflow_tool_contracts.py` documents why importing one at
module scope would break that gate. The structural checks guard `import yaml`
the way schema tests guard `import jsonschema`, so they skip where the parser
is absent rather than breaking collection.
"""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

HAS_YAML = importlib.util.find_spec("yaml") is not None
if HAS_YAML:
    import yaml

ROOT = Path(__file__).resolve().parents[1]
OPENAPI = ROOT / "openapi.yaml"
SCHEMAS = ROOT / "schemas"

EXTERNAL_REF = re.compile(r"https://idkmesh\.org/schemas/([A-Za-z0-9._-]+\.schema\.json)")


def schema_filenames() -> set[str]:
    return {path.name for path in SCHEMAS.glob("*.schema.json")}


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


@unittest.skipUnless(HAS_YAML, "structural OpenAPI checks require a YAML parser")
class OpenapiDocumentStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))

    def test_document_is_valid_yaml_and_openapi_3_1(self) -> None:
        self.assertEqual("3.1.0", self.document["openapi"])
        self.assertTrue(self.document["info"]["title"])
        self.assertIn("paths", self.document)

    def test_component_entries_cover_the_schema_directory_exactly(self) -> None:
        components = self.document["components"]["schemas"]
        expected = {name[: -len(".schema.json")] for name in schema_filenames()}
        self.assertEqual(expected, set(components))
        for key, entry in components.items():
            with self.subTest(schema=key):
                self.assertEqual(
                    f"{key}.schema.json",
                    EXTERNAL_REF.search(entry["$ref"]).group(1),
                    "component key and referenced schema file must agree",
                )

    def test_idempotency_contract_is_in_the_catalog(self) -> None:
        self.assertIn("idkmesh-idempotency-v0.1", self.document["components"]["schemas"])

    def test_every_internal_reference_resolves(self) -> None:
        def walk(node, found):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "$ref" and isinstance(value, str) and value.startswith("#/"):
                        found.append(value)
                    else:
                        walk(value, found)
            elif isinstance(node, list):
                for item in node:
                    walk(item, found)

        refs: list[str] = []
        walk(self.document, refs)
        self.assertTrue(refs, "no internal references found; this guard is vacuous")
        for ref in refs:
            with self.subTest(ref=ref):
                target = self.document
                for part in ref[2:].split("/"):
                    self.assertIn(part, target, f"unresolved internal reference {ref}")
                    target = target[part]


if __name__ == "__main__":
    unittest.main()
