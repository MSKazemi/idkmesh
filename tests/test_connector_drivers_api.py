"""GET /api/v1/connector-drivers: static, secret-free driver declarations (#580).

The route is a pure projection of the registry's descriptors. These tests pin
its shape to the registry, its fail-closed behaviour, its ordering, and the
absence of any secret-looking field, using the same live-server style as the
sibling connection routes.
"""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import re
import threading
import unittest
from unittest import mock

from idkmesh.api_client import (
    ControlTowerClient,
    ProtocolError,
)
from idkmesh.connector_control_read import (
    ConnectorControlReadError,
    DRIVER_REGISTRY_NAME,
    list_connector_drivers,
)
from idkmesh.connector_registry import (
    ConnectorRegistry,
    DriverCapabilities,
    StaticFakeDriver,
    build_fake_registry,
)
from idkmesh.control_tower_ui import TOKEN_ENV, TOKEN_HEADER, create_server

ROOT = Path(__file__).resolve().parents[1]
PATH = "/api/v1/connector-drivers"
TOKEN = "d" * 32

# Field names / values that must never appear in a driver declaration.
_SECRET_NAME = re.compile(
    r"secret|token|password|passwd|api[_-]?key|credential|auth[_-]?ref|bearer",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(r"sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|SENTINEL")


def _secret_looking(document: object) -> list[str]:
    """Return every key or string value in ``document`` that looks secret."""
    found: list[str] = []
    if isinstance(document, dict):
        for key, value in document.items():
            if _SECRET_NAME.search(str(key)):
                found.append(f"key:{key}")
            found.extend(_secret_looking(value))
    elif isinstance(document, list):
        for value in document:
            found.extend(_secret_looking(value))
    elif isinstance(document, str) and _SECRET_VALUE.search(document):
        found.append(f"value:{document}")
    return found


def _fake_driver(kind: str, driver_id: str, version: str = "0.1"):
    return StaticFakeDriver(
        kind=kind,
        driver_id=driver_id,
        driver_version=version,
        capabilities=DriverCapabilities(),
    )


class _ServerCase(unittest.TestCase):
    def start(self, *, store: str | None = None):
        with mock.patch.dict("os.environ", {TOKEN_ENV: TOKEN}):
            server = create_server(port=0, product_spine_store_path=store)
        thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.01),
            daemon=True,
        )
        thread.start()

        def cleanup() -> None:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(cleanup)
        return server

    @staticmethod
    def request(server, method: str, path: str, *, token: str | None = TOKEN):
        conn = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=3
        )
        headers = {TOKEN_HEADER: token} if token is not None else {}
        conn.request(method, path, headers=headers)
        response = conn.getresponse()
        body = response.read()
        result = (response.status, dict(response.getheaders()), body)
        conn.close()
        return result


