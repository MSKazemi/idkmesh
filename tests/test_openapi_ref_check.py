"""Tests for tools/openapi_ref_check.py (issue #737's reference resolution gate).

The gate must prove two things and this file exercises both sides of each:

- the repository's real ``openapi.yaml`` and ``schemas/`` tree resolves with no
  unresolved references, and the CLI reports that as exit 0;
- a deliberately broken reference -- in the OpenAPI document or in a schema,
  internal pointer or cross-file schema pointer -- is *found*, attributed to
  its source file, and fails the gate with exit 1. A gate that only ever sees
  green input proves nothing.

Fixtures are synthetic miniature trees written to a temporary directory, so
the negative cases never touch the real contracts. Like the gate itself these
tests need only the standard library: the PR Gate installs pytest and
``requirements-phase0.txt`` and no YAML parser, so ``openapi.yaml`` fixture
text is kept to the shapes the gate's bounded scanner understands.

All tests are methods on ``unittest.TestCase`` classes on purpose; the
documented module-level ``test_*`` counts in ``tests/test_documented_test_counts.py``
would otherwise drift.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import openapi_ref_check as orc

TOOL = ROOT / "tools" / "openapi_ref_check.py"

EXAMPLE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://idkmesh.org/schemas/example-v0.1.schema.json",
    "title": "Example",
    "type": "object",
    "additionalProperties": False,
    "required": ["kind"],
    "properties": {
        "kind": {"const": "example"},
        "other": {"$ref": "#/$defs/other"},
    },
    "$defs": {"other": {"type": "string"}},
}

CLEAN_OPENAPI = """\
openapi: 3.1.0
info:
  title: Example API
  version: "0.1"
paths: {}
components:
  schemas:
    Example:
      $ref: "https://idkmesh.org/schemas/example-v0.1.schema.json"
  parameters:
    RunId:
      name: run_id
      in: path
      required: true
      schema:
        type: string
