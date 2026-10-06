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

Two legs, both bound to the advertisement:

- documented examples are validated against the schema the catalog advertises
  for the response they document;
- representative runtime responses -- served over real loopback HTTP by the
  same ``create_server`` entry point the Control Tower ships -- are validated
  against the schema the catalog advertises for that response, and every
  advertised response must have a representative or a recorded reason it has
  no canonical schema. Every envelope the runtime serves is advertised: the
  store-unavailable 503s and the inspect endpoint's api-error 406/413/415
  bodies were the last served-but-unadvertised envelopes, and the ledger that
  pinned them retired once the catalog declared them all.

Only ``jsonschema`` (a Phase 0 dependency) is needed, and its import is
guarded the way ``tests/test_example_contract_coverage.py`` guards it.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import unittest

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.control_tower_ui import SAMPLE_REPORT, create_server
from idkmesh.local_ui_security import MAX_BODY_BYTES, TOKEN_HEADER
from idkmesh.product_spine_run_store import ProductSpineRunStore

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


def errors_for_document(validator, document) -> list[str]:
    return [
        f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in sorted(
            validator.iter_errors(document), key=lambda e: list(e.path)
        )
    ]


def validation_errors(validator, example_path: str) -> list[str]:
    document = json.loads((REPO_ROOT / example_path).read_text(encoding="utf-8"))
    return errors_for_document(validator, document)


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


# ---------------------------------------------------------------------------
# Representative runtime responses (API Conventions section 19:
# "representative runtime responses validate in CI").
#
# The requests below are issued against real loopback servers built by the
# same `create_server` entry point the Control Tower ships: one seeded with a
# Product Spine store (the `seeded` server) and one deliberately without one
# (the `bare` server), which is how the Unavailable surfaces are produced.
# ---------------------------------------------------------------------------


def load_sibling_test_module(name: str):
    """Load a sibling tests/ module for its shared seeding helpers.

    Same shape as `tests/test_control_tower_run_evidence.py`'s `_load_sibling`:
    the fixture builders in `tests/test_run_evidence_store.py` seed a run with
    a retained evidence report and attempts, which is exactly the realistic
    input the evidence and attempts responses need.
    """
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_sibling_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Identities the path templates are filled with. The run id comes from the
# seeded offline run (its identity is content-derived), the rest are the fixed
# identities `tests/test_run_evidence_store.py`'s `cli_run` uses.
WORK_UNIT_ID = "work/test-1"
PROJECT_ID = "project.test"
MISSING_RUN_ID = "run/does-not-exist"

