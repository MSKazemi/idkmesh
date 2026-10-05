"""API contract conformance: examples bind to the schemas the API advertises.

Issue #737 / ``docs/specifications/API_CONVENTIONS_V0_1.md`` section 19
requires that documented examples validate in CI and that representative
runtime responses validate against the advertised schemas. The two existing
layers each leave one half of that sentence unchecked:

- ``tests/test_example_contract_coverage.py`` validates every committed
  example against a schema its table names, and the Control Tower test
  modules validate served responses against schema files their tests name;
- nothing checked that the schema a test names is the schema ``openapi.yaml``
  advertises for that surface.

Without that link the catalog can drift away from the tests without either
one failing: an example keeps validating against a contract the API no
longer advertises, and a response keeps validating against a schema the
catalog does not serve. This module closes that gap. It resolves the target
schema from ``openapi.yaml`` first -- scanned as text, because the PR Gate
installs no YAML parser (see ``tests/test_openapi_document.py`` and
``tests/test_workflow_tool_contracts.py``) -- and only then validates the
document against that advertised contract.

Only ``jsonschema`` (a Phase 0 dependency) is needed, and its import is
guarded the way ``tests/test_example_contract_coverage.py`` guards it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import unittest

# The randomness-lab test job installs a minimal dependency set without
# jsonschema, so an unguarded module-scope import would break collection.
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    import jsonschema
    from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENAPI = REPO_ROOT / "openapi.yaml"
SCHEMAS = REPO_ROOT / "schemas"
API_EXAMPLES_DIR = "examples/api"

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

# A `key:` / `key: value` / `"key":` / `"key": value` line in the block-mapping
# subset of YAML that `openapi.yaml` uses. A value may itself contain colons;
# the key ends at the first one.
_KEY = re.compile(r"""^(?:"([^"]*)"|'([^']*)'|([^\s:][^:]*?)):(?:\s+(.*))?$""")
_BLOCK_SCALAR = re.compile(r"^[>|][+-]?\d*$")


