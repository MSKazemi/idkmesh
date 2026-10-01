"""HTTP tests for GET /api/v1/runs/{run_id}/evidence (ADR-0024, #739).

Also proves the mixed-store behaviour at the API boundary: an offline-spine run
is now readable through the plain run endpoints and listed next to a CLI run,
while admission/error/foreign rows no longer break ``GET /api/v1/runs``.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from idkmesh.connector_store import LocalMetadataStore
from idkmesh.control_tower_ui import create_server
from idkmesh.local_ui_security import TOKEN_HEADER
from idkmesh.product_spine_run_store import ProductSpineRunStore


def _load_sibling(name: str):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_sibling_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_helpers = _load_sibling("test_run_evidence_store")

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"
EVIDENCE_RESPONSE_SCHEMA = (
    "idkmesh-control-tower-run-evidence-response-v0.1.schema.json"
)
TAMPER_MARKER = _helpers.TAMPER_MARKER


def _registry() -> Registry:
    """Every published schema, so cross-file ``$ref``s resolve offline."""
    registry = Registry()
    for path in sorted(SCHEMAS.glob("*.json")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        schema_id = contents.get("$id") if isinstance(contents, dict) else None
        if schema_id:
            registry = registry.with_resource(
                schema_id,
                Resource.from_contents(contents, default_specification=DRAFT202012),
            )
    return registry


def _validate(schema_filename: str, document: dict) -> None:
    schema = json.loads((SCHEMAS / schema_filename).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, registry=_registry()).validate(document)


class _ServerCase(unittest.TestCase):
    server = None

    @classmethod
    def _start(cls, store_path: str | None):
        server = create_server(port=0, product_spine_store_path=store_path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    @classmethod
    def _stop(cls, server, thread) -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    def request(self, method: str, path: str, *, token: bool = True):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=5
        )
        headers = {TOKEN_HEADER: self.server.ui_token} if token else {}
        conn.request(method, path, headers=headers)
        response = conn.getresponse()
        payload = response.read()
        response_headers = dict(response.getheaders())
        conn.close()
        return response.status, response_headers, payload


class ControlTowerRunEvidenceTests(_ServerCase):
    """One mixed store: a good offline run, a tampered one, a CLI run, foreign rows."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="idkmesh-ct-evidence-")
        root = Path(cls._tmp.name)
        cls.db = root / "product-spine.sqlite3"
        cls.good = _helpers.seed_offline_run(cls.db, root, key="idem/good")
        cls.tampered = _helpers.seed_offline_run(cls.db, root, key="idem/tampered")
        store = LocalMetadataStore(cls.db)
        cls.cli_run_id = "run/cli-1"
        ProductSpineRunStore(store).create(
            _helpers.cli_run(cls.cli_run_id),
            idempotency_key="cli-1",
            created_at="2026-10-02T00:00:00Z",
        )
        cls.foreign = _helpers.add_foreign_rows(store)

        def tamper(metadata):
            metadata["evidence_report"]["warnings"].append(TAMPER_MARKER)

        _helpers.rewrite_metadata(cls.db, cls.tampered.run.run_id, tamper)
        cls.server, cls.thread = cls._start(str(cls.db))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._stop(cls.server, cls.thread)
        cls._tmp.cleanup()

    def evidence_path(self, run_id: str) -> str:
        return f"/api/v1/runs/{run_id}/evidence"

    # ---- the evidence endpoint ------------------------------------------------

    def test_serves_the_retained_report_matching_its_schema(self) -> None:
        status, _, body = self.request("GET", self.evidence_path(self.good.run.run_id))
        payload = json.loads(body)

        self.assertEqual(status, 200)
        _validate(EVIDENCE_RESPONSE_SCHEMA, payload)
        self.assertEqual(
            payload["kind"], "idkmesh-control-tower-run-evidence-response"
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["run_id"], self.good.run.run_id)
        self.assertEqual(payload["evidence_report"], self.good.evidence_report)
        self.assertEqual(
            payload["evidence_report_digest"],
            self.good.run.evidence_report_digest,
        )

    def test_the_served_digest_is_the_canonical_digest_of_the_served_report(self) -> None:
        from idkmesh.work_unit_binding import canonical_digest

        _, _, body = self.request("GET", self.evidence_path(self.good.run.run_id))
        payload = json.loads(body)

        self.assertEqual(
            canonical_digest(payload["evidence_report"]),
            payload["evidence_report_digest"],
        )

    def test_a_run_id_containing_slashes_resolves_with_the_evidence_suffix(self) -> None:
        # Offline run ids look like "offline/<hash>" (ADR-0019 suffix resolution).
        self.assertIn("/", self.good.run.run_id)
        status, _, body = self.request("GET", self.evidence_path(self.good.run.run_id))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["run_id"], self.good.run.run_id)

    def test_the_response_carries_an_etag(self) -> None:
        _, headers, _ = self.request("GET", self.evidence_path(self.good.run.run_id))
        self.assertIn("ETag", headers)
        self.assertTrue(headers["ETag"].startswith('"'))

    def test_unknown_run_is_404_run_not_found(self) -> None:
        status, _, body = self.request(
            "GET", self.evidence_path("offline/does-not-exist")
        )
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"]["code"], "run_not_found")

    def test_a_cli_run_has_no_evidence_which_is_distinct_from_no_run(self) -> None:
        status, _, body = self.request("GET", self.evidence_path(self.cli_run_id))
        self.assertEqual(status, 404)
        self.assertEqual(
            json.loads(body)["error"]["code"], "evidence_not_available"
        )

    def test_a_tampered_row_is_500_and_the_report_is_never_served(self) -> None:
        status, _, body = self.request(
            "GET", self.evidence_path(self.tampered.run.run_id)
        )
        payload = json.loads(body)

        self.assertEqual(status, 500)
        self.assertEqual(payload["error"]["code"], "evidence_integrity_error")
        self.assertNotIn("evidence_report", payload)
        self.assertNotIn(TAMPER_MARKER.encode("utf-8"), body)

    def test_decisions_is_still_not_built(self) -> None:
        status, _, body = self.request(
            "GET", f"/api/v1/runs/{self.good.run.run_id}/decisions"
        )
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"]["code"], "not_found")

    def test_query_parameters_are_rejected(self) -> None:
        status, _, body = self.request(
            "GET", self.evidence_path(self.good.run.run_id) + "?limit=1"
        )
        self.assertEqual(status, 400)
        self.assertEqual(
            json.loads(body)["error"]["code"], "unexpected_query_parameters"
        )

    def test_a_missing_token_is_forbidden(self) -> None:
        status, _, _ = self.request(
            "GET", self.evidence_path(self.good.run.run_id), token=False
        )
        self.assertEqual(status, 403)

    def test_every_write_method_is_not_allowed(self) -> None:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            status, headers, _ = self.request(
                method, self.evidence_path(self.good.run.run_id)
            )
            self.assertEqual(status, 405, method)
            self.assertEqual(headers.get("Allow"), "GET, HEAD", method)

    def test_head_returns_headers_without_a_body(self) -> None:
        status, headers, body = self.request(
            "HEAD", self.evidence_path(self.good.run.run_id)
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)

    # ---- the mixed-store behaviour at the API boundary --------------------------

    def test_the_plain_run_read_now_returns_the_offline_run(self) -> None:
        status, _, body = self.request(
            "GET", f"/api/v1/runs/{self.good.run.run_id}"
        )
        payload = json.loads(body)

        self.assertEqual(status, 200)
        _validate("idkmesh-control-tower-run-response-v0.1.schema.json", payload)
        self.assertEqual(payload["run"]["run_id"], self.good.run.run_id)
        self.assertEqual(
            payload["run"]["evidence_report_digest"],
            self.good.run.evidence_report_digest,
        )
        record = LocalMetadataStore(self.db).get_run(self.good.run.run_id)
        assert record is not None
        self.assertEqual(payload["create_request_digest"], record.request_digest)

    def test_a_non_product_spine_row_is_still_not_readable_as_a_run(self) -> None:
        status, _, body = self.request("GET", f"/api/v1/runs/{self.foreign[0]}")
        self.assertEqual(status, 400)
        self.assertEqual(
            json.loads(body)["error"]["code"], "not_product_spine_cli_run"
        )

    def test_the_run_list_includes_both_kinds_and_skips_foreign_rows(self) -> None:
        status, _, body = self.request("GET", "/api/v1/runs?limit=200")
        payload = json.loads(body)

        self.assertEqual(status, 200)
        _validate("idkmesh-list-v0.1.schema.json", payload)
        ids = [item["run_id"] for item in payload["items"]]
        expected = sorted(
            [
                self.good.run.run_id,
                self.tampered.run.run_id,
                self.cli_run_id,
            ]
        )
        self.assertEqual(ids, expected)
        for foreign in self.foreign:
            self.assertNotIn(foreign, ids)
        self.assertIsNone(payload["page"]["next_cursor"])

    def test_list_paging_across_foreign_rows_is_stable_over_http(self) -> None:
        seen: list[str] = []
        cursor = None
        for _ in range(6):
            query = "/api/v1/runs?limit=1"
            if cursor is not None:
                query += f"&cursor={cursor}"
            status, _, body = self.request("GET", query)
            self.assertEqual(status, 200)
            page = json.loads(body)
            seen.extend(item["run_id"] for item in page["items"])
            cursor = page["page"]["next_cursor"]
            if cursor is None:
                break
        else:
            self.fail("paging did not terminate")

        self.assertEqual(len(seen), 3)
        self.assertEqual(len(seen), len(set(seen)))

    def test_work_unit_and_project_reads_still_work_in_the_mixed_store(self) -> None:
        status, _, body = self.request("GET", "/api/v1/projects/MSKazemi/idkmesh")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(json.loads(body)["project"]["run_count"], 2)


class ControlTowerRunEvidenceWithoutAStoreTests(_ServerCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server, cls.thread = cls._start(None)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._stop(cls.server, cls.thread)

    def test_503_without_a_configured_store(self) -> None:
        status, _, body = self.request(
            "GET", "/api/v1/runs/offline/anything/evidence"
        )
        self.assertEqual(status, 503)
        self.assertEqual(
            json.loads(body)["error"]["code"],
            "product_spine_store_not_configured",
        )


if __name__ == "__main__":
    unittest.main()
