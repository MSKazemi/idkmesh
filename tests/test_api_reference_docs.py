"""Drift guards for the API reference pages (issue #746).

``docs/reference/API_ERROR_CATALOG.md``, ``API_LIMITS.md`` and
``API_QUICKSTART.md`` make claims about the running service. Each claim here is
re-derived from the code or the live server, so the pages cannot rot silently:

* every error code the source can emit is in the catalog, and every cataloged
  code exists in the source;
* every cataloged code is reproduced against a live ``create_server`` and the
  documented HTTP status, retryability and ``Retry-After`` must match;
* every documented limit equals the ``operations.limits`` the server publishes,
  the runtime constants, and the validators' accepted range;
* every Python snippet in the quickstart is executed in-process.

Class-based on purpose: ``tests/test_documented_test_counts.py`` counts
module-level ``test_*`` functions and this file must not shift them. Standard
library plus ``jsonschema`` only, because CI installs nothing else.
"""

from __future__ import annotations

import ast
import contextlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock

from idkmesh import service_runtime
from idkmesh.cli import main as cli_main
from idkmesh.connector_store import LocalMetadataStore
from idkmesh.control_tower_api import openapi_document
from idkmesh.control_tower_ui import create_server
from idkmesh.local_ui_security import MAX_BODY_BYTES, TOKEN_HEADER
from idkmesh.product_spine_run_store import ProductSpineRunStore

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
REFERENCE = DOCS / "reference"
CATALOG = REFERENCE / "API_ERROR_CATALOG.md"
LIMITS = REFERENCE / "API_LIMITS.md"
QUICKSTART = REFERENCE / "API_QUICKSTART.md"
OVERVIEW = REFERENCE / "API_OVERVIEW.md"
SPEC = DOCS / "specifications" / "CONTROL_TOWER_LOCAL_API_V0_1.md"

CODE_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")

# Codes that exist in the Product Spine run store but cannot be produced by any
# HTTP route of the read-only Control Tower: they belong to create/cancel/replay
# or to inputs the router validates before the store sees them. They are the
# *complement* of the catalog inside the store's code set, and the test below
# fails when a new store code is in neither place.
LIBRARY_ONLY_STORE_CODES = frozenset(
    {
        "cancel_conflict",
        "cancel_not_allowed",
        "create_requires_proposed",
        "idempotency_conflict",
        "invalid_idempotency_key",
        "invalid_project_id",
        "invalid_projection",
        "invalid_run_id",
        "invalid_sequence",
        "invalid_timestamp",
        "invalid_work_unit_id",
    }
)

# Catalog codes whose exact live trigger is a corrupt connector row; the
# handler's mapping is read from source instead of being reproduced.
STATIC_ONLY_CODES = frozenset({"connection_record_invalid"})


def _rows(text: str) -> list[list[str]]:
    """Cells of every Markdown table row whose first cell is a code span."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("| `"):
            continue
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def _strip_ticks(cell: str) -> str:
    return cell.strip().strip("`")


def _catalog_rows() -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for cells in _rows(CATALOG.read_text(encoding="utf-8")):
        code = _strip_ticks(cells[0])
        if not CODE_RE.match(code):
            continue
        result[code] = {
            "status": int(cells[1]),
            "retryable": {"yes": True, "no": False}[cells[2].lower()],
        }
    return result


def _string_literals_in_error_calls(path: Path) -> set[str]:
    """Error codes the module can emit, read from the AST.

    Collected: the first argument of ``error_document(...)``, any ``code=`` /
    ``overloaded_code=`` keyword, the default of a ``code`` / ``overloaded_code``
    parameter, and an ``overloaded_code`` dictionary entry.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()

    def add(node: ast.AST | None) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if CODE_RE.match(node.value):
                found.add(node.value)
        elif isinstance(node, ast.IfExp):
            add(node.body)
            add(node.orelse)

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "error_document"
            and node.args
        ):
            add(node.args[0])
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg in {"code", "overloaded_code"}:
                    add(keyword.value)
        if isinstance(node, ast.FunctionDef):
            names = [a.arg for a in node.args.args + node.args.kwonlyargs]
            defaults = node.args.defaults + node.args.kw_defaults
            offset = len(names) - len(defaults)
            for index, default in enumerate(defaults):
                if names[offset + index] in {"code", "overloaded_code"}:
                    add(default)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "overloaded_code":
                    add(value)
    return found