def _unquote(value: str) -> str:
    """Strip one layer of matching YAML quotes from a scalar value."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_block_mapping(text: str) -> dict:
    """Parse the block-mapping subset of YAML `openapi.yaml` is written in.

    Deliberately not a YAML parser: this must run where only the standard
    library exists. List items and block scalars are skipped wholesale --
    nothing this module asserts lives inside one -- and any line shape that
    does not match is ignored rather than guessed at. What remains is the
    nested ``key: value`` mapping tree: paths, verbs, response codes, media
    types, schema references, and the ``components`` sections.
    """
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    skip_indent: int | None = None
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))
        if skip_indent is not None:
            if indent > skip_indent or stripped.startswith("- "):
                continue
            skip_indent = None
        if stripped.startswith("- "):
            # A list item (security schemes, parameters). Skip it and its
            # continuation lines; no advertised schema lives inside one.
            skip_indent = indent
            continue
        match = _KEY.match(stripped)
        if match is None:
            continue
        double, single, plain, value = match.groups()
        key = (double if double is not None else single if single is not None else plain).strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if value is None or value == "":
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        elif _BLOCK_SCALAR.match(value):
            skip_indent = indent
            parent[key] = value
        else:
            parent[key] = _unquote(value)
    return root


def load_catalog() -> dict:
    return parse_block_mapping(OPENAPI.read_text(encoding="utf-8"))


def advertised_response_schemas(document: dict) -> dict:
    """Map (METHOD, path, status) to {media type: advertised schema key}.

    The schema key is the ``components.schemas`` key, which by
    ``tests/test_openapi_document.py`` equals the schema file's name minus
    ``.schema.json``. ``None`` means the response declares an inline schema
    (or none) rather than referencing a canonical contract; the empty dict
    means the response declares no content at all.
    """
    shared = (document.get("components") or {}).get("responses") or {}
    advertised: dict = {}
    for path, item in (document.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for verb, operation in item.items():
            if verb.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            for status, response in (operation.get("responses") or {}).items():
                if not isinstance(response, dict):
                    continue
                if "$ref" in response:
                    name = str(response["$ref"]).rsplit("/", 1)[-1]
                    response = shared.get(name) or {}
                media_map: dict = {}
                for media_type, media in (response.get("content") or {}).items():
                    schema = media.get("schema") if isinstance(media, dict) else None
                    if isinstance(schema, dict) and "$ref" in schema:
                        media_map[media_type] = str(schema["$ref"]).rsplit("/", 1)[-1]
                    else:
                        media_map[media_type] = None
                advertised[(verb.upper(), path, str(status))] = media_map
    return advertised


def tracked_api_examples() -> set[str]:
    """Tracked JSON under examples/api/. Tracked-only, like the coverage module."""
    output = subprocess.run(
        ["git", "ls-files", "-z", "--", f"{API_EXAMPLES_DIR}/*.json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {entry for entry in output.split("\0") if entry}


def validator_for(schema_key: str):
    """A Draft 2020-12 validator for the advertised schema, cross-file refs resolved."""
    registry = Registry()
    for path in sorted(SCHEMAS.glob("*.json")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        registry = registry.with_resource(
            contents.get("$id", path.name), Resource.from_contents(contents)
        )
    schema = json.loads(
        (SCHEMAS / f"{schema_key}.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema, registry=registry)


def validation_errors(validator, example_path: str) -> list[str]:
    document = json.loads((REPO_ROOT / example_path).read_text(encoding="utf-8"))
    return [
        f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in sorted(
            validator.iter_errors(document), key=lambda e: list(e.path)
        )
    ]


# Each documented example of a response body, bound to the exact response it
# documents: (METHOD, path template, status, media type). The endpoint binding
# is what ties the example to the advertisement; without it a name-based table
# can pair an example with a schema the API serves somewhere else, or nowhere.
API_EXAMPLES = {
    "examples/api/control-tower-run-attempts-response.example.json": (
        "GET",
        "/api/v1/runs/{run_id}/attempts",
        "200",
        "application/json",
    ),
    "examples/api/control-tower-run-response.example.json": (
        "GET",
        "/api/v1/runs/{run_id}",
        "200",
        "application/json",
    ),
    "examples/api/control-tower-status.example.json": (
        "GET",
        "/api/v1/status",
        "200",
        "application/json",
    ),
    # The standard error envelope is advertised by every 4xx/5xx component
    # response; one representative endpoint is bound here and the component
    # agreement is asserted across all of them below.
    "examples/api/error-envelope.example.json": (
        "GET",
        "/api/v1/runs/{run_id}",
        "404",
        "application/json",
    ),
    "examples/api/list-envelope.example.json": (
        "GET",
        "/api/v1/runs",
        "200",
        "application/json",
    ),
    "examples/api/readiness.example.json": (
        "GET",
        "/readyz",
        "200",
        "application/json",
    ),
}

# Examples that document a schema object rather than a whole response body.
# The component key must still be one the catalog advertises.
SCHEMA_DOCUMENT_EXAMPLES = {
    "examples/api/product-spine-run.example.json": "idkmesh-product-spine-run-v0.1",
}

# Semantic-invalid fixtures: their rejection by the schema is asserted in
# `tests/test_example_contract_coverage.py`; they must never validate here.
NEGATIVE_API_EXAMPLES = {
    "examples/api/invalid-missing-status.readiness.json",
}


class CatalogScanTests(unittest.TestCase):
    """The advertisement scan must find the catalog before it can bind to it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.document = load_catalog()
        cls.advertised = advertised_response_schemas(cls.document)

    def test_the_scan_finds_every_documented_path(self) -> None:
        found = {path for _, path, _ in self.advertised}
        expected = {
            "/healthz",
            "/readyz",
            "/api/v1/status",
            "/api/v1/openapi.json",
            "/api/v1/run-evidence/inspect",
            "/api/v1/runs",
            "/api/v1/runs/{run_id}",
            "/api/v1/runs/{run_id}/attempts",
            "/api/v1/runs/{run_id}/evidence",
            "/api/v1/work-units",
            "/api/v1/work-units/{work_unit_id}",
            "/api/v1/projects/{project_id}",
            "/api/v1/events",
            "/api/v1/events/stream",
        }
        self.assertEqual(expected, found)

    def test_the_scan_is_not_vacuous(self) -> None:
        self.assertGreaterEqual(
            len(self.advertised),
            35,
            "the catalog scan found almost no responses; this guards nothing",
        )

    def test_every_named_schema_key_resolves_to_a_schema_file(self) -> None:
        keys = {
            key
            for media_map in self.advertised.values()
            for key in media_map.values()
            if key is not None
        }
        self.assertTrue(keys)
        for key in sorted(keys):
            with self.subTest(schema=key):
                self.assertTrue(
                    (SCHEMAS / f"{key}.schema.json").is_file(),
                    f"openapi.yaml advertises {key} but schemas/{key}.schema.json "
                    "does not exist",
                )

    def test_json_media_type_pairings_never_disagree(self) -> None:
        for (method, path, status), media_map in sorted(self.advertised.items()):
            json_keys = {
                key
                for media, key in media_map.items()
                if media.endswith("json") and key is not None
            }
            with self.subTest(response=f"{method} {path} {status}"):
                self.assertLessEqual(
                    len(json_keys),
                    1,
                    f"the JSON media types of {method} {path} {status} advertise "
                    f"different schemas: {sorted(json_keys)}",
                )