class ConnectorDriversProjectionTests(unittest.TestCase):
    def test_projection_equals_the_registry_descriptors(self) -> None:
        listing = list_connector_drivers()
        expected = [
            {"kind": d.kind, "driver": d.driver_id, "version": d.driver_version}
            for d in build_fake_registry().descriptors()
        ]
        self.assertEqual(listing["drivers"], expected)
        self.assertEqual(listing["registry"], DRIVER_REGISTRY_NAME)
        self.assertIs(listing["live_adapters"], False)
        self.assertEqual(
            {entry["kind"] for entry in listing["drivers"]},
            {"scm", "agent", "model", "execution"},
        )

    def test_ordering_is_deterministic_regardless_of_registration_order(
        self,
    ) -> None:
        drivers = [
            _fake_driver("scm", "zeta"),
            _fake_driver("agent", "beta"),
            _fake_driver("agent", "alpha"),
            _fake_driver("model", "mid"),
        ]
        forward, backward = ConnectorRegistry(), ConnectorRegistry()
        for driver in drivers:
            forward.register(driver)
        for driver in reversed(drivers):
            backward.register(driver)
        first = list_connector_drivers(forward)
        self.assertEqual(first, list_connector_drivers(backward))
        self.assertEqual(
            [(d["kind"], d["driver"]) for d in first["drivers"]],
            [
                ("agent", "alpha"),
                ("agent", "beta"),
                ("model", "mid"),
                ("scm", "zeta"),
            ],
        )

    def test_extra_driver_attributes_and_capabilities_are_never_projected(
        self,
    ) -> None:
        class Leaky:
            kind = "model"
            driver_id = "leaky"
            driver_version = "9.9"
            api_key = "SENTINEL-api-key-value"
            secret_ref = "env:SENTINEL_SECRET_REF"
            settings = {"base_url": "https://SENTINEL.invalid"}

            def declared_capabilities(self, config):  # pragma: no cover
                raise AssertionError("capabilities must not be resolved")

        registry = ConnectorRegistry()
        registry.register(Leaky())
        listing = list_connector_drivers(registry)
        self.assertEqual(
            listing["drivers"],
            [{"kind": "model", "driver": "leaky", "version": "9.9"}],
        )
        self.assertNotIn("SENTINEL", json.dumps(listing))
        self.assertEqual(_secret_looking(listing), [])

    def test_negative_control_the_detector_flags_planted_secrets(self) -> None:
        # Proves the secret detector can fail, so the green results above
        # and below are not vacuous.
        poisoned = {
            "drivers": [
                {
                    "kind": "model",
                    "driver": "x",
                    "version": "1",
                    "api_key": "v",
                    "note": "sk-abcdefgh12345678",
                }
            ]
        }
        self.assertEqual(len(_secret_looking(poisoned)), 2)
        for listing in (list_connector_drivers(),):
            self.assertEqual(_secret_looking(listing), [])

    def test_malformed_declarations_fail_closed_without_echo(self) -> None:
        for kind, driver_id, version in (
            ("scm", "bad/id", "0.1"),
            ("scm", "bad:id", "0.1"),
            ("scm", "-leading", "0.1"),
            ("scm", "SENTINEL" + "x" * 130, "0.1"),
            ("scm", "ok", "v" * 65),
        ):
            with self.subTest(driver_id=driver_id[:12], version=version[:4]):
                registry = ConnectorRegistry()
                registry.register(_fake_driver(kind, driver_id, version))
                with self.assertRaises(ConnectorControlReadError) as ctx:
                    list_connector_drivers(registry)
                self.assertEqual(ctx.exception.code, "driver_record_invalid")
                self.assertNotIn("SENTINEL", str(ctx.exception))
                self.assertNotIn(driver_id, str(ctx.exception))


