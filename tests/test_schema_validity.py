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

`jsonschema` is available here because the PR Gate installs
`requirements-phase0.txt`, which pins it.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.validators import validator_for

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"


def schema_files() -> list[Path]:
    return sorted(SCHEMA_DIR.glob("*.json"))


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


if __name__ == "__main__":
    unittest.main()
