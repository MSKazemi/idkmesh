"""Issue #744: the served, read-only Prometheus text exposition route."""
from __future__ import annotations

import http.client
import json
import threading
import unittest
from unittest import mock

from idkmesh.control_tower_ui import TOKEN_ENV, create_server
from idkmesh.local_ui_security import TOKEN_HEADER
from idkmesh.otel_metrics import (
    PROMETHEUS_MAX_BODY_BYTES,
    PROMETHEUS_TEXT_CONTENT_TYPE,
    OtlpMetricsInputError,
    render_prometheus_bytes,
)
from idkmesh.service_runtime import _access_log_route
from tests.test_api_observability_prometheus import ALLOWED_LABELS, _document, _parse

TOKEN = "p" * 32
PATH = "/api/v1/metrics/prometheus"
SENTINEL = "SECRETSENTINEL-3f9a"


class PrometheusRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        patch = mock.patch.dict("os.environ", {TOKEN_ENV: TOKEN}, clear=False)
        patch.start()
        self.addCleanup(patch.stop)
        self.server = create_server(port=0)
        thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        thread.start()

        def stop() -> None:
            self.server.shutdown()
            thread.join(timeout=3)
            self.server.server_close()

        self.addCleanup(stop)

    def call(
        self,
        method: str,
        path: str = PATH,
        *,
        token: bool = True,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        sent = dict(headers or {})
        if token:
            sent[TOKEN_HEADER] = TOKEN
        conn.request(method, path, headers=sent)
        response = conn.getresponse()
        body = response.read()
        result = (
            response.status,
            {k.lower(): v for k, v in response.getheaders()},
            body,
        )
        conn.close()
        return result

    def test_get_serves_valid_closed_label_exposition(self) -> None:
        self.call("GET", "/readyz", token=False)
        status, headers, body = self.call("GET")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], PROMETHEUS_TEXT_CONTENT_TYPE)
        self.assertEqual(headers["content-length"], str(len(body)))
        self.assertLessEqual(len(body), PROMETHEUS_MAX_BODY_BYTES)
        text = body.decode("ascii")
        samples, types, helps = _parse(text)
        self.assertEqual(set(types), helps)
        labels = {name for _, items in samples for name, _ in items}
        self.assertLessEqual(labels, ALLOWED_LABELS)
        self.assertGreaterEqual(
            int(samples[("idkmesh_api_requests_total", (("status_class", "2xx"),))]),
            1,
        )
        self.assertNotIn(TOKEN, text)
        self.assertNotIn("/readyz", text)

    def test_text_accept_and_scraper_accept_are_served_json_only_is_not(self) -> None:
        scraper = (
            "application/openmetrics-text;version=1.0.0;q=0.75,"
            "text/plain;version=0.0.4;q=0.5,*/*;q=0.1"
        )
        self.assertEqual(self.call("GET", headers={"Accept": scraper})[0], 200)
        self.assertEqual(self.call("GET", headers={"Accept": "text/plain"})[0], 200)
        status, _, body = self.call("GET", headers={"Accept": "application/json"})
        self.assertEqual(status, 406)
        self.assertEqual(json.loads(body)["error"]["code"], "not_acceptable")

    def test_head_has_headers_and_no_body(self) -> None:
        status, headers, body = self.call("HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], PROMETHEUS_TEXT_CONTENT_TYPE)
        self.assertEqual(body, b"")

    def test_missing_or_wrong_token_is_the_sibling_403(self) -> None:
        for query in ("", f"?x={SENTINEL}"):
            status, _, body = self.call("GET", PATH + query, token=False)
            self.assertEqual(status, 403)
            self.assertEqual(
                json.loads(body)["error"]["code"], "invalid_session_token"
            )
            self.assertNotIn(SENTINEL.encode(), body)
        sibling = self.call(
            "GET", "/api/v1/metrics", token=False, headers={TOKEN_HEADER: "x" * 32}
        )
        wrong = self.call(
            "GET", token=False, headers={TOKEN_HEADER: "x" * 32}
        )
        self.assertEqual(wrong[0], sibling[0])
        self.assertEqual(wrong[2], sibling[2])

    def test_query_string_is_rejected_after_the_token_gate(self) -> None:
        status, _, body = self.call("GET", PATH + f"?token={SENTINEL}")
        self.assertEqual(status, 400)
        self.assertEqual(
            json.loads(body)["error"]["code"], "unexpected_query_parameters"
        )
        self.assertNotIn(SENTINEL.encode(), body)

    def test_only_get_and_head_are_allowed(self) -> None:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                status, headers, body = self.call(method)
                self.assertEqual(status, 405)
                self.assertEqual(headers["allow"], "GET, HEAD")
                self.assertEqual(
                    json.loads(body)["error"]["code"], "method_not_allowed"
                )

    def test_unsafe_service_label_is_refused_not_emitted(self) -> None:
        unsafe = f'idk"mesh={SENTINEL}'
        with mock.patch("idkmesh.control_tower_ui.SERVICE_NAME", unsafe):
            status, headers, body = self.call("GET")
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body)["error"]["code"], "metrics_unavailable")
        self.assertNotIn(SENTINEL.encode(), body)
        self.assertNotIn("text/plain", headers["content-type"])

    def test_access_log_route_template_is_the_fixed_literal(self) -> None:
        self.assertEqual(_access_log_route(PATH), PATH)
        self.assertEqual(_access_log_route(PATH + "/" + SENTINEL), "<unmatched>")


class PrometheusBytesTests(unittest.TestCase):
    def test_unsafe_service_label_is_rejected(self) -> None:
        for bad in (f'a"b{SENTINEL}', "a b", "a\nb", "x" * 129):
            with self.subTest(bad=bad):
                with self.assertRaises(OtlpMetricsInputError):
                    render_prometheus_bytes(_document(service=bad))

    def test_size_bound_fails_closed_instead_of_truncating(self) -> None:
        document = _document()
        full = render_prometheus_bytes(document)
        self.assertLess(len(full), PROMETHEUS_MAX_BODY_BYTES)
        with self.assertRaises(OtlpMetricsInputError):
            render_prometheus_bytes(document, max_bytes=len(full) - 1)


if __name__ == "__main__":
    unittest.main()