# Every advertised response that names a canonical schema, with the request
# that produces it. Key: (METHOD, path template, status). Value: overrides for
# the default request (the `seeded` server, with the session token, the
# template filled with the identities above). `sse` reads the first event of
# the stream instead of a whole JSON body.
REPRESENTATIVES = {
    ("GET", "/readyz", "200"): {"token": False},
    ("GET", "/api/v1/status", "200"): {},
    ("GET", "/api/v1/status", "403"): {"token": False},
    ("GET", "/api/v1/openapi.json", "403"): {"token": False},
    ("POST", "/api/v1/run-evidence/inspect", "200"): {
        "headers": {"Content-Type": "application/json"},
        "body": SAMPLE_REPORT,
    },
    ("POST", "/api/v1/run-evidence/inspect", "400"): {
        "headers": {"Content-Type": "application/json"},
        "body": "{not json",
    },
    ("POST", "/api/v1/run-evidence/inspect", "403"): {
        "token": False,
        "headers": {"Content-Type": "application/json"},
        "body": SAMPLE_REPORT,
    },
    ("POST", "/api/v1/run-evidence/inspect", "406"): {
        "headers": {
            "Content-Type": "application/json",
            "Accept": "application/xml",
        },
        "body": SAMPLE_REPORT,
    },
    ("POST", "/api/v1/run-evidence/inspect", "413"): {
        "headers": {"Content-Type": "application/json"},
        "body": "x" * (MAX_BODY_BYTES + 1024),
    },
    ("POST", "/api/v1/run-evidence/inspect", "415"): {
        "headers": {"Content-Type": "text/plain"},
        "body": SAMPLE_REPORT,
    },
    ("GET", "/api/v1/runs", "200"): {},
    ("GET", "/api/v1/runs", "400"): {
        "request_path": "/api/v1/runs?state=bogus"
    },
    ("GET", "/api/v1/runs", "403"): {"token": False},
    ("GET", "/api/v1/runs", "503"): {"server": "bare"},
    ("GET", "/api/v1/runs/{run_id}", "200"): {},
    ("GET", "/api/v1/runs/{run_id}", "403"): {"token": False},
    ("GET", "/api/v1/runs/{run_id}", "404"): {
        "path_values": {"run_id": MISSING_RUN_ID}
    },
    ("GET", "/api/v1/runs/{run_id}", "503"): {"server": "bare"},
    ("GET", "/api/v1/runs/{run_id}/attempts", "200"): {},
    ("GET", "/api/v1/runs/{run_id}/attempts", "403"): {"token": False},
    ("GET", "/api/v1/runs/{run_id}/attempts", "404"): {
        "path_values": {"run_id": MISSING_RUN_ID}
    },
    ("GET", "/api/v1/runs/{run_id}/attempts", "503"): {"server": "bare"},
    ("GET", "/api/v1/runs/{run_id}/evidence", "200"): {},
    ("GET", "/api/v1/runs/{run_id}/evidence", "403"): {"token": False},
    ("GET", "/api/v1/runs/{run_id}/evidence", "404"): {
        "path_values": {"run_id": MISSING_RUN_ID}
    },
    ("GET", "/api/v1/runs/{run_id}/evidence", "503"): {"server": "bare"},
    ("GET", "/api/v1/work-units", "200"): {},
    ("GET", "/api/v1/work-units", "400"): {
        "request_path": "/api/v1/work-units?limit=0"
    },
    ("GET", "/api/v1/work-units", "403"): {"token": False},
    ("GET", "/api/v1/work-units", "503"): {"server": "bare"},
    ("GET", "/api/v1/work-units/{work_unit_id}", "200"): {},
    ("GET", "/api/v1/work-units/{work_unit_id}", "403"): {"token": False},
    ("GET", "/api/v1/work-units/{work_unit_id}", "404"): {
        "path_values": {"work_unit_id": "work/does-not-exist"}
    },
    ("GET", "/api/v1/work-units/{work_unit_id}", "503"): {"server": "bare"},
    ("GET", "/api/v1/projects/{project_id}", "200"): {},
    ("GET", "/api/v1/projects/{project_id}", "403"): {"token": False},
    ("GET", "/api/v1/projects/{project_id}", "404"): {
        "path_values": {"project_id": "project.missing"}
    },
    ("GET", "/api/v1/projects/{project_id}", "503"): {"server": "bare"},
    ("GET", "/api/v1/events", "200"): {},
    ("GET", "/api/v1/events", "400"): {
        "request_path": "/api/v1/events?limit=0"
    },
    ("GET", "/api/v1/events", "403"): {"token": False},
    ("GET", "/api/v1/events", "503"): {"server": "bare"},
    ("GET", "/api/v1/events/stream", "200"): {"sse": True},
    ("GET", "/api/v1/events/stream", "403"): {
        "token": False,
        "headers": {"Accept": "text/event-stream"},
    },
}

# Advertised responses that declare no canonical schema to validate against.
# Recording them keeps "no schema" a decision rather than an oversight, and
# the guard below fails if one of them ever gains a schema without gaining a
# representative.
NO_CANONICAL_SCHEMA = {
    ("GET", "/healthz", "200"): (
        "text/plain liveness string; there is no JSON contract to validate against"
    ),
    ("GET", "/api/v1/openapi.json", "200"): (
        "inline `type: object`; the document is its own contract"
    ),
}