"""


def _violation_sources(report: dict) -> list[str]:
    return [item["source"] for item in report["violations"]]


class RepositoryTreeTests(unittest.TestCase):
    def test_repository_references_all_resolve(self) -> None:
        report = orc.check_references(ROOT)
        self.assertTrue(report["ok"], orc.format_report(report))
        self.assertEqual(report["violations"], [])
        self.assertEqual(report["kind"], "idkmesh-openapi-ref-check")

    def test_repository_counts_cover_the_whole_tree(self) -> None:
        report = orc.check_references(ROOT)
        counts = report["counts"]
        self.assertGreater(counts["openapi_refs"], 0)
        self.assertGreater(counts["schema_refs"], 0)
        self.assertGreater(counts["components"], 0)
        self.assertEqual(
            counts["schema_documents"],
            len(list((ROOT / "schemas").glob("*.json"))),
        )

    def test_format_report_states_the_green_result(self) -> None:
        text = orc.format_report(orc.check_references(ROOT))
        self.assertIn("no unresolved references", text)
        self.assertNotIn("unresolved reference(s):", text)


class CliTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(TOOL), *args],
            cwd=str(ROOT), capture_output=True, text=True,
        )

    def test_cli_exits_zero_on_the_repository(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no unresolved references", result.stdout)

    def test_cli_json_mode_is_machine_readable(self) -> None:
        result = self._run("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["kind"], "idkmesh-openapi-ref-check")
        self.assertTrue(report["ok"])

    def test_cli_missing_openapi_document_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "schemas").mkdir()
            result = self._run("--root", tmp)
        self.assertEqual(result.returncode, 2)
        self.assertIn("openapi.yaml is missing", result.stderr)

    def test_cli_empty_schemas_directory_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "openapi.yaml").write_text(CLEAN_OPENAPI, encoding="utf-8")
            (Path(tmp) / "schemas").mkdir()
            result = self._run("--root", tmp)
        self.assertEqual(result.returncode, 2)
        self.assertIn("no schema documents", result.stderr)


class SyntheticTreeTests(unittest.TestCase):
    """Negative fixtures: every broken reference shape must be reported."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "schemas").mkdir()
        self.write_schema("example-v0.1.schema.json", EXAMPLE_SCHEMA)

    def write_schema(self, name: str, document: dict) -> None:
        (self.root / "schemas" / name).write_text(
            json.dumps(document, indent=2), encoding="utf-8",
        )

    def write_openapi(self, text: str) -> None:
        (self.root / "openapi.yaml").write_text(text, encoding="utf-8")

    def check(self) -> dict:
        return orc.check_references(self.root)

    def test_clean_synthetic_tree_resolves(self) -> None:
        self.write_openapi(CLEAN_OPENAPI)
        report = self.check()
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["counts"]["openapi_refs"], 1)
        self.assertEqual(report["counts"]["schema_refs"], 1)
        self.assertEqual(report["counts"]["schema_documents"], 1)

    def test_unresolved_openapi_schema_reference_is_reported(self) -> None:
        self.write_openapi(CLEAN_OPENAPI.replace(
            "example-v0.1.schema.json", "missing-v0.1.schema.json",
        ))
        report = self.check()
        self.assertFalse(report["ok"])
        self.assertEqual(len(report["violations"]), 1)
        item = report["violations"][0]
        self.assertIn("openapi.yaml:", item["source"])
        self.assertIn("missing-v0.1.schema.json", item["ref"])
        self.assertIn("does not exist", item["reason"])

    def test_unresolved_component_reference_is_reported(self) -> None:
        self.write_openapi(CLEAN_OPENAPI + """\
  responses:
    Missing:
      $ref: "#/components/schemas/Nope"
""")
        report = self.check()
        self.assertFalse(report["ok"])
        item = report["violations"][0]
        self.assertIn("#/components/schemas/Nope", item["ref"])
        self.assertIn("no component 'Nope'", item["reason"])

    def test_unresolved_internal_pointer_in_schema_is_reported(self) -> None:
        document = json.loads(json.dumps(EXAMPLE_SCHEMA))
        document["properties"]["other"] = {"$ref": "#/$defs/absent"}
        self.write_schema("example-v0.1.schema.json", document)
        self.write_openapi(CLEAN_OPENAPI)
        report = self.check()
        self.assertFalse(report["ok"])
        self.assertEqual(_violation_sources(report), ["schemas/example-v0.1.schema.json"])
        self.assertIn("#/$defs/absent", report["violations"][0]["ref"])
        self.assertIn("does not resolve", report["violations"][0]["reason"])

    def test_unresolved_cross_file_fragment_is_reported(self) -> None:
        other = dict(EXAMPLE_SCHEMA)
        other["$id"] = "https://idkmesh.org/schemas/other-v0.1.schema.json"
        self.write_schema("other-v0.1.schema.json", other)
        document = json.loads(json.dumps(EXAMPLE_SCHEMA))
        document["properties"]["other"] = {
            "$ref": "https://idkmesh.org/schemas/other-v0.1.schema.json#/$defs/absent",
        }
        self.write_schema("example-v0.1.schema.json", document)
        self.write_openapi(CLEAN_OPENAPI)
        report = self.check()
        self.assertFalse(report["ok"])
        self.assertEqual(len(report["violations"]), 1)
        self.assertIn("#/$defs/absent", report["violations"][0]["ref"])
        self.assertIn("does not resolve inside", report["violations"][0]["reason"])

    def test_schema_identity_mismatch_is_reported(self) -> None:
        document = dict(EXAMPLE_SCHEMA)
        document["$id"] = "https://idkmesh.org/schemas/renamed-v0.1.schema.json"
        self.write_schema("example-v0.1.schema.json", document)
        self.write_openapi(CLEAN_OPENAPI)
        report = self.check()
        self.assertFalse(report["ok"])
        self.assertIn("$id", report["violations"][0]["reason"])
        self.assertIn("does not agree", report["violations"][0]["reason"])

    def test_reference_outside_the_schemas_namespace_is_reported(self) -> None:
        self.write_openapi(CLEAN_OPENAPI + """\
  requestBodies:
    Elsewhere:
      $ref: "https://example.com/somewhere/other.json"
""")
        report = self.check()
        self.assertFalse(report["ok"])
        item = report["violations"][0]
        self.assertIn("https://example.com/somewhere/other.json", item["ref"])
        self.assertIn("outside the schemas/ namespace", item["reason"])

    def test_invalid_json_schema_is_reported_not_crashed(self) -> None:
        (self.root / "schemas" / "example-v0.1.schema.json").write_text(
            "{not-json", encoding="utf-8",
        )
        self.write_openapi(CLEAN_OPENAPI)
        report = self.check()
        self.assertFalse(report["ok"])
        reasons = [item["reason"] for item in report["violations"]]
        self.assertTrue(any("not valid JSON" in reason for reason in reasons))

    def test_missing_openapi_document_raises_gate_error(self) -> None:
        with self.assertRaises(orc.OpenApiRefCheckError):
            self.check()

    def test_format_report_lists_each_violation_with_its_reason(self) -> None:
        self.write_openapi(CLEAN_OPENAPI.replace(
            "example-v0.1.schema.json", "missing-v0.1.schema.json",
        ))
        text = orc.format_report(self.check())
        self.assertIn("1 unresolved reference(s):", text)
        self.assertIn("missing-v0.1.schema.json", text)
        self.assertIn("does not exist", text)


class EntrypointTests(unittest.TestCase):
    def test_main_returns_one_for_a_broken_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "schemas").mkdir()
            (root / "schemas" / "example-v0.1.schema.json").write_text(
                json.dumps(EXAMPLE_SCHEMA), encoding="utf-8",
            )
            (root / "openapi.yaml").write_text(
                CLEAN_OPENAPI.replace(
                    "example-v0.1.schema.json", "missing-v0.1.schema.json",
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = orc.main(["--root", tmp])
        self.assertEqual(code, 1)
        self.assertIn("unresolved reference(s):", stream.getvalue())

    @unittest.skipIf(os.name == "nt", "executable bit is a POSIX concept")
    def test_tool_is_executable_with_a_shebang(self) -> None:
        first_line = TOOL.read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(first_line.startswith("#!"))
        self.assertTrue(os.access(TOOL, os.X_OK), f"{TOOL} must be executable")


if __name__ == "__main__":
    unittest.main()