class ConnectorDriversRouteTests(_ServerCase):
    def test_200_matches_registry_example_and_schema(self) -> None:
        server = self.start()  # no store: the route needs none
        status, headers, body = self.request(server, "GET", PATH)
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        payload = json.loads(body)
        listing = list_connector_drivers()
        self.assertEqual(payload["drivers"], listing["drivers"])
        self.assertEqual(payload["registry"], "offline-fake")
        self.assertIs(payload["live_adapters"], False)
        self.assertEqual(
            payload["kind"], "idkmesh-control-tower-connector-drivers-response"
        )
        example = json.loads(
            (
                ROOT
                / "examples/api/control-tower-connector-drivers-response.example.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(payload, example)
        schema = json.loads(
            (
                ROOT
                / "schemas/idkmesh-control-tower-connector-drivers-response-v0.1.schema.json"
            ).read_text(encoding="utf-8")
        )
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(payload)

    def test_response_is_secret_free_and_byte_stable(self) -> None:
        server = self.start()
        _, _, first = self.request(server, "GET", PATH)
        _, _, second = self.request(server, "GET", PATH)
        self.assertEqual(first, second)
        self.assertEqual(_secret_looking(json.loads(first)), [])

    def test_store_does_not_change_the_answer(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            store = str(Path(tmp) / "state.sqlite3")
            with_store = self.request(self.start(store=store), "GET", PATH)
            without = self.request(self.start(), "GET", PATH)
            # The route never opens the store file.
            self.assertFalse(Path(store).exists())
        self.assertEqual(with_store[0], 200)
        self.assertEqual(json.loads(with_store[2]), json.loads(without[2]))

    def test_head_has_no_body(self) -> None:
        status, headers, body = self.request(self.start(), "HEAD", PATH)
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_missing_or_wrong_token_is_403(self) -> None:
        server = self.start()
        for token in (None, "not-the-session-token"):
            with self.subTest(token=token):
                status, _, body = self.request(
                    server, "GET", PATH, token=token
                )
                self.assertEqual(status, 403)
                self.assertEqual(
                    json.loads(body)["error"]["code"], "invalid_session_token"
                )
                self.assertNotIn(b"fake-agent", body)

    def test_403_precedes_query_and_method_feedback(self) -> None:
        server = self.start()
        for method, path in (("GET", PATH + "?x=1"), ("POST", PATH)):
            status, _, _ = self.request(server, method, path, token=None)
            self.assertEqual(status, 403)

    def test_query_string_is_400(self) -> None:
        server = self.start()
        for query in ("?limit=1", "?x=1", "?cursor=abc"):
            with self.subTest(query=query):
                status, _, body = self.request(server, "GET", PATH + query)
                self.assertEqual(status, 400)
                self.assertEqual(
                    json.loads(body)["error"]["code"],
                    "unexpected_query_parameters",
                )

    def test_write_methods_are_405_get_head_only(self) -> None:
        server = self.start()
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                status, headers, _ = self.request(server, method, PATH)
                self.assertEqual(status, 405)
                self.assertEqual(headers.get("Allow"), "GET, HEAD")

    def test_registry_fault_is_500_without_echo(self) -> None:
        server = self.start()
        error = ConnectorControlReadError(
            "driver_record_invalid", "a registered driver declaration is bad"
        )
        with mock.patch(
            "idkmesh.connector_control_read.list_connector_drivers",
            side_effect=error,
        ):
            status, _, body = self.request(server, "GET", PATH)
        self.assertEqual(status, 500)
        self.assertEqual(
            json.loads(body)["error"]["code"], "driver_record_invalid"
        )

    def test_route_is_advertised_and_openapi_is_get_only(self) -> None:
        server = self.start()
        _, _, body = self.request(server, "GET", "/api/v1/status")
        self.assertEqual(
            json.loads(body)["endpoints"]["list_connector_drivers"],
            "GET " + PATH,
        )
        _, _, body = self.request(server, "GET", "/api/v1/openapi.json")
        self.assertEqual(sorted(json.loads(body)["paths"][PATH]), ["get"])


class ConnectorDriversClientTests(_ServerCase):
    def client(self, server) -> ControlTowerClient:
        return ControlTowerClient(
            f"http://127.0.0.1:{server.server_port}", TOKEN, timeout=2.0
        )

    def test_client_reads_the_listing(self) -> None:
        result = self.client(self.start()).list_connector_drivers()
        self.assertEqual(
            result.value["drivers"], list_connector_drivers()["drivers"]
        )
        self.assertIs(result.value["live_adapters"], False)

    def test_client_fails_closed_on_malformed_documents(self) -> None:
        client = ControlTowerClient(
            "http://127.0.0.1:8770", TOKEN, timeout=1.0
        )
        from idkmesh.api_client import ApiResult, ResponseMetadata
        from idkmesh.work_unit_binding import canonical_digest

        base = {
            "kind": "idkmesh-control-tower-connector-drivers-response",
            "registry": "offline-fake",
            "live_adapters": False,
            "drivers": [{"kind": "scm", "driver": "d", "version": "1"}],
        }
        bad_documents = [
            {**base, "live_adapters": True},
            {**base, "registry": 1},
            {**base, "drivers": "nope"},
            {**base, "drivers": [{"kind": "scm", "driver": "d"}]},
            {
                **base,
                "drivers": [
                    {
                        "kind": "scm",
                        "driver": "d",
                        "version": "1",
                        "api_key": "x",
                    }
                ],
            },
            {**base, "kind": "idkmesh-list"},
        ]
        for document in bad_documents:
            with self.subTest(document=document):
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
                        client.list_connector_drivers()


if __name__ == "__main__":
    unittest.main()
