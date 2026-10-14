"""Opt-in retry, lazy pagination and credential hygiene of the Python client (#746).

Class-based on purpose: ``tests/test_documented_test_counts.py`` counts
module-level ``test_*`` functions and this file must not shift them.
Standard library only (plus the repository package), because CI installs
nothing else.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import tempfile
import threading
import unittest
from unittest import mock

from idkmesh.api_client import (
    MAX_RETRY_ATTEMPTS,
    MAX_RETRY_DELAY_SECONDS,
    ApiResponseError,
    ApiResult,
    ClientConfigurationError,
    ControlTowerClient,
    IntegrityError,
    ListPage,
    ProtocolError,
    ResponseMetadata,
    RetryPolicy,
    TransportError,
)
from idkmesh.connector_store import LocalMetadataStore
from idkmesh.control_tower_ui import TOKEN_ENV, create_server
from idkmesh.product_spine import ProductSpineRun
from idkmesh.product_spine_run_store import ProductSpineRunStore
from idkmesh.work_unit_binding import canonical_digest

TOKEN = "r" * 32
SHA = "0123456789abcdef0123456789abcdef01234567"
PATCH_TARGET = "idkmesh.api_client.http.client.HTTPConnection"


class _Response:
    def __init__(
        self,
        payload: dict,
        *,
        status: int = 200,
        digest: str | None = None,
        retry_after: str | None = None,
    ) -> None:
        self.status = status
        self._raw = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self._headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-Request-ID": "req_retry",
            "X-IDKMesh-Content-Digest": (
                canonical_digest(payload) if digest is None else digest
            ),
        }
        if retry_after is not None:
            self._headers["Retry-After"] = retry_after

    def read(self):
        return self._raw

    def getheader(self, name):
        return self._headers.get(name)


class _Script:
    """Hands out one scripted outcome per HTTPConnection, in order."""

    def __init__(self, *outcomes) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[tuple[str, str]] = []

    def __call__(self, *args, **kwargs):
        outcome = self.outcomes.pop(0)
        script = self

        class _Conn:
            def request(self, method, path, body=None, headers=None):
                script.requests.append((method, path))
                if isinstance(outcome, BaseException):
                    raise outcome

            def getresponse(self):
                return outcome

            def close(self):
                pass

        return _Conn()


STATUS_OK = {"kind": "idkmesh-control-tower-status", "ok": True}


def _error(code: str, status: int, *, retryable: bool, retry_after=None):
    payload = {
        "api_version": "v1",
        "schema_version": "0.1",
        "kind": "idkmesh-api-error",
        "ok": False,
        "error": {"code": code, "message": "m", "retryable": retryable},
    }
    return _Response(payload, status=status, retry_after=retry_after)


class RetryPolicyValidationTests(unittest.TestCase):
    def test_accepts_documented_bounds(self):
        policy = RetryPolicy(max_attempts=MAX_RETRY_ATTEMPTS)
        self.assertEqual(policy.delay_before_retry(1), 0.25)
        self.assertEqual(policy.delay_before_retry(2), 0.5)
        self.assertEqual(policy.delay_before_retry(10), 5.0)  # capped

    def test_rejects_unbounded_or_malformed_policies(self):
        bad = [
            {"max_attempts": 1},
            {"max_attempts": 0},
            {"max_attempts": MAX_RETRY_ATTEMPTS + 1},
            {"max_attempts": True},
            {"max_attempts": 2.0},
            {"max_attempts": 3, "base_delay": 0},
            {"max_attempts": 3, "base_delay": -1.0},
            {"max_attempts": 3, "base_delay": float("nan")},
            {"max_attempts": 3, "max_delay": float("inf")},
            {"max_attempts": 3, "max_delay": MAX_RETRY_DELAY_SECONDS + 1},
            {"max_attempts": 3, "base_delay": 2.0, "max_delay": 1.0},
        ]
        for kwargs in bad:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ClientConfigurationError):
                    RetryPolicy(**kwargs)

    def test_server_retry_after_beyond_ceiling_is_not_waited_out(self):
        policy = RetryPolicy(max_attempts=3, max_delay=5.0)
        self.assertIsNone(policy.delay_before_retry(1, 6))
        self.assertEqual(policy.delay_before_retry(1, 3), 3.0)
        self.assertEqual(policy.delay_before_retry(3, 1), 1.0)

    def test_client_rejects_wrong_retry_or_sleep_types(self):
        with self.assertRaises(ClientConfigurationError):
            ControlTowerClient(
                "http://127.0.0.1:1", TOKEN, timeout=1.0, retry=3  # type: ignore[arg-type]
            )
        with self.assertRaises(ClientConfigurationError):
            ControlTowerClient(
                "http://127.0.0.1:1", TOKEN, timeout=1.0, sleep="x"  # type: ignore[arg-type]
            )


class RetryBehaviourTests(unittest.TestCase):
    def make(self, *, attempts: int = 3, **policy):
        self.sleeps: list[float] = []
        return ControlTowerClient(
            "http://127.0.0.1:8770",
            TOKEN,
            timeout=1.0,
            retry=RetryPolicy(max_attempts=attempts, **policy),
            sleep=self.sleeps.append,
        )

    def run_status(self, client, *outcomes):
        script = _Script(*outcomes)
        with mock.patch(PATCH_TARGET, side_effect=script):
            try:
                return script, client.status(), None
            except Exception as exc:  # noqa: BLE001 - the test inspects it
                return script, None, exc

    def test_retryable_capacity_error_is_retried_then_succeeds(self):
        script, result, error = self.run_status(
            self.make(),
            _error("overloaded", 503, retryable=True),
            _Response(STATUS_OK),
        )
        self.assertIsNone(error)
        self.assertEqual(len(script.requests), 2)
        self.assertEqual(self.sleeps, [0.25])
        self.assertEqual(result.metadata.attempts, 2)
        self.assertEqual(result.request_id, "req_retry")

    def test_backoff_is_deterministic_exponential_and_capped(self):
        script, result, error = self.run_status(
            self.make(attempts=5, max_delay=0.75),
            _error("overloaded", 503, retryable=True),
            _error("overloaded", 503, retryable=True),
            _error("overloaded", 503, retryable=True),
            _error("overloaded", 503, retryable=True),
            _Response(STATUS_OK),
        )
        self.assertIsNone(error)
        self.assertEqual(self.sleeps, [0.25, 0.5, 0.75, 0.75])
        self.assertEqual(result.metadata.attempts, 5)

    def test_exhaustion_raises_last_error_with_attempt_count(self):
        script, result, error = self.run_status(
            self.make(attempts=3),
            _error("overloaded", 503, retryable=True),
            _error("overloaded", 503, retryable=True),
            _error("shutting_down", 503, retryable=True),
        )
        self.assertIsInstance(error, ApiResponseError)
        self.assertEqual(error.code, "shutting_down")
        self.assertEqual(error.attempts, 3)
        self.assertEqual(len(script.requests), 3)
        self.assertEqual(len(self.sleeps), 2)

    def test_retry_after_lengthens_the_wait_within_the_ceiling(self):
        script, result, error = self.run_status(
            self.make(),
            _error("overloaded", 503, retryable=True, retry_after="2"),
            _Response(STATUS_OK),
        )
        self.assertIsNone(error)
        self.assertEqual(self.sleeps, [2.0])

    def test_retry_after_beyond_ceiling_surfaces_the_error_without_sleeping(self):
        script, result, error = self.run_status(
            self.make(max_delay=5.0),
            _error("overloaded", 503, retryable=True, retry_after="120"),
        )
        self.assertIsInstance(error, ApiResponseError)
        self.assertEqual(error.retry_after_seconds, 120)
        self.assertEqual(error.attempts, 1)
        self.assertEqual(self.sleeps, [])
        self.assertEqual(len(script.requests), 1)

    def test_malformed_retry_after_is_ignored_not_trusted(self):
        for value in ("-1", "abc", "1e3", "", "9999999", " 5", "5 "):
            with self.subTest(value=value):
                script, result, error = self.run_status(
                    self.make(),
                    _error("overloaded", 503, retryable=True, retry_after=value),
                    _Response(STATUS_OK),
                )
                self.assertIsNone(error)
                self.assertEqual(self.sleeps, [0.25])

    def test_transport_failure_is_retried(self):
        script, result, error = self.run_status(
            self.make(),
            ConnectionResetError("reset"),
            _Response(STATUS_OK),
        )
        self.assertIsNone(error)
        self.assertEqual(result.metadata.attempts, 2)

    def test_persistent_transport_failure_raises_transport_error(self):
        script, result, error = self.run_status(
            self.make(attempts=2),
            ConnectionRefusedError("a"),
            ConnectionRefusedError("b"),
        )
        self.assertIsInstance(error, TransportError)
        self.assertEqual(error.attempts, 2)

    def test_non_retryable_failures_are_never_retried(self):
        cases = {
            "non-retryable api error": _error("run_not_found", 404, retryable=False),
            "retryable flag on a 500": _error("store_error", 500, retryable=True),
            "bad digest": _Response(STATUS_OK, digest="sha256:" + "0" * 64),
            "wrong kind": _Response({"kind": "something-else"}),
        }
        expected = {
            "non-retryable api error": ApiResponseError,
            "retryable flag on a 500": ApiResponseError,
            "bad digest": IntegrityError,
            "wrong kind": ProtocolError,
        }
        for name, response in cases.items():
            with self.subTest(name=name):
                script, result, error = self.run_status(self.make(), response)
                self.assertIsInstance(error, expected[name])
                self.assertEqual(len(script.requests), 1)
                self.assertEqual(self.sleeps, [])
                self.assertEqual(error.attempts, 1)

    def test_default_client_never_retries_and_reports_one_attempt(self):
        client = ControlTowerClient("http://127.0.0.1:8770", TOKEN, timeout=1.0)
        script, result, error = self.run_status(
            client, _error("overloaded", 503, retryable=True)
        )
        self.assertIsInstance(error, ApiResponseError)
        self.assertEqual(len(script.requests), 1)
        self.assertEqual(error.attempts, 1)

    def test_non_get_and_payload_requests_are_never_retried(self):
        client = self.make()
        script = _Script(ConnectionResetError("x"), _Response(STATUS_OK))
        with mock.patch(PATCH_TARGET, side_effect=script):
            with self.assertRaises(TransportError):
                client._request("POST", "/api/v1/anything", payload={"a": 1})
        self.assertEqual(len(script.requests), 1)
        script = _Script(ConnectionResetError("x"), _Response(STATUS_OK))
        with mock.patch(PATCH_TARGET, side_effect=script):
            with self.assertRaises(TransportError):
                client._request("GET", "/api/v1/status", payload={"a": 1})
        self.assertEqual(len(script.requests), 1)

    def test_event_stream_open_is_never_retried(self):
        client = self.make()
        script = _Script(ConnectionResetError("x"), ConnectionResetError("y"))
        with mock.patch(PATCH_TARGET, side_effect=script):
            with self.assertRaises(TransportError):
                client.stream_events(idle_timeout=1.0)
        self.assertEqual(len(script.requests), 1)
        self.assertEqual(self.sleeps, [])


class CredentialHygieneTests(unittest.TestCase):
    def test_repr_and_str_never_contain_the_token(self):
        token = "SecretTokenValue" + "0" * 20
        client = ControlTowerClient(
            "http://127.0.0.1:8770", token, timeout=1.0
        )
        for text in (repr(client), str(client), f"{client!r}", f"{client}"):
            self.assertNotIn(token, text)
            self.assertNotIn("SecretToken", text)

    def test_transport_error_message_does_not_leak_the_token(self):
        token = "LeakCheckToken" + "1" * 20
        client = ControlTowerClient("http://127.0.0.1:8770", token, timeout=1.0)
        script = _Script(OSError("boom"))
        with mock.patch(PATCH_TARGET, side_effect=script):
            with self.assertRaises(TransportError) as caught:
                client.status()
        self.assertNotIn(token, str(caught.exception))
        self.assertNotIn(token, repr(caught.exception))

    def test_invalid_token_error_does_not_echo_the_token(self):
        bad = "bad token with spaces " + "z" * 20
        with self.assertRaises(ClientConfigurationError) as caught:
            ControlTowerClient("http://127.0.0.1:8770", bad, timeout=1.0)
        self.assertNotIn("bad token", str(caught.exception))


class _Recorder(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server naming
        self.server.hits.append(self.path)  # type: ignore[attr-defined]
        location = self.server.location  # type: ignore[attr-defined]
        if location is None:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"target")
        else:
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()

    def log_message(self, *args):  # noqa: D401 - silence
        return


class RedirectTests(unittest.TestCase):
    def serve(self, location):
        server = HTTPServer(("127.0.0.1", 0), _Recorder)
        server.hits = []  # type: ignore[attr-defined]
        server.location = location  # type: ignore[attr-defined]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(cleanup)
        return server

    def test_redirect_to_another_host_is_not_followed_and_no_token_is_sent_there(self):
        target = self.serve(None)
        redirector = self.serve(f"http://127.0.0.1:{target.server_port}/steal")
        client = ControlTowerClient(
            f"http://127.0.0.1:{redirector.server_port}",
            TOKEN,
            timeout=2.0,
            retry=RetryPolicy(max_attempts=3),
            sleep=lambda _s: None,
        )
        with self.assertRaises(ProtocolError):
            client.status()
        self.assertEqual(redirector.hits, ["/api/v1/status"])
        self.assertEqual(target.hits, [])


def _run(run_id: str) -> ProductSpineRun:
    return ProductSpineRun(
        run_id=run_id,
        request_digest="sha256:" + "a" * 64,
        project_id="project.retry",
        work_unit_id=f"work/{run_id.rsplit('/', 1)[-1]}",
        work_unit_version=1,
        work_unit_digest="sha256:" + "b" * 64,
        source_revision=SHA,
        authority_mode="agent_candidate",
        routing_policy_version="retry-test-v1",
        state="proposed",
    )


class LazyPaginationTests(unittest.TestCase):
    def live_client(self, count: int) -> ControlTowerClient:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = f"{directory.name}/store.sqlite3"
        store = ProductSpineRunStore(LocalMetadataStore(path))
        for index in range(count):
            store.create(
                _run(f"run/pages-{index}"),
                idempotency_key=f"page-{index}",
                created_at=f"2026-10-08T00:0{index}:00Z",
            )
        with mock.patch.dict("os.environ", {TOKEN_ENV: TOKEN}):
            server = create_server(port=0, product_spine_store_path=path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(cleanup)
        return ControlTowerClient(
            f"http://127.0.0.1:{server.server_port}", TOKEN, timeout=2.0
        )

    def test_iter_runs_is_lazy_one_read_per_page_and_complete(self):
        client = self.live_client(3)
        calls = []
        original = client.list_runs

        def counting(**kwargs):
            calls.append(kwargs.get("cursor"))
            return original(**kwargs)

        client.list_runs = counting  # type: ignore[method-assign]
        iterator = client.iter_runs(max_pages=5, limit=1)
        self.assertEqual(calls, [])  # nothing is fetched until iterated
        first = next(iterator)
        self.assertEqual(len(calls), 1)
        rest = list(iterator)
        items = [first, *rest]
        self.assertEqual(len(items), 3)
        self.assertEqual(len({item["run_id"] for item in items}), 3)
        self.assertEqual(len(calls), 3)

    def test_iter_run_pages_keeps_earlier_pages_when_budget_is_too_small(self):
        client = self.live_client(3)
        seen = []
        with self.assertRaises(ProtocolError):
            for page in client.iter_run_pages(max_pages=2, limit=1):
                seen.append(page)
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(isinstance(p.value, ListPage) for p in seen))

    def test_repeated_cursor_is_refused(self):
        client = self.live_client(0)
        page = ApiResult(
            value=ListPage(items=({"run_id": "r"},), next_cursor="same", limit=1),
            metadata=ResponseMetadata(
                status_code=200, request_id="req", content_digest="sha256:" + "0" * 64
            ),
        )
        client.list_runs = lambda **_k: page  # type: ignore[method-assign]
        collected = []
        with self.assertRaises(ProtocolError):
            for item in client.iter_runs(max_pages=10, limit=1):
                collected.append(item)
        self.assertEqual(len(collected), 2)  # first page, then the replay is refused

    def test_budget_is_validated_before_any_io(self):
        client = ControlTowerClient("http://127.0.0.1:1", TOKEN, timeout=1.0)
        for bad in (0, 101, True, 2.0, "3"):
            with self.subTest(max_pages=bad):
                with self.assertRaises(ClientConfigurationError):
                    next(client.iter_run_pages(max_pages=bad))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