def _store_codes(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == class_name
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            found.add(node.args[0].value)
    return found


def _load_sibling(name: str):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_sibling_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _ServerCase(unittest.TestCase):
    def start(self, **kwargs):
        server = create_server(port=0, **kwargs)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop():
            # An event stream a quickstart snippet left open outlives
            # shutdown(); drain() ends it before the temp store is removed.
            server.drain(timeout=5.0)
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(stop)
        return server

    @staticmethod
    def raw(server, head: bytes, body: bytes = b"", *, timeout: float = 5.0):
        """Send raw bytes, return ``(status, headers, document-or-None)``."""
        with socket.create_connection(
            ("127.0.0.1", server.server_port), timeout=timeout
        ) as sock:
            sock.sendall(head + body)
            chunks = []
            try:
                while True:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
            except (socket.timeout, ConnectionResetError):
                pass
        data = b"".join(chunks)
        head_part, _, payload = data.partition(b"\r\n\r\n")
        lines = head_part.decode("latin-1").split("\r\n")
        status = int(lines[0].split()[1])
        headers = {}
        for line in lines[1:]:
            name, _, value = line.partition(":")
            headers[name.strip().title()] = value.strip()
        try:
            document = json.loads(payload) if payload else None
        except ValueError:
            document = None
        return status, headers, document

    def request(
        self,
        server,
        method,
        path,
        *,
        headers=None,
        body=b"",
        token=True,
        host=None,
        accept="application/json",
        timeout: float = 5.0,
    ):
        lines = [
            f"{method} {path} HTTP/1.1",
            f"Host: {host or '127.0.0.1:%d' % server.server_port}",
        ]
        if accept is not None:
            lines.append(f"Accept: {accept}")
        if token:
            lines.append(f"{TOKEN_HEADER}: {server.ui_token}")
        for name, value in (headers or {}).items():
            lines.append(f"{name}: {value}")
        head = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
        return self.raw(server, head, body, timeout=timeout)


class CatalogSourceTests(unittest.TestCase):
    """The catalog and the source agree about which codes exist."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = _catalog_rows()
        cls.http_codes = _string_literals_in_error_calls(
            REPO_ROOT / "idkmesh" / "control_tower_ui.py"
        )
        cls.store_codes = _store_codes(
            REPO_ROOT / "idkmesh" / "product_spine_run_store.py",
            "ProductSpineRunStoreError",
        ) | _store_codes(
            REPO_ROOT / "idkmesh" / "connector_control_read.py",
            "ConnectorControlReadError",
        )

    def test_the_catalog_is_not_empty_and_codes_match_the_error_schema(self):
        self.assertGreaterEqual(len(self.catalog), 30)
        schema = json.loads(
            (REPO_ROOT / "schemas" / "idkmesh-api-error-v0.1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        pattern = schema["properties"]["error"]["properties"]["code"]["pattern"]
        pattern = pattern.replace("(?!\n)", "")
        for code in self.catalog:
            with self.subTest(code=code):
                self.assertRegex(code, pattern)

    def test_every_code_the_http_layer_can_emit_is_cataloged(self):
        self.assertGreaterEqual(len(self.http_codes), 20)
        self.assertEqual(sorted(self.http_codes - set(self.catalog)), [])

    def test_every_store_code_is_cataloged_or_declared_library_only(self):
        undeclared = self.store_codes - set(self.catalog) - LIBRARY_ONLY_STORE_CODES
        self.assertEqual(
            sorted(undeclared),
            [],
            "a new run-store error code must be cataloged or declared library-only",
        )

    def test_library_only_codes_are_not_also_cataloged(self):
        self.assertEqual(sorted(LIBRARY_ONLY_STORE_CODES & set(self.catalog)), [])
        self.assertEqual(
            sorted(LIBRARY_ONLY_STORE_CODES - self.store_codes),
            [],
            "LIBRARY_ONLY_STORE_CODES names a code the store no longer raises",
        )

    def test_every_cataloged_code_exists_in_the_source(self):
        known = self.http_codes | self.store_codes
        self.assertEqual(
            sorted(set(self.catalog) - known),
            [],
            "the catalog documents a code the source never emits",
        )

    def test_the_spec_code_list_is_a_subset_of_the_catalog(self):
        text = SPEC.read_text(encoding="utf-8")
        section = text.split("Stable v0.1 codes include:")[1].split("## Service limits")[0]
        spec_codes = set(re.findall(r"^- `([a-z_]+)`", section, re.MULTILINE))
        self.assertGreaterEqual(len(spec_codes), 25)
        self.assertEqual(sorted(spec_codes - set(self.catalog)), [])

    def test_only_the_capacity_trio_is_retryable(self):
        retryable = {c for c, row in self.catalog.items() if row["retryable"]}
        self.assertEqual(retryable, {"overloaded", "too_many_streams", "shutting_down"})

    def test_the_connector_record_mapping_is_read_from_source(self):
        source = (REPO_ROOT / "idkmesh" / "control_tower_ui.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('exc.code in {"invalid_cursor", "invalid_limit"}', source)
        self.assertEqual(self.catalog["connection_record_invalid"]["status"], 500)
        self.assertIn("connection_record_invalid", self.store_codes)

    def test_the_openapi_error_statuses_are_documented_in_the_catalog(self):
        catalog_statuses = {row["status"] for row in self.catalog.values()}
        declared = set()
        for operations in openapi_document()["paths"].values():
            for operation in operations.values():
                declared |= {
                    int(status)
                    for status in operation.get("responses", {})
                    if status.isdigit() and int(status) >= 400
                }
        self.assertEqual(sorted(declared - catalog_statuses), [])


class CatalogLiveTests(_ServerCase):
    """Every cataloged code is reproduced against a real server."""

    def test_each_cataloged_code_matches_the_live_server(self):
        catalog = _catalog_rows()
        helpers = _load_sibling("test_run_evidence_store")
        tmp = tempfile.TemporaryDirectory(prefix="idkmesh-api-catalog-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        db = root / "store.sqlite3"
        good = helpers.seed_offline_run(db, root, key="idem/good")
        tampered = helpers.seed_offline_run(db, root, key="idem/tampered")
        store = LocalMetadataStore(db)
        ProductSpineRunStore(store).create(
            helpers.cli_run("run/cli-1"),
            idempotency_key="cli-1",
            created_at="2026-10-02T00:00:00Z",
        )
        helpers.add_foreign_rows(store)
        helpers.rewrite_metadata(
            db,
            tampered.run.run_id,
            lambda m: m["evidence_report"]["warnings"].append("tampered"),
        )
        corrupt = helpers.seed_offline_run(db, root, key="idem/corrupt")
        helpers.rewrite_metadata(
            db, corrupt.run.run_id, lambda m: m.__setitem__("projection", None)
        )

        server = self.start(product_spine_store_path=str(db))
        bare = self.start()  # no store configured
        short = self.start(request_timeout=0.3, product_spine_store_path=str(db))
        tiny = self.start(
            max_concurrent_requests=1,
            max_sse_clients=1,
            product_spine_store_path=str(db),
        )
        draining = self.start(product_spine_store_path=str(db))
        garbage = root / "garbage.sqlite3"
        garbage.write_bytes(b"this is not a sqlite database" * 20)
        broken = self.start(product_spine_store_path=str(garbage))

        post = "/api/v1/run-evidence/inspect"
        json_type = {"Content-Type": "application/json"}

        def get(srv, path, **kwargs):
            return self.request(srv, "GET", path, **kwargs)

        def posted(srv, headers, body, **kwargs):
            return self.request(srv, "POST", post, headers=headers, body=body, **kwargs)

        def overloaded():
            self.assertEqual(tiny.limiter.admit(), service_runtime.ADMITTED)
            try:
                return get(tiny, "/api/v1/runs")
            finally:
                tiny.limiter.release()

        def too_many_streams():
            self.assertEqual(tiny.sse_limiter.admit(), service_runtime.ADMITTED)
            try:
                return get(
                    tiny,
                    "/api/v1/events/stream",
                    accept="text/event-stream",
                )
            finally:
                tiny.sse_limiter.release()

        def metrics_unavailable():
            with mock.patch("idkmesh.control_tower_ui.SERVICE_NAME", 'bad"label'):
                return get(
                    server, "/api/v1/metrics/prometheus", accept="text/plain"
                )

        def shutting_down():
            draining.drain(timeout=2.0)
            return get(draining, "/api/v1/runs")

        def request_timeout():
            head = (
                f"POST {post} HTTP/1.1\r\nHost: 127.0.0.1:{short.server_port}\r\n"
                f"Accept: application/json\r\n{TOKEN_HEADER}: {short.ui_token}\r\n"
                "Content-Type: application/json\r\nContent-Length: 50\r\n\r\n"
            ).encode("latin-1")
            return self.raw(short, head, b'{"partial":')

        repro = {
            "invalid_host": lambda: get(server, "/api/v1/status", host="evil.example"),
            "invalid_session_token": lambda: get(server, "/api/v1/status", token=False),
            "unsupported_api_version": lambda: get(server, "/api/v9/status"),
            "not_acceptable": lambda: get(server, "/api/v1/status", accept="text/html"),
            "unexpected_query_parameters": lambda: get(server, "/api/v1/status?x=1"),
            "method_not_allowed": lambda: self.request(server, "POST", "/api/v1/status"),
            "preflight_not_supported": lambda: self.request(
                server, "OPTIONS", "/api/v1/runs"
            ),
            "not_found": lambda: get(server, "/api/v1/nope"),
            "unsupported_transfer_encoding": lambda: posted(
                server,
                {**json_type, "Transfer-Encoding": "chunked"},
                b"2\r\n{}\r\n0\r\n\r\n",
            ),
            "unsupported_media_type": lambda: posted(
                server, {"Content-Type": "text/plain", "Content-Length": "2"}, b"{}"
            ),
            "length_required": lambda: posted(server, json_type, b""),
            "invalid_content_length": lambda: posted(
                server, {**json_type, "Content-Length": "+2"}, b"{}"
            ),
            "payload_too_large": lambda: posted(
                server, {**json_type, "Content-Length": str(MAX_BODY_BYTES + 1)}, b""
            ),
            "request_timeout": request_timeout,
            "invalid_utf8": lambda: posted(
                server, {**json_type, "Content-Length": "2"}, b"\xff\xfe"
            ),
            "invalid_run_evidence": lambda: posted(
                server, {**json_type, "Content-Length": "2"}, b"{}"
            ),
            "product_spine_store_not_configured": lambda: get(bare, "/api/v1/runs"),
            "invalid_limit": lambda: get(server, "/api/v1/runs?limit=0"),
            "invalid_cursor": lambda: get(server, "/api/v1/runs?cursor=not-issued"),
            "invalid_state": lambda: get(server, "/api/v1/runs?state=bogus"),
            "invalid_event_type": lambda: get(server, "/api/v1/events?event_type=bogus"),
            "invalid_filter": lambda: get(server, "/api/v1/events?run_id="),
            "invalid_last_event_id": lambda: get(
                server,
                "/api/v1/events/stream",
                accept="text/event-stream",
                headers={"Last-Event-ID": "abc"},
            ),
            "run_not_found": lambda: get(server, "/api/v1/runs/offline/nothing"),
            "work_unit_not_found": lambda: get(server, "/api/v1/work-units/work/none"),
            "project_not_found": lambda: get(server, "/api/v1/projects/project.none"),
            "connection_not_found": lambda: get(
                server, "/api/v1/connections/agent.none"
            ),
            "invalid_connection_id": lambda: get(
                server, "/api/v1/connections/agent:probe"
            ),
            "evidence_not_available": lambda: get(server, "/api/v1/runs/run/cli-1/evidence"),
            "evidence_integrity_error": lambda: get(
                server, f"/api/v1/runs/{tampered.run.run_id}/evidence"
            ),
            "store_error": lambda: get(broken, "/api/v1/runs"),
            "persisted_state_corrupt": lambda: get(
                server, f"/api/v1/runs/{corrupt.run.run_id}"
            ),
            "not_product_spine_cli_run": lambda: get(
                server, "/api/v1/runs/y-foreign-github"
            ),
            "metrics_unavailable": metrics_unavailable,
            "overloaded": overloaded,
            "too_many_streams": too_many_streams,
            "shutting_down": shutting_down,
        }
        self.assertEqual(
            set(repro) | STATIC_ONLY_CODES,
            set(catalog),
            "every cataloged code needs a live reproduction or a static-only note",
        )
        self.assertTrue(good.run.run_id)

        for code, trigger in sorted(repro.items()):
            with self.subTest(code=code):
                status, headers, document = trigger()
                self.assertIsNotNone(document, f"{code}: no JSON error body")
                self.assertEqual(document["kind"], "idkmesh-api-error")
                self.assertIs(document["ok"], False)
                self.assertEqual(document["error"]["code"], code)
                self.assertEqual(status, catalog[code]["status"])
                self.assertIs(
                    document["error"]["retryable"], catalog[code]["retryable"]
                )
                if catalog[code]["retryable"]:
                    self.assertGreaterEqual(int(headers["Retry-After"]), 1)
                    self.assertIn("retry_after_seconds", document["error"]["details"])
                self.assertRegex(headers["X-Request-Id"], r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

    def test_the_unbuilt_decisions_route_is_a_plain_not_found(self):
        tmp = tempfile.TemporaryDirectory(prefix="idkmesh-api-catalog-")
        self.addCleanup(tmp.cleanup)
        server = self.start(
            product_spine_store_path=str(Path(tmp.name) / "store.sqlite3")
        )
        status, _, document = self.request(
            server, "GET", "/api/v1/runs/run/x/decisions"
        )
        self.assertEqual((status, document["error"]["code"]), (404, "not_found"))
        self.assertIn("/decisions", CATALOG.read_text(encoding="utf-8"))

    def test_unsupported_api_version_names_the_supported_versions(self):
        server = self.start()
        _, _, document = self.request(server, "GET", "/api/v9/status")
        self.assertEqual(document["error"]["details"]["supported_versions"], ["v1"])
        text = CATALOG.read_text(encoding="utf-8")
        self.assertIn("supported_versions", text)

    def test_invalid_last_event_id_beyond_the_stream_reports_the_latest_sequence(self):
        text = CATALOG.read_text(encoding="utf-8")
        self.assertIn("latest_sequence", text)
        tmp = tempfile.TemporaryDirectory(prefix="idkmesh-api-catalog-")
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "store.sqlite3"
        ProductSpineRunStore(LocalMetadataStore(db))
        server = self.start(product_spine_store_path=str(db))
        status, _, document = self.request(
            server,
            "GET",
            "/api/v1/events/stream",
            accept="text/event-stream",
            headers={"Last-Event-ID": "999"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(document["error"]["code"], "invalid_last_event_id")
        self.assertIn("latest_sequence", document["error"]["details"])


class LimitsTests(_ServerCase):
    """Every documented limit is the one the server publishes and enforces."""

    @classmethod
    def setUpClass(cls):
        cls.text = LIMITS.read_text(encoding="utf-8")

    def documented_limits(self) -> dict[str, object]:
        section = self.text.split("## Published limits")[1].split("\n## ")[0]
        limits = {}
        for cells in _rows(section):
            limits[_strip_ticks(cells[0])] = json.loads(_strip_ticks(cells[1]))
        return limits

    def test_documented_limits_equal_what_the_server_publishes(self):
        server = self.start()
        status, _, document = self.request(server, "GET", "/api/v1/status")
        self.assertEqual(status, 200)
        published = document["operations"]["limits"]
        self.assertEqual(self.documented_limits(), published)

    def test_documented_limits_equal_the_runtime_constants(self):
        documented = self.documented_limits()
        expected = {
            "request_timeout_seconds": service_runtime.DEFAULT_REQUEST_TIMEOUT_SECONDS,
            "max_concurrent_requests": service_runtime.DEFAULT_MAX_CONCURRENT_REQUESTS,
            "retry_after_seconds": service_runtime.DEFAULT_RETRY_AFTER_SECONDS,
            "drain_timeout_seconds": service_runtime.DEFAULT_DRAIN_TIMEOUT_SECONDS,
            "max_request_line_bytes": service_runtime.MAX_REQUEST_LINE_BYTES,
            "max_header_line_bytes": service_runtime.MAX_HEADER_LINE_BYTES,
            "max_header_count": service_runtime.MAX_HEADER_COUNT,
            "max_request_body_bytes": MAX_BODY_BYTES,
            "max_sse_clients": service_runtime.DEFAULT_MAX_SSE_CLIENTS,
            "sse_heartbeat_seconds": service_runtime.SSE_HEARTBEAT_SECONDS,
            "sse_max_stream_seconds": service_runtime.SSE_MAX_STREAM_SECONDS,
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(documented[key], value)

    def test_documented_flag_ranges_are_the_ranges_the_validators_enforce(self):
        section = self.text.split("## Tunable limits")[1].split("\n## ")[0]
        rows = {_strip_ticks(c[0]): c for c in _rows(section)}
        validators = {
            "--request-timeout": (
                service_runtime.validate_request_timeout,
                float,
                "request_timeout_seconds",
            ),
            "--max-concurrent-requests": (
                service_runtime.validate_max_concurrent_requests,
                int,
                "max_concurrent_requests",
            ),
            "--max-sse-clients": (
                service_runtime.validate_max_sse_clients,
                int,
                "max_sse_clients",
            ),
        }
        self.assertEqual(set(rows), set(validators))
        defaults = self.documented_limits()
        for flag, (validate, kind, key) in validators.items():
            with self.subTest(flag=flag):
                low = kind(_strip_ticks(rows[flag][1]))
                high = kind(_strip_ticks(rows[flag][2]))
                self.assertEqual(kind(_strip_ticks(rows[flag][3])), defaults[key])
                self.assertEqual(validate(low), low)
                self.assertEqual(validate(high), high)
                step = 0.01 if kind is float else 1
                for outside in (low - step, high + step):
                    with self.assertRaises(ValueError):
                        validate(outside)

    def test_the_cli_exposes_every_documented_flag(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            with self.assertRaises(SystemExit):
                cli_main(["control-tower", "--help"])
        for flag in ("--request-timeout", "--max-concurrent-requests", "--max-sse-clients"):
            with self.subTest(flag=flag):
                self.assertIn(flag, buffer.getvalue())
                self.assertIn(flag, self.text)

    def test_parser_bounds_answer_the_documented_statuses(self):
        server = self.start()
        host = f"127.0.0.1:{server.server_port}"
        long_path = "/" + "a" * (service_runtime.MAX_REQUEST_LINE_BYTES + 1)
        status, _, _ = self.raw(
            server, f"GET {long_path} HTTP/1.1\r\nHost: {host}\r\n\r\n".encode()
        )
        self.assertEqual(status, 414)

        def with_extra(count: int) -> bytes:
            extra = "".join(f"X-F{i}: v\r\n" for i in range(count))
            return f"GET /healthz HTTP/1.1\r\nHost: {host}\r\n{extra}\r\n".encode()

        # Host plus 98 extras is exactly 99 header fields: accepted. One more: 431.
        ok, _, _ = self.raw(server, with_extra(service_runtime.MAX_HEADER_COUNT - 1))
        self.assertEqual(ok, 200)
        status, _, _ = self.raw(server, with_extra(service_runtime.MAX_HEADER_COUNT))
        self.assertEqual(status, 431)
        big = "x" * (service_runtime.MAX_HEADER_LINE_BYTES + 1)
        status, _, _ = self.raw(
            server, f"GET /healthz HTTP/1.1\r\nHost: {host}\r\nX-Big: {big}\r\n\r\n".encode()
        )
        self.assertEqual(status, 431)
        self.assertIn("414", self.text)
        self.assertIn("431", self.text)

    def test_one_request_per_connection_is_the_documented_policy(self):
        server = self.start()
        status, headers, _ = self.request(server, "GET", "/api/v1/status")
        self.assertEqual(status, 200)
        self.assertIn("close_after_response", self.text)
        self.assertEqual(
            self.documented_limits()["connection_policy"], "close_after_response"
        )
        self.assertNotIn("keep-alive", headers.get("Connection", "").lower())

    def test_429_is_documented_as_not_emitted(self):
        self.assertEqual(self.documented_limits()["per_client_rate_limit"], "not_implemented")
        self.assertEqual(
            [c for c, r in _catalog_rows().items() if r["status"] == 429], []
        )
        self.assertIn("429", self.text)


class ResponseHeaderTests(_ServerCase):
    def test_the_documented_response_headers_are_sent(self):
        text = QUICKSTART.read_text(encoding="utf-8")
        server = self.start()
        status, headers, _ = self.request(
            server, "GET", "/api/v1/status", headers={"X-Request-ID": "doc-check-1"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Request-Id"], "doc-check-1")
        for name in (
            service_runtime.REQUEST_ID_HEADER,
            service_runtime.SERVICE_HEADER,
            service_runtime.SERVICE_VERSION_HEADER,
            service_runtime.READ_ONLY_HEADER,
            "X-IDKMesh-API-Version",
            "X-IDKMesh-Content-Digest",
            "ETag",
            "Retry-After",
            "Allow",
        ):
            with self.subTest(header=name):
                self.assertIn(f"`{name}`", text)
                if name not in {"Retry-After", "Allow"}:
                    self.assertIn(name.title(), headers)


class QuickstartTests(_ServerCase):
    """The quickstart's Python snippets run, unchanged, against a live server."""

    TOKEN = "q" * 40

    def setUp(self):
        self.text = QUICKSTART.read_text(encoding="utf-8")
        tmp = tempfile.TemporaryDirectory(prefix="idkmesh-quickstart-")
        self.addCleanup(tmp.cleanup)
        self.store = str(Path(tmp.name) / "state.sqlite")

    def snippets(self, language: str) -> list[str]:
        return re.findall(rf"```{language}\n(.*?)```", self.text, re.DOTALL)

    def test_the_python_snippets_execute_against_a_live_control_tower(self):
        example = REPO_ROOT / "examples" / "api" / "product-spine-run.example.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                cli_main(
                    [
                        "run",
                        "create",
                        str(example),
                        "--store",
                        self.store,
                        "--idempotency-key",
                        "quickstart-1",
                    ]
                ),
                0,
            )
        with mock.patch.dict(
            "os.environ", {"IDKMESH_CONTROL_TOWER_TOKEN": self.TOKEN}
        ):
            server = self.start(product_spine_store_path=self.store)
        snippets = self.snippets("python")
        self.assertGreaterEqual(len(snippets), 4)
        namespace: dict[str, object] = {"__name__": "quickstart"}
        url = f"http://127.0.0.1:{server.server_port}"
        output = io.StringIO()
        previous = os.getcwd()
        os.chdir(REPO_ROOT)  # snippets use repository-relative example paths
        self.addCleanup(os.chdir, previous)
        with mock.patch.dict(
            "os.environ", {"IDKMESH_CONTROL_TOWER_TOKEN": self.TOKEN}
        ):
            for index, snippet in enumerate(snippets):
                source = snippet.replace("http://127.0.0.1:8770", url)
                with self.subTest(snippet=index), contextlib.redirect_stdout(output):
                    exec(compile(source, f"<quickstart-{index}>", "exec"), namespace)
        printed = output.getvalue()
        self.assertIn("run/example-1", printed)

    def test_curl_examples_name_only_routes_the_openapi_document_declares(self):
        paths = set(openapi_document()["paths"])
        patterns = [
            re.compile("^" + re.sub(r"\{[^}]+\}", ".+", path) + "$") for path in paths
        ]
        urls = re.findall(r"http://127\.0\.0\.1:8770(/[A-Za-z0-9_./{}-]*)", self.text)
        self.assertGreaterEqual(len(urls), 3)
        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(any(p.match(url) for p in patterns), url)

    def test_the_client_methods_it_names_exist(self):
        from idkmesh.api_client import ControlTowerClient

        code = "\n".join(self.snippets("python"))
        called = set(re.findall(r"\bclient\.([a-z_]+)\(", code))
        named = set(re.findall(r"`((?:get|list|inspect)_[a-z_]+|status)`", self.text))
        self.assertGreaterEqual(len(called), 6)
        self.assertGreaterEqual(len(named), 6)
        for name in sorted(called | named):
            with self.subTest(method=name):
                self.assertTrue(callable(getattr(ControlTowerClient, name, None)))