class DocumentedExampleConformanceTests(unittest.TestCase):
    """Every documented example validates against the schema the API advertises."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.advertised = advertised_response_schemas(load_catalog())

    def test_every_api_example_is_classified(self) -> None:
        classified = set(API_EXAMPLES) | set(SCHEMA_DOCUMENT_EXAMPLES) | NEGATIVE_API_EXAMPLES
        tracked = tracked_api_examples()
        self.assertEqual(
            set(),
            tracked - classified,
            "a new examples/api/ file is not classified in "
            "tests/test_api_contract_conformance.py; decide which response it documents",
        )
        self.assertEqual(
            set(),
            classified - tracked,
            "the tables name an examples/api/ file that is no longer tracked",
        )

    def test_each_endpoint_example_validates_against_the_advertised_schema(self) -> None:
        for example, (method, path, status, media_type) in sorted(API_EXAMPLES.items()):
            with self.subTest(example=example):
                key = self.advertised[(method, path, status)][media_type]
                self.assertIsNotNone(
                    key,
                    f"{method} {path} {status} advertises no canonical schema for "
                    f"{media_type}, so {example} validates against nothing",
                )
                validator = validator_for(key)
                self.assertEqual(
                    [], validation_errors(validator, example),
                    f"{example} no longer validates against {key}.schema.json, the "
                    f"schema openapi.yaml advertises for {method} {path} {status}",
                )

    def test_advertised_schema_agrees_with_the_example_contract_coverage_table(self) -> None:
        """Two example/schema tables exist; they must never disagree.

        `tests/test_example_contract_coverage.py` pairs each example with a
        schema file directly; this module pairs it with whatever the catalog
        advertises for the response it documents. Either pairing changing
        alone would leave the other asserting against a lie.
        """
        spec = importlib.util.spec_from_file_location(
            "example_contract_coverage",
            REPO_ROOT / "tests" / "test_example_contract_coverage.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for example, (method, path, status, media_type) in sorted(API_EXAMPLES.items()):
            with self.subTest(example=example):
                key = self.advertised[(method, path, status)][media_type]
                self.assertEqual(
                    f"{key}.schema.json",
                    module.VALID_AGAINST.get(example),
                    f"{example} is paired with {module.VALID_AGAINST.get(example)} by "
                    "the coverage table but the API advertises "
                    f"{key}.schema.json for {method} {path} {status}",
                )

    def test_schema_document_example_names_an_advertised_component(self) -> None:
        components = (self.document_components()).get("schemas") or {}
        for example, key in sorted(SCHEMA_DOCUMENT_EXAMPLES.items()):
            with self.subTest(example=example):
                self.assertIn(
                    key,
                    components,
                    f"{example} documents {key}, which openapi.yaml does not advertise",
                )

    @unittest.skipUnless(HAS_JSONSCHEMA, "example validation requires jsonschema")
    def test_schema_document_example_validates_against_its_advertised_schema(self) -> None:
        for example, key in sorted(SCHEMA_DOCUMENT_EXAMPLES.items()):
            with self.subTest(example=example):
                self.assertEqual(
                    [], validation_errors(validator_for(key), example),
                    f"{example} no longer validates against {key}.schema.json",
                )

    def test_negative_fixtures_are_bound_to_their_response_too(self) -> None:
        """The rejected fixtures document a real response shape.

        Their rejection is asserted elsewhere; here they must at least name
        surfaces the catalog really advertises, so they stay honest examples
        of what a *bad* response against *this* API looks like.
        """
        expected = {
            "examples/api/invalid-missing-status.readiness.json": (
                "GET",
                "/readyz",
                "200",
            ),
        }
        self.assertEqual(expected.keys() & NEGATIVE_API_EXAMPLES, NEGATIVE_API_EXAMPLES)
        for example, (method, path, status) in expected.items():
            with self.subTest(example=example):
                self.assertIn(
                    (method, path, status),
                    self.advertised,
                    f"{example} names a response the catalog does not advertise",
                )

    @unittest.skipUnless(HAS_JSONSCHEMA, "example validation requires jsonschema")
    def test_negative_fixtures_are_still_rejected(self) -> None:
        key = self.advertised[("GET", "/readyz", "200")]["application/json"]
        validator = validator_for(key)
        for example in sorted(NEGATIVE_API_EXAMPLES):
            with self.subTest(example=example):
                self.assertNotEqual(
                    [],
                    validation_errors(validator, example),
                    f"{example} now validates against {key}.schema.json, so it no "
                    "longer proves the schema rejects a missing required property",
                )

    def document_components(self) -> dict:
        return load_catalog().get("components") or {}


if __name__ == "__main__":
    unittest.main()
