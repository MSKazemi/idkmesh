"""Load, soak, and memory-ceiling qualification for the Control Tower API.

(issue #745, Reliability slice: load test, soak test, memory ceiling.)

The traceability matrix (`docs/planning/API_V1_REQUIREMENTS_TRACEABILITY_MATRIX_2026-09-23.md`)
expects load/soak/memory evidence as a release artifact rather than manual
confidence. This module is that artifact: it runs against the real loopback
server and is marked ``slow``, so the cheap testkit tiers skip it and the
nightly tier (`scripts/testkit.py`, ``-m "sim or slow"``) runs it
reproducibly.

Scope decision (recorded, not an oversight): the harness runs a store-less
server. The qualification target is the HTTP surface -- admission, envelope
generation, parsing, and capacity accounting. Store-backed reads are cheaper
per request and are covered functionally by the run-read/events suites; a
future store-backed soak can extend ``_MIX`` without changing the contracts
below.

Contracts asserted here:

- **Load** (``LoadTests``): N requests at K-way concurrency against a mixed
  endpoint set all return exactly the status each shape returns in isolation
  (no nondeterministic 503s or corruption under concurrency), every response
  is a well-formed envelope, and all admission capacity is released
  afterwards (``in_flight == 0``). The wall-clock bound is a hang canary,
  deliberately far above any plausible CI machine, not a latency target.
- **Soak** (``SoakTests``): many mixed cycles -- including adversarial
  probes (unauthenticated, wrong method, malformed body) with their absolute
  contracts -- accumulate zero failures and zero capacity leaks.
- **Memory ceiling** (``MemoryCeilingTests``): a bounded tracemalloc peak
  over a larger run that includes big bodies. The ceiling is set to catch
  per-request retention (which grows linearly with request count), not to
  pin allocator details.

Class-based and ``pytestmark``-marked only: the documented module-level test
counts in ``tests/test_documented_test_counts.py`` must not drift.
"""

from __future__ import annotations

import concurrent.futures
import http.client
import importlib.util
import json
import threading
import time
import tracemalloc
import unittest

from idkmesh.control_tower_ui import SAMPLE_REPORT, create_server
from idkmesh.local_ui_security import TOKEN_HEADER

# The marker is a tier hint for pytest, never a precondition for the
# assertions (same guard as tests/test_benchmark_publication.py): narrow
# workflow jobs run this module through `python -m unittest` on a bare
# interpreter where importing pytest would break collection.
if importlib.util.find_spec("pytest") is not None:
    import pytest

    pytestmark = pytest.mark.slow
else:  # pragma: no cover - bare-interpreter CI jobs take this path
    pytestmark = ()

# ---------------------------------------------------------------- budgets --
LOAD_REQUESTS = 240
LOAD_CONCURRENCY = 8
LOAD_WALL_SECONDS = 90.0  # hang canary only; typical wall is a few seconds

SOAK_CYCLES = 40

MEM_REQUESTS = 300
MEM_BIG_BODY_BYTES = 100_000
MEM_CEILING_BYTES = 8 * 1024 * 1024
# Ceiling reasoning: tracemalloc measures Python-heap growth only. The run
# allocates and frees ~MEM_REQUESTS envelopes plus several big parse
# attempts; a steady-state server stays far below this. Per-request
# retention would exceed it within the run (e.g. retaining one 100 KB body
# per request already exceeds it threefold), so the ceiling is a leak
# canary, not a tuning target.

_INVALID_TOKEN = "not-the-session-token-000000000000000"