class RepresentativeCoverageTests(unittest.TestCase):
    """The catalog and the two runtime tables must cover each other exactly."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.advertised = advertised_response_schemas(load_catalog())

    def test_every_advertised_response_is_represented_or_recorded(self) -> None:
        advertised = set(self.advertised)
        covered = set(REPRESENTATIVES) | set(NO_CANONICAL_SCHEMA)
        self.assertEqual(
            set(),
            advertised - covered,
            "openapi.yaml advertises responses with no representative runtime "
            "capture and no recorded reason; add one of the two",
        )
        self.assertEqual(
            set(),
            covered - advertised,
            "the runtime tables name responses openapi.yaml no longer advertises",
        )
        self.assertEqual(
            set(),
            set(REPRESENTATIVES) & set(NO_CANONICAL_SCHEMA),
            "a response cannot both have and lack a canonical schema",
        )

    def test_the_representative_table_is_not_vacuous(self) -> None:
        self.assertGreaterEqual(
            len(REPRESENTATIVES),
            30,
            "the representative table shrank; it must cover the whole API surface",
        )

    def test_recorded_no_schema_responses_really_declare_none(self) -> None:
        for key in sorted(NO_CANONICAL_SCHEMA):
            with self.subTest(response=key):
                named = {
                    name
                    for name in (self.advertised.get(key) or {}).values()
                    if name is not None
                }
                self.assertEqual(
                    set(),
                    named,
                    f"{key} now advertises a canonical schema {sorted(named)}; "
                    "move it into REPRESENTATIVES and validate it",
                )




@unittest.skipUnless(HAS_JSONSCHEMA, "response validation requires jsonschema")
class RuntimeResponseConformanceTests(unittest.TestCase):
    """Real served responses validate against the schema the catalog advertises."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="idkmesh-api-conformance-")
        root = Path(cls._tmp.name)
        db = root / "product-spine.sqlite3"
        helpers = load_sibling_test_module("test_run_evidence_store")
        # One offline run with a retained evidence report and attempts, plus two
        # plain runs so the event stream has real events to replay.
        cls.good = helpers.seed_offline_run(db, root, key="idem/conformance")
        service = ProductSpineRunStore(LocalMetadataStore(db))
        for index, run_id in enumerate(("run/evt-1", "run/evt-2"), start=1):
            service.create(
                helpers.cli_run(run_id, project_id=PROJECT_ID),
                idempotency_key=f"conformance-{run_id}",
                created_at=f"2026-10-01T00:00:{index:02d}Z",
            )
        cls.run_id = cls.good.run.run_id
        cls.servers = {
            "seeded": create_server(port=0, product_spine_store_path=str(db)),
            "bare": create_server(port=0),
        }
        cls._threads = []
        for server in cls.servers.values():
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            cls._threads.append(thread)
        cls.advertised = advertised_response_schemas(load_catalog())

    @classmethod
    def tearDownClass(cls) -> None:
        # Like tests/test_control_tower_events.py: open event streams keep
        # handler threads polling after the accept loop stops, so drain() wakes
        # and ends them before shutdown.
        for server in cls.servers.values():
            server.drain(timeout=5.0)
            server.shutdown()
            server.server_close()
        for thread in cls._threads:
            thread.join(timeout=2)
        cls._tmp.cleanup()

    def _http(self, server_name, method, path, *, token=True, headers=None, body=None):
        server = self.servers[server_name]
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        sent = {TOKEN_HEADER: server.ui_token} if token else {}
        sent.update(headers or {})
        try:
            conn.request(method, path, headers=sent, body=body)
        except (BrokenPipeError, ConnectionResetError):
            # The server rejects an oversized body from the Content-Length
            # header alone and closes without reading the upload, so a body
            # still in flight legitimately races the connection close and its
            # write fails. That is the transport rejecting the rest of the
            # upload, not the request failing: the response is already on the
            # wire (the recorded 413 case depends on exactly this). Tolerate the
            # write-side race and read the response; a genuinely unanswered
            # request still fails in getresponse() and below.
            pass
        response = conn.getresponse()
        payload = response.read()
        status = response.status
        content_type = dict(response.getheaders()).get("Content-Type", "")
        conn.close()
        return status, content_type, payload

    def _first_sse_event(self, server_name, *, token=True):
        server = self.servers[server_name]
        sock = socket.create_connection(("127.0.0.1", server.server_port), timeout=5)
        try:
            lines = [
                "GET /api/v1/events/stream HTTP/1.1",
                f"Host: 127.0.0.1:{server.server_port}",
                "Accept: text/event-stream",
                # A fresh connection without this header is a live tail (ADR-0023);
                # 0 replays the retained history, so the first frame is a real
                # committed event rather than a wait for the next one.
                "Last-Event-ID: 0",
            ]
            if token:
                lines.append(f"{TOKEN_HEADER}: {server.ui_token}")
            sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("ascii"))
            stream = sock.makefile("rb")
            status = int(stream.readline().split()[1])
            while True:
                line = stream.readline()
                if not line or line in (b"\r\n", b"\n"):
                    break
            data = None
            while data is None:
                line = stream.readline()
                if not line:
                    break
                text = line.decode("utf-8").rstrip("\r\n")
                if text.startswith("data:"):
                    data = text[5:].strip()
            return status, json.loads(data) if data else None
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _request_path(self, template: str, trigger: dict) -> str:
        values = {
            "run_id": self.run_id,
            "work_unit_id": WORK_UNIT_ID,
            "project_id": PROJECT_ID,
        }
        values.update(trigger.get("path_values", {}))
        return trigger.get("request_path") or template.format_map(values)

    def test_the_representative_seeds_are_populated(self) -> None:
        """A representative response must not be an empty one."""
        for path in ("/api/v1/runs", "/api/v1/work-units", "/api/v1/events"):
            with self.subTest(path=path):
                status, _, body = self._http("seeded", "GET", path)
                self.assertEqual(200, status)
                self.assertGreaterEqual(
                    len(json.loads(body)["items"]),
                    2,
                    f"{path} served an empty list; the representatives would "
                    "validate nothing",
                )

    def test_representative_runtime_responses_validate_against_their_advertised_schema(self) -> None:
        for (method, path, status), trigger in sorted(REPRESENTATIVES.items()):
            if trigger.get("sse"):
                continue
            with self.subTest(response=f"{method} {path} {status}"):
                observed, content_type, body = self._http(
                    trigger.get("server", "seeded"),
                    method,
                    self._request_path(path, trigger),
                    token=trigger.get("token", True),
                    headers=trigger.get("headers"),
                    body=trigger.get("body"),
                )
                self.assertEqual(
                    int(status),
                    observed,
                    "the runtime no longer produces the advertised response",
                )
                media = content_type.split(";")[0].strip()
                media_map = self.advertised[(method, path, status)]
                self.assertIn(
                    media,
                    media_map,
                    f"the runtime serves {media}, which the catalog does not "
                    f"advertise for {method} {path} {status}",
                )
                key = media_map[media]
                self.assertIsNotNone(key, f"no named schema advertised for {media}")
                self.assertEqual(
                    [],
                    errors_for_document(
                        validator_for(key), json.loads(body.decode("utf-8"))
                    ),
                    f"the runtime response for {method} {path} {status} does not "
                    f"validate against {key}.schema.json, the schema openapi.yaml "
                    "advertises for it",
                )

    def test_sse_stream_events_validate_against_their_advertised_schema(self) -> None:
        method, path, status = ("GET", "/api/v1/events/stream", "200")
        key = self.advertised[(method, path, status)]["text/event-stream"]
        self.assertIsNotNone(key)
        observed, payload = self._first_sse_event("seeded")
        self.assertEqual(200, observed)
        self.assertIsNotNone(payload, "the stream produced no event to validate")
        self.assertEqual(
            [],
            errors_for_document(validator_for(key), payload),
            f"the first event of the SSE stream does not validate against "
            f"{key}.schema.json, the schema openapi.yaml advertises for it",
        )




if __name__ == "__main__":
    unittest.main()