class ClientTaxonomyTests(unittest.TestCase):
    def test_the_catalog_lists_exactly_the_clients_exception_classes(self):
        import idkmesh.api_client as client_module

        text = CATALOG.read_text(encoding="utf-8")
        section = text.split("## Python client: exception taxonomy")[1]
        documented = {
            _strip_ticks(cells[0])
            for cells in _rows(section)
            if _strip_ticks(cells[0]).endswith("Error")
        }
        actual = {
            name
            for name in client_module.__all__
            if name.endswith("Error") and name != "ControlTowerClientError"
        }
        self.assertEqual(documented, actual)
        base = client_module.ControlTowerClientError
        for name in documented:
            with self.subTest(name=name):
                self.assertTrue(issubclass(getattr(client_module, name), base))
        self.assertTrue(
            issubclass(client_module.IntegrityError, client_module.ProtocolError)
        )
        for attribute in ("status_code", "code", "message", "retryable", "details", "request_id"):
            self.assertIn(f"`{attribute}`", section)


class OverviewTests(unittest.TestCase):
    """``API_OVERVIEW.md`` is a map: every pointer on it must resolve."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = OVERVIEW.read_text(encoding="utf-8")
        cls.routes = cls.text.split("## Routes")[1].split("## Download")[0]

    def test_every_served_route_is_listed_and_no_unserved_route_is(self):
        paths = openapi_document()["paths"]
        listed = set(re.findall(r"`(?:GET|POST) (/[A-Za-z0-9_./{}-]*)`", self.routes))
        self.assertEqual(listed, set(paths))

    def test_documented_methods_match_the_openapi_document(self):
        paths = openapi_document()["paths"]
        found = re.findall(r"`(GET|POST) (/[A-Za-z0-9_./{}-]*)`", self.routes)
        self.assertGreaterEqual(len(found), 16)
        for method, route in found:
            with self.subTest(route=route):
                self.assertIn(method.lower(), paths[route])

    def test_every_schema_file_named_exists_and_is_valid_json(self):
        names = re.findall(r"`(idkmesh-[a-z-]+-v0\.1\.schema\.json)`", self.text)
        self.assertGreaterEqual(len(names), 10)
        for name in names:
            with self.subTest(schema=name):
                path = REPO_ROOT / "schemas" / name
                self.assertTrue(path.is_file())
                json.loads(path.read_text(encoding="utf-8"))

    def test_every_client_method_it_names_exists(self):
        from idkmesh.api_client import ControlTowerClient

        names = set(re.findall(r"`([a-z_]+)\(\)`", self.routes))
        self.assertGreaterEqual(len(names), 10)
        for name in sorted(names):
            with self.subTest(method=name):
                self.assertTrue(callable(getattr(ControlTowerClient, name, None)))

    def test_relative_links_resolve(self):
        targets = re.findall(
            r"\]\((?!https?://|#)([^)#]+)(?:#[^)]*)?\)", self.text
        )
        self.assertGreaterEqual(len(targets), 8)
        for target in targets:
            with self.subTest(link=target):
                self.assertTrue((OVERVIEW.parent / target).resolve().exists(), target)

    def test_in_page_anchors_exist_in_the_quickstart(self):
        quickstart = QUICKSTART.read_text(encoding="utf-8")
        slugs = {
            re.sub(r"[^a-z0-9 -]", "", heading.lower()).strip().replace(" ", "-")
            for heading in re.findall(r"^#+ (.+)$", quickstart, re.M)
        }
        anchors = re.findall(r"API_QUICKSTART\.md#([a-z0-9-]+)", self.text)
        self.assertGreaterEqual(len(anchors), 2)
        for anchor in anchors:
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, slugs)

    def test_it_states_there_are_no_scopes_and_marks_unbuilt_surfaces(self):
        self.assertRegex(self.text, r"(?i)no users, roles or \*\*scopes\*\*")
        self.assertIn("#740", self.text)
        self.assertRegex(self.text, r"(?i)no JavaScript client is shipped")
        from idkmesh.api_client import ControlTowerClient

        self.assertFalse(hasattr(ControlTowerClient, "record_human_decision"))


class IntegrationTests(unittest.TestCase):
    PAGES = (
        "reference/API_OVERVIEW.md",
        "reference/API_ERROR_CATALOG.md",
        "reference/API_LIMITS.md",
        "reference/API_QUICKSTART.md",
    )

    def test_pages_have_front_matter_and_are_indexed(self):
        docs_index = (DOCS / "README.md").read_text(encoding="utf-8")
        reference_index = (REFERENCE / "README.md").read_text(encoding="utf-8")
        for page in self.PAGES:
            with self.subTest(page=page):
                text = (DOCS / page).read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"))
                self.assertRegex(text.split("---\n")[1], r'description: ".{40,}"')
                self.assertIn(page, docs_index)
                self.assertIn(Path(page).name, reference_index)

    def test_pages_are_linked_from_the_quick_reference_tutorial_and_spec(self):
        for source in (
            REFERENCE / "CLI_HTTP_QUICK_REFERENCE.md",
            DOCS / "RUN_LIFECYCLE_TUTORIAL.md",
            SPEC,
        ):
            text = source.read_text(encoding="utf-8")
            with self.subTest(source=source.name):
                self.assertIn("API_ERROR_CATALOG.md", text)

    def test_unbuilt_surfaces_are_marked_planned_not_available(self):
        quickstart = QUICKSTART.read_text(encoding="utf-8")
        self.assertIn("#740", quickstart)
        self.assertRegex(quickstart, r"(?i)planned")
        for token in ("record_human_decision", "/decisions"):
            self.assertIn(token, quickstart)
        # The client genuinely has no such method, so the "planned" claim is true.
        from idkmesh.api_client import ControlTowerClient

        self.assertFalse(hasattr(ControlTowerClient, "record_human_decision"))
        # The event-stream helper shipped, so it must not be listed as planned.
        self.assertTrue(callable(getattr(ControlTowerClient, "stream_events", None)))
        planned = quickstart.split("## Planned, not available today")[1]
        self.assertNotIn("event stream", planned)

    def test_the_spec_no_longer_says_the_client_omits_openapi_and_metrics(self):
        text = SPEC.read_text(encoding="utf-8")
        self.assertNotIn("`openapi.json` discovery,\n`metrics`", text)
        self.assertIn("get_openapi", text)
        self.assertIn("get_metrics", text)


if __name__ == "__main__":
    unittest.main()
