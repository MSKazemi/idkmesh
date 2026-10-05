"""Every published schema must itself be a valid JSON Schema.

`schemas/` is described in docs/README.md as the machine-readable protocol
truth, but only five of its documents were ever meta-validated:
`experiments/harness.py validate` names work-unit-v0.2, experiment-manifest-v0.1,
experiment-result-v0.1, result-manifest-v0.1 and verification-result-v0.1, and
`Draft202012Validator.check_schema` runs only on those. The remaining schemas
were covered by nothing.

That gap was not theoretical. Setting `"type": "not-a-valid-type"` and
`"properties": "should-be-an-object"` in `schemas/goal-graph.schema.json` still
produced `OK: schemas valid` and exit 0 from the harness -- the gate asserted a
property it had not checked. A JSON-syntax check does not close this either: a
structurally invalid schema is usually still valid JSON.

A broken schema does not fail loudly. `jsonschema` may accept an unknown keyword
and silently validate nothing, so the first symptom is an instance passing a
check that no longer constrains it.

`jsonschema` is available in the PR Gate, which installs
`requirements-phase0.txt`. It is *not* available in the randomness-lab test job,
which installs a smaller set, so the import is guarded and these tests skip
there rather than failing collection for the whole file.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

# The randomness-lab test job installs a minimal dependency set without
# jsonschema, so importing it at module scope makes that job fail to even
# collect this file. Guarded the way tests/test_ace_lineage_schema.py does.
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator
    from jsonschema.validators import validator_for

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"


def schema_files() -> list[Path]:
    return sorted(SCHEMA_DIR.glob("*.json"))


# Schema documents that deliberately leave their top-level object open. All
# four are legacy unversioned contracts that shipped open before this policy;
# ADR-0020 forbids closing them in place, because removing accepted properties
# is exactly the breaking change its compatibility gate exists to block. Where
# a strict versioned successor exists (work-unit-v0.2, experiment-result-v0.1,
# result-manifest-v0.1) that file is where closure lives. A new entry needs a
# reason, not just a name.
OPEN_DOCUMENTS = {
    "experiment-result.schema.json": (
        "shipped open before the policy; ADR-0020 forbids closing it in place "
        "-- strictness lives in experiment-result-v0.1"
    ),
    "goal-graph.schema.json": (
        "shipped open before the policy; ADR-0020 forbids closing it in place "
        "and no versioned successor has been cut yet"
    ),
    "result-manifest.schema.json": (
        "shipped open before the policy; ADR-0020 forbids closing it in place "
        "-- strictness lives in result-manifest-v0.1"
    ),
    "work-unit.schema.json": (
        "shipped open before the policy; ADR-0020 forbids closing it in place "
        "-- strictness lives in work-unit-v0.2"
    ),
}


def is_object_schema(document: dict) -> bool:
    return document.get("type") == "object" or "properties" in document


@unittest.skipUnless(HAS_JSONSCHEMA, "schema meta-validation requires jsonschema")
class SchemaValidityTests(unittest.TestCase):
    def test_the_schema_directory_is_not_empty(self) -> None:
        """Guard the guard: a bad glob would make every check below vacuous."""
        self.assertGreater(
            len(schema_files()),
            0,
            f"no schemas found in {SCHEMA_DIR}; this guard is checking nothing.",
        )

    def test_every_schema_is_parseable_json(self) -> None:
        for path in schema_files():
            with self.subTest(schema=path.name):
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    self.fail(f"{path.name} is not valid JSON: {error}")

    def test_every_schema_is_a_valid_json_schema(self) -> None:
        for path in schema_files():
            with self.subTest(schema=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                # Honour the document's own `$schema` where it declares one, so a
                # schema written against a different draft is judged by its own
                # dialect rather than by whichever default this test prefers.
                validator = validator_for(document, default=Draft202012Validator)
                try:
                    validator.check_schema(document)
                except Exception as error:  # jsonschema raises SchemaError
                    self.fail(
                        f"{path.name} is not a valid JSON Schema under "
                        f"{validator.__name__}: {error}"
                    )


class SchemaAdditionalPropertiesPolicyTests(unittest.TestCase):
    """Issue #737: `additionalProperties: false` is used where intentional.

    "Where intentional" is only enforceable if the choice is explicit. This
    class holds the policy at the document boundary -- the public object's own
    contract: every top-level object schema declares its
    `additionalProperties` policy, and it is `false` unless the file is
    recorded above with a reason. Nested subschemas are each schema's own
    design (conditional `if` branches and open payload namespaces are
    deliberate there), and any in-place change to them is already frozen by
    ADR-0020's compatibility gate. Needs no third-party packages, so it runs
    in the minimal test jobs as well as the PR Gate.
    """

    def test_every_object_schema_declares_an_explicit_policy(self) -> None:
        for path in schema_files():
            document = json.loads(path.read_text(encoding="utf-8"))
            if not is_object_schema(document):
                continue
            with self.subTest(schema=path.name):
                self.assertIn(
                    "additionalProperties",
                    document,
                    f"{path.name} leaves its top-level policy implicit; a new "
                    "public object must say whether it is closed",
                )

    def test_object_schemas_are_closed_by_default(self) -> None:
        for path in schema_files():
            document = json.loads(path.read_text(encoding="utf-8"))
            if not is_object_schema(document) or path.name in OPEN_DOCUMENTS:
                # The recorded legacy documents are checked for staleness in
                # the test below, not re-argued here.
                continue
            with self.subTest(schema=path.name):
                self.assertEqual(
                    False,
                    document.get("additionalProperties"),
                    f"{path.name} is open at its top level; only the recorded "
                    "legacy documents may be, and this is not one of them",
                )

    def test_the_open_document_records_are_exact_and_not_stale(self) -> None:
        actually_open = set()
        for path in schema_files():
            document = json.loads(path.read_text(encoding="utf-8"))
            if is_object_schema(document) and (
                document.get("additionalProperties") is not False
            ):
                actually_open.add(path.name)
        self.assertEqual(
            set(),
            actually_open - set(OPEN_DOCUMENTS),
            "a schema went open without a recorded reason",
        )
        self.assertEqual(
            set(),
            set(OPEN_DOCUMENTS) - actually_open,
            "an OPEN_DOCUMENTS record names a schema that is no longer open; "
            "delete the stale record",
        )
        for name, reason in sorted(OPEN_DOCUMENTS.items()):
            with self.subTest(schema=name):
                self.assertTrue(
                    reason.strip(), f"{name} is recorded open with no reason"
                )
                self.assertTrue(
                    (SCHEMA_DIR / name).is_file(),
                    f"OPEN_DOCUMENTS names {name}, which does not exist",
                )

    def test_the_scan_is_not_vacuous(self) -> None:
        object_schemas = [
            path
            for path in schema_files()
            if is_object_schema(json.loads(path.read_text(encoding="utf-8")))
        ]
        self.assertGreaterEqual(
            len(object_schemas),
            40,
            "the schema scan matched almost nothing; this guard is checking nothing",
        )
        self.assertLessEqual(
            len(OPEN_DOCUMENTS),
            5,
            "the exemption table is growing past the legacy four; new public "
            "objects should ship closed",
        )


if __name__ == "__main__":
    unittest.main()
