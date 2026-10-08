"""Contract tests for the official read-only Control Tower Python client (#746)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from idkmesh.api_client import (
    ApiResponseError,
    ApiResult,
    ClientConfigurationError,
    ControlTowerClient,
    IntegrityError,
    ProtocolError,
    ResponseMetadata,
)
from idkmesh.connector_store import LocalMetadataStore
from idkmesh.control_tower_ui import SAMPLE_REPORT, TOKEN_ENV, create_server
from idkmesh.product_spine import ProductSpineRun
from idkmesh.product_spine_run_store import ProductSpineRunStore
from idkmesh.work_unit_binding import canonical_digest


TOKEN = "t" * 32
SHA = "0123456789abcdef0123456789abcdef01234567"


def _run(run_id: str, *, project_id: str = "project.client") -> ProductSpineRun:
    return ProductSpineRun(
        run_id=run_id,
        request_digest="sha256:" + "a" * 64,
        project_id=project_id,
        work_unit_id=f"work/{run_id.rsplit('/', 1)[-1]}",
        work_unit_version=1,
        work_unit_digest="sha256:" + "b" * 64,
        source_revision=SHA,
        authority_mode="agent_candidate",
        routing_policy_version="client-test-v1",
        state="proposed",
    )


class ClientServerCase(unittest.TestCase):
    def start_server(self, store_path: str | None = None):
        with mock.patch.dict("os.environ", {TOKEN_ENV: TOKEN}):
            server = create_server(
                port=0,
                product_spine_store_path=store_path,
            )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(cleanup)
        client = ControlTowerClient(
            f"http://127.0.0.1:{server.server_port}",
            TOKEN,
            timeout=2.0,
        )
        return server, client

    @staticmethod
    def seed(path: str, *run_ids: str) -> None:
        service = ProductSpineRunStore(LocalMetadataStore(path))
        for index, run_id in enumerate(run_ids):
            service.create(
                _run(run_id),
                idempotency_key=f"client-{index}",
                created_at=f"2026-10-08T00:0{index}:00Z",
            )


class ConfigurationTests(unittest.TestCase):
    def test_timeout_is_mandatory_and_validated(self):
        with self.assertRaises(TypeError):
            ControlTowerClient("http://127.0.0.1:8770", TOKEN)
        for timeout in (0, -1, True, float("inf")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ClientConfigurationError):
                    ControlTowerClient(
                        "http://127.0.0.1:8770",
                        TOKEN,
                        timeout=timeout,
                    )

    def test_client_refuses_non_loopback_or_non_http_token_destinations(self):
        for url in (
            "https://127.0.0.1:8770",
            "http://example.com:8770",
            "http://127.0.0.1:8770/api/v1",
            "http://user@127.0.0.1:8770",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ClientConfigurationError):
                    ControlTowerClient(url, TOKEN, timeout=1.0)

    def test_token_contract_matches_local_control_tower_profile(self):
        for token in ("short", "x" * 31, "x" * 32 + " "):
            with self.subTest(token=token):
                with self.assertRaises(ClientConfigurationError):
                    ControlTowerClient(
                        "http://127.0.0.1:8770",
                        token,
                        timeout=1.0,
                    )


class LiveServerTests(ClientServerCase):
    def test_status_exposes_request_id_and_verified_content_digest(self):
        _server, client = self.start_server()
        result = client.status()

        self.assertEqual(
            result.value["kind"],
            "idkmesh-control-tower-status",
        )
        self.assertTrue(result.request_id.startswith("req_"))
        self.assertEqual(
            result.metadata.content_digest,
            canonical_digest(result.value),
        )

    def test_inspect_run_evidence_verifies_snapshot_digest(self):
        _server, client = self.start_server()
        report = json.loads(SAMPLE_REPORT)
        result = client.inspect_run_evidence(report)

        self.assertEqual(
            result.value["snapshot_digest"],
            canonical_digest(result.value["snapshot"]),
        )
        self.assertEqual(
            result.value["snapshot"]["source"]["evidence_report_digest"],
            canonical_digest(report),
        )

    def test_get_run_supports_canonical_run_ids_containing_slash(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = str(Path(tmp) / "state.sqlite")
            self.seed(store, "run:client/one")
            _server, client = self.start_server(store)
            result = client.get_run("run:client/one")

        self.assertEqual(result.value["run"]["run_id"], "run:client/one")
        self.assertFalse(result.value["merge_authority"])

    def test_list_events_pages_and_filters_without_constructing_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = str(Path(tmp) / "state.sqlite")
            self.seed(store, "run/client-one", "run/client-two")
            _server, client = self.start_server(store)

            first = client.list_events(
                limit=1,
                project_id="project.client",
                event_type="run.created",
            )
            self.assertEqual(len(first.value.items), 1)
            self.assertIsNotNone(first.value.next_cursor)

            second = client.list_events(
                limit=1,
                cursor=first.value.next_cursor,
                project_id="project.client",
                event_type="run.created",
            )
            self.assertEqual(len(second.value.items), 1)
            self.assertIsNone(second.value.next_cursor)
            self.assertNotEqual(
                first.value.items[0]["event_id"],
                second.value.items[0]["event_id"],
            )

    def test_list_runs_pages_and_filters_by_exact_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = str(Path(tmp) / "state.sqlite")
            self.seed(store, "run/client-one", "run/client-two")
            _server, client = self.start_server(store)

            first = client.list_runs(limit=1, project_id="project.client")
            self.assertEqual(len(first.value.items), 1)
            self.assertIsNotNone(first.value.next_cursor)

            second = client.list_runs(
                limit=1,
                cursor=first.value.next_cursor,
                project_id="project.client",
            )
            self.assertEqual(len(second.value.items), 1)
            self.assertIsNone(second.value.next_cursor)
            self.assertNotEqual(
                first.value.items[0]["run_id"],
                second.value.items[0]["run_id"],
            )

            matched = client.list_runs(
                state="proposed",
                project_id="project.client",
            )
            self.assertEqual(len(matched.value.items), 2)

            empty = client.list_runs(
                state="cancelled",
                project_id="project.client",
            )
            self.assertEqual(empty.value.items, ())

            with self.assertRaises(ApiResponseError) as caught:
                client.list_runs(state="not-a-state")
            self.assertEqual(caught.exception.code, "invalid_state")
            self.assertEqual(caught.exception.status_code, 400)

    def test_get_run_attempts_echoes_the_requested_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = str(Path(tmp) / "state.sqlite")
            self.seed(store, "run/client-one")
            _server, client = self.start_server(store)
            result = client.get_run_attempts("run/client-one")

        self.assertEqual(
            result.value["kind"],
            "idkmesh-control-tower-run-attempts-response",
        )
        self.assertEqual(result.value["run_id"], "run/client-one")
        self.assertEqual(result.value["attempts"], [])

    def test_work_unit_and_project_reads_expose_derived_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = str(Path(tmp) / "state.sqlite")
            self.seed(store, "run/client-one")
            _server, client = self.start_server(store)

            work_unit = client.get_work_unit("work/client-one")
            resource = work_unit.value["work_unit"]
            self.assertEqual(resource["id"], "work/client-one")
            self.assertEqual(resource["run_count"], 1)
            self.assertEqual(resource["revisions"][0]["source_revision"], SHA)

            page = client.list_work_units(project_id="project.client")
            self.assertEqual(
                [item["id"] for item in page.value.items],
                ["work/client-one"],
            )

            project = client.get_project("project.client")
            summary = project.value["project"]
            self.assertEqual(summary["project_id"], "project.client")
            self.assertEqual(summary["run_count"], 1)
            self.assertEqual(summary["work_unit_count"], 1)
            self.assertEqual(summary["runs_by_state"]["proposed"], 1)
            self.assertEqual(sum(summary["runs_by_state"].values()), 1)

    def test_unknown_resources_fail_with_stable_error_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = str(Path(tmp) / "state.sqlite")
            self.seed(store, "run/client-one")
            _server, client = self.start_server(store)

            cases = [
                (
                    "get_run",
                    "run_not_found",
                    lambda: client.get_run("run/missing"),
                ),
                (
                    "get_run_attempts",
                    "run_not_found",
                    lambda: client.get_run_attempts("run/missing"),
                ),
                (
                    "get_work_unit",
                    "work_unit_not_found",
                    lambda: client.get_work_unit("work/missing"),
                ),
                (
                    "get_project",
                    "project_not_found",
                    lambda: client.get_project("project.missing"),
                ),
            ]
            for name, expected_code, call in cases:
                with self.subTest(method=name):
                    with self.assertRaises(ApiResponseError) as caught:
                        call()
                    self.assertEqual(caught.exception.code, expected_code)
                    self.assertEqual(caught.exception.status_code, 404)

    def test_api_error_exposes_stable_code_retryability_and_request_id(self):
        server, _client = self.start_server()
        wrong = ControlTowerClient(
            f"http://127.0.0.1:{server.server_port}",
            "z" * 32,
            timeout=2.0,
        )
        with self.assertRaises(ApiResponseError) as caught:
            wrong.status()

        error = caught.exception
        self.assertEqual(error.status_code, 403)
        self.assertEqual(error.code, "invalid_session_token")
        self.assertFalse(error.retryable)
        self.assertTrue(error.request_id.startswith("req_"))


class _FakeResponse:
    def __init__(
        self,
        payload: dict,
        *,
        status: int = 200,
        digest: str | None = None,
    ) -> None:
        self.status = status
        self._raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        self._headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-Request-ID": "req_test",
            "X-IDKMesh-Content-Digest": (
                canonical_digest(payload) if digest is None else digest
            ),
        }

    def read(self):
        return self._raw

    def getheader(self, name):
        return self._headers.get(name)


class _FakeConnection:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def request(self, method, path, body=None, headers=None):
        self.requests.append((method, path, body, dict(headers or {})))

    def getresponse(self):
        return self.response

    def close(self):
        pass


class FailClosedTransportTests(unittest.TestCase):
    def client(self):
        return ControlTowerClient(
            "http://127.0.0.1:8770",
            TOKEN,
            timeout=1.0,
        )

    def test_wrong_outer_content_digest_fails_closed(self):
        payload = {
            "kind": "idkmesh-control-tower-status",
            "ok": True,
        }
        connection = _FakeConnection(
            _FakeResponse(payload, digest="sha256:" + "0" * 64)
        )
        with mock.patch(
            "idkmesh.api_client.http.client.HTTPConnection",
            return_value=connection,
        ):
            with self.assertRaises(IntegrityError):
                self.client().status()
        self.assertEqual(len(connection.requests), 1)

    def test_retryable_server_error_is_not_automatically_retried(self):
        payload = {
            "api_version": "v1",
            "schema_version": "0.1",
            "kind": "idkmesh-api-error",
            "ok": False,
            "error": {
                "code": "overloaded",
                "message": "busy",
                "retryable": True,
            },
        }
        connection = _FakeConnection(_FakeResponse(payload, status=503))
        with mock.patch(
            "idkmesh.api_client.http.client.HTTPConnection",
            return_value=connection,
        ) as factory:
            with self.assertRaises(ApiResponseError) as caught:
                self.client().status()

        self.assertTrue(caught.exception.retryable)
        self.assertEqual(len(connection.requests), 1)
        factory.assert_called_once()

    def test_retained_evidence_is_verified_independently_of_outer_response(self):
        client = self.client()
        report = {"kind": "idkmesh-run-evidence-report", "schema_version": "0.1"}
        document = {
            "kind": "idkmesh-control-tower-run-evidence-response",
            "run_id": "run/example",
            "evidence_report": report,
            "evidence_report_digest": "sha256:" + "0" * 64,
        }
        result = ApiResult(
            value=document,
            metadata=ResponseMetadata(
                status_code=200,
                request_id="req_test",
                content_digest=canonical_digest(document),
            ),
        )
        with mock.patch.object(client, "_request", return_value=result):
            with self.assertRaises(IntegrityError):
                client.get_run_evidence("run/example")

    def test_inspection_snapshot_is_verified_independently(self):
        client = self.client()
        snapshot = {
            "kind": "idkmesh-control-tower-snapshot",
            "schema_version": "0.1",
        }
        document = {
            "kind": "idkmesh-control-tower-inspection-response",
            "snapshot": snapshot,
            "snapshot_digest": "sha256:" + "0" * 64,
        }
        result = ApiResult(
            value=document,
            metadata=ResponseMetadata(
                status_code=200,
                request_id="req_test",
                content_digest=canonical_digest(document),
            ),
        )
        with mock.patch.object(client, "_request", return_value=result):
            with self.assertRaises(IntegrityError):
                client.inspect_run_evidence(
                    {"kind": "idkmesh-run-evidence-report"}
                )

    def test_list_limit_validation_happens_before_transport(self):
        client = self.client()
        for method in (
            client.list_events,
            client.list_runs,
            client.list_work_units,
        ):
            with self.subTest(method=method.__name__):
                with mock.patch(
                    "idkmesh.api_client.http.client.HTTPConnection"
                ) as factory:
                    with self.assertRaises(ClientConfigurationError):
                        method(limit=0)
                factory.assert_not_called()

    def test_resource_identity_mismatch_fails_closed(self):
        client = self.client()
        cases = [
            (
                client.get_run,
                "run/example",
                {
                    "kind": "idkmesh-control-tower-run-response",
                    "run": {"run_id": "run/other"},
                },
            ),
            (
                client.get_run_attempts,
                "run/example",
                {
                    "kind": "idkmesh-control-tower-run-attempts-response",
                    "run_id": "run/other",
                    "attempts": [],
                },
            ),
            (
                client.get_work_unit,
                "work/example",
                {
                    "kind": "idkmesh-control-tower-work-unit-response",
                    "work_unit": {"id": "work/other"},
                },
            ),
            (
                client.get_project,
                "project.example",
                {
                    "kind": "idkmesh-control-tower-project-response",
                    "project": {"project_id": "project.other"},
                },
            ),
        ]
        for method, resource_id, document in cases:
            with self.subTest(method=method.__name__):
                result = ApiResult(
                    value=document,
                    metadata=ResponseMetadata(
                        status_code=200,
                        request_id="req_test",
                        content_digest=canonical_digest(document),
                    ),
                )
                with mock.patch.object(client, "_request", return_value=result):
                    with self.assertRaises(ProtocolError):
                        method(resource_id)


if __name__ == "__main__":
    unittest.main()