def _start_server():
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_server(server, thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def _request(
    server,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    token: bool = True,
) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection(
        "127.0.0.1", server.server_port, timeout=10
    )
    headers: dict[str, str] = {}
    if token:
        headers[TOKEN_HEADER] = server.ui_token
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        headers["Content-Length"] = str(len(body))
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


# The mixed traffic pattern. Each shape's expected status is *recorded* from
# an isolated probe at setUp (the server is deterministic), then every
# response under load must match it exactly. Shapes with absolute contracts
# (auth, methods) assert those directly elsewhere in the suite.
_MIX: tuple[tuple[str, str, bytes | None], ...] = (
    ("GET", "/api/v1/status", None),
    ("GET", "/api/v1/openapi.json", None),
    ("GET", "/api/v1/metrics", None),
    ("GET", "/api/v1/runs", None),
    ("GET", "/api/v1/connections", None),
    ("GET", "/api/v1/work-units", None),
    ("GET", "/api/v1/events", None),
    ("GET", "/api/v1/runs/no-such-run", None),
    ("GET", "/api/v1/no-such-endpoint", None),
    ("POST", "/api/v1/run-evidence/inspect", SAMPLE_REPORT.encode("utf-8")),
    ("POST", "/api/v1/run-evidence/inspect", b"{not valid json"),
    ("POST", "/api/v1/run-evidence/inspect", b'"' + b"x" * 10_000 + b'"'),
)


# Shapes whose 200 body is live state rather than a fixed document: metrics
# embeds in-flight gauges, so byte-exact reproduction is not a contract there.
# Status equality remains required for every shape.
_DYNAMIC_BODY_SHAPES = {("GET", "/api/v1/metrics", None)}


class _ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server, cls.thread = _start_server()
        # Record each shape's isolated behavior once; load must reproduce it.
        cls.expected = {
            (method, path, body): _request(cls.server, method, path, body=body)
            for method, path, body in _MIX
        }

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server, cls.thread)

    def assert_capacity_released(self) -> None:
        # A client can observe the complete response before the server
        # thread finishes its release, so zero is polled to a short
        # deadline: the contract is "capacity is released promptly". A true
        # leak (a slot that is never released) still fails the poll.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if (
                self.server.limiter.in_flight == 0
                and self.server.sse_limiter.in_flight == 0
            ):
                return
            time.sleep(0.01)
        self.assertEqual(self.server.limiter.in_flight, 0)
        self.assertEqual(self.server.sse_limiter.in_flight, 0)

    def run_mix(
        self, count: int, workers: int
    ) -> list[tuple[int, int, bytes]]:
        """Run ``count`` mixed requests; return (shape_index, status, body).

        Completion order is nondeterministic under concurrency, so the
        shape index travels with each result instead of being re-derived.
        """
        shapes = list(_MIX)
        results: list[tuple[int, int, bytes]] = []
        errors: list[str] = []

        def one(index: int) -> tuple[int, int, bytes]:
            shape_index = index % len(shapes)
            method, path, body = shapes[shape_index]
            status, payload = _request(self.server, method, path, body=body)
            return shape_index, status, payload

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=workers
        ) as pool:
            futures = [pool.submit(one, i) for i in range(count)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:  # noqa: BLE001 - recorded, then fails
                    errors.append(repr(exc))

        self.assertEqual(errors, [], f"transport errors under load: {errors}")
        self.assertEqual(len(results), count)
        return results

    def assert_matches_isolation(
        self, results: list[tuple[int, int, bytes]]
    ) -> None:
        shapes = list(_MIX)
        for shape_index, status, body in results:
            method, path, body_sent = shapes[shape_index]
            expected_status, expected_body = self.expected[
                (method, path, body_sent)
            ]
            self.assertEqual(
                status,
                expected_status,
                f"{method} {path} drifted under load",
            )
            if (method, path, body_sent) not in _DYNAMIC_BODY_SHAPES:
                self.assertEqual(
                    body,
                    expected_body,
                    f"{method} {path} body drifted under load",
                )


class LoadTests(_ServerCase):
    def test_mixed_load_reproduces_isolated_behavior_exactly(self) -> None:
        started = time.monotonic()
        results = self.run_mix(LOAD_REQUESTS, LOAD_CONCURRENCY)
        elapsed = time.monotonic() - started
        self.assertLess(
            elapsed,
            LOAD_WALL_SECONDS,
            f"load of {LOAD_REQUESTS} requests took {elapsed:.1f}s",
        )
        self.assert_matches_isolation(results)
        self.assert_capacity_released()

    def test_every_response_parses_and_errors_are_envelopes(self) -> None:
        results = self.run_mix(len(_MIX) * 4, LOAD_CONCURRENCY)
        for _shape_index, status, body in results:
            with self.subTest(status=status):
                document = json.loads(body.decode("utf-8"))
                self.assertIsInstance(document, dict)
                if status >= 400:
                    # Every client error is the documented JSON envelope.
                    self.assertIsInstance(document["error"]["code"], str)
                    self.assertEqual(document["api_version"], "v1")


class SoakTests(_ServerCase):
    def test_soak_cycles_accumulate_no_failures_or_leaks(self) -> None:
        adversarial = (
            # Absolute contracts (see the security matrix): auth first,
            # closed method set.
            ("GET", "/api/v1/status", None, False, 403),
            ("PUT", "/api/v1/status", None, True, 405),
            ("POST", "/api/v1/runs", b"{}", True, 405),
            ("DELETE", "/api/v1/metrics", None, True, 405),
        )
        started = time.monotonic()
        for cycle in range(SOAK_CYCLES):
            results = self.run_mix(len(_MIX), workers=4)
            self.assert_matches_isolation(results)
            for method, path, body, token, want in adversarial:
                status, _ = _request(
                    self.server, method, path, body=body, token=token
                )
                self.assertEqual(
                    status,
                    want,
                    f"cycle {cycle}: {method} {path} contract drifted",
                )
            # Steady state means released capacity at every cycle boundary.
            self.assert_capacity_released()
        elapsed = time.monotonic() - started
        print(
            f"[soak] {SOAK_CYCLES} cycles x {len(_MIX)} mixed + "
            f"{len(adversarial)} adversarial in {elapsed:.1f}s"
        )


class MemoryCeilingTests(_ServerCase):
    def test_peak_python_heap_growth_stays_under_the_ceiling(self) -> None:
        # Warm up so one-time imports and caches are outside the window.
        self.run_mix(len(_MIX) * 2, workers=4)

        tracemalloc.start()
        try:
            results = self.run_mix(MEM_REQUESTS, workers=4)
            for _ in range(10):
                _request(
                    self.server,
                    "POST",
                    "/api/v1/run-evidence/inspect",
                    body=b"x" * MEM_BIG_BODY_BYTES,
                )
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assert_matches_isolation(results)
        self.assert_capacity_released()
        print(f"[memory] peak python-heap growth: {peak / 1024:.0f} KiB")
        self.assertLessEqual(
            peak,
            MEM_CEILING_BYTES,
            f"peak python-heap growth {peak / 1024:.0f} KiB exceeds the "
            f"{MEM_CEILING_BYTES / 1024:.0f} KiB ceiling; retention likely",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
