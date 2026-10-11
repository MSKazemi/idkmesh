#!/usr/bin/env python3
"""Bounded load and soak check for the local Control Tower API (issue #745).

The reliability suites prove individual behaviours (a cap, a drain, a stalled
client). This tool answers the remaining qualification questions with a
measurement: under sustained concurrent traffic, does the service keep
answering correctly, and does it stay the same size?

It starts the real server in-process over a seeded store, then runs two equal
rounds of mixed traffic -- authenticated reads of every route, a share of
hostile requests (bad token, wrong method, unknown route) -- from several
client threads. It records:

* **correctness** -- every response must be one of the expected statuses for
  the request sent; ``503`` with ``Retry-After`` is the service's own load
  shedding and is counted separately, never as success and never as failure;
  any other status, and any transport error, is a failure;
* **body integrity** -- every endpoint whose idle answer is stable (two idle
  requests return the same bytes) must return those same bytes under load, which
  catches corruption and cross-request bleed that a status check cannot;
* **latency** -- p50 / p95 / p99 / max per round (a generous p99 ceiling, since
  wall-clock on a shared runner is noisy; see ``--max-p99-ms``);
* **leaks** -- thread count and open file descriptors after the server has
  drained, against a baseline taken after a warm-up;
* **memory ceiling** -- Python heap growth across the second of two further
  traced rounds (``tracemalloc``), so one-off caches warmed by the first are not
  counted but a per-request leak shows up as growth. These rounds are separate
  from the latency rounds because tracing slows every allocation and would
  distort the percentiles.

Exit codes: 0 every limit held, 1 a limit was exceeded, 2 the run could not
start. ``--json`` prints the full report.

This is a regression tripwire, not a capacity benchmark: the defaults are small
enough to finish in seconds, and the limits are ceilings, not targets.
"""

from __future__ import annotations

import argparse
import http.client
from concurrent.futures import ThreadPoolExecutor
import gc
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import threading
import time
import tracemalloc
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from idkmesh.connector_store import LocalMetadataStore  # noqa: E402
from idkmesh.control_tower_ui import create_server  # noqa: E402
from idkmesh.local_ui_security import TOKEN_HEADER  # noqa: E402
from idkmesh.product_spine import ProductSpineRun  # noqa: E402
from idkmesh.product_spine_run_store import ProductSpineRunStore  # noqa: E402

REPORT_SCHEMA = "idkmesh-api-load-soak/v1"
SEED = 20261011
RUN_COUNT = 12
SOURCE_REVISION = "0123456789abcdef0123456789abcdef01234567"

DEFAULT_REQUESTS = 900
DEFAULT_THREADS = 8
DEFAULT_MAX_P99_MS = 2000.0
DEFAULT_MAX_THREAD_GROWTH = 2
DEFAULT_MAX_FD_GROWTH = 4
DEFAULT_MAX_HEAP_GROWTH_KIB = 4096

# (method, path, token, statuses that are a correct answer)
RUN_ID = "run/soak-1"
GOOD = (200,)
PLAN: tuple[tuple[str, str, bool, tuple[int, ...]], ...] = (
    ("GET", "/api/v1/status", True, GOOD),
    ("GET", "/api/v1/runs", True, GOOD),
    ("GET", f"/api/v1/runs/{RUN_ID}", True, GOOD),
    ("GET", "/api/v1/events", True, GOOD),
    ("GET", "/api/v1/work-units", True, GOOD),
    ("GET", "/api/v1/metrics", True, GOOD),
    ("GET", "/healthz", True, GOOD),
    ("GET", "/api/v1/runs/run/does-not-exist", True, (404,)),
    ("GET", "/api/v1/status", False, (403,)),
    ("DELETE", "/api/v1/runs", True, (405,)),
    ("GET", "/api/v1/not-a-route", True, (404,)),
)


def percentile(sorted_values: Sequence[float], fraction: float) -> float:
    """Nearest-rank percentile of an already sorted sequence (0 for empty)."""
    if not sorted_values:
        return 0.0
    rank = max(1, min(len(sorted_values), round(fraction * len(sorted_values) + 0.4999)))
    return sorted_values[rank - 1]


def open_fd_count() -> int | None:
    """Open file descriptors of this process, or None where /proc is absent."""
    try:
        return len(os.listdir("/proc/self/fd"))
    except OSError:
        return None


def seed_store(path: Path) -> None:
    service = ProductSpineRunStore(LocalMetadataStore(path))
    for index in range(1, RUN_COUNT + 1):
        service.create(
            ProductSpineRun(
                run_id=f"run/soak-{index}",
                request_digest="sha256:" + f"{index:x}" * 64,
                project_id="project.soak",
                work_unit_id=f"work/soak-{index}",
                work_unit_version=1,
                work_unit_digest="sha256:" + "b" * 64,
                source_revision=SOURCE_REVISION,
                authority_mode="agent_candidate",
                routing_policy_version="c1-v0.1",
                state="proposed",
            ),
            idempotency_key=f"soak-{index}",
            created_at="2026-10-11T00:00:00Z",
        )


class _Client:
    def __init__(self, port: int, token: str) -> None:
        self.port = port
        self.token = token

    def call(
        self, method: str, path: str, with_token: bool
    ) -> tuple[int, bool, float, str]:
        """One request; returns (status, retry_after_present, seconds, body_digest)."""
        started = time.perf_counter()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            headers = {TOKEN_HEADER: self.token} if with_token else {}
            conn.request(method, path, headers=headers)
            response = conn.getresponse()
            body = response.read()
            return (
                response.status,
                response.getheader("Retry-After") is not None,
                time.perf_counter() - started,
                hashlib.sha256(body).hexdigest(),
            )
        finally:
            conn.close()


def isolated_baselines(client: _Client) -> dict[tuple[str, str, bool], str]:
    """Body digest of every plan entry whose answer is stable when idle.

    Each entry is requested twice with nothing else running; if the two bodies
    match, the answer is deterministic and any different body seen under load
    is corruption or drift, not a timestamp. Entries that legitimately vary
    (uptime, counters, request ids) are left out rather than special-cased.
    """
    stable: dict[tuple[str, str, bool], str] = {}
    for method, path, with_token, _expected in PLAN:
        first = client.call(method, path, with_token)
        second = client.call(method, path, with_token)
        if first[3] == second[3]:
            stable[(method, path, with_token)] = first[3]
    return stable


def run_round(
    client: _Client,
    requests: int,
    threads: int,
    seed: int,
    baselines: dict[tuple[str, str, bool], str] | None = None,
) -> dict[str, Any]:
    rng = random.Random(seed)
    jobs = [PLAN[rng.randrange(len(PLAN))] for _ in range(requests)]
    latencies: list[float] = []
    shed = 0
    failures: list[str] = []
    lock = threading.Lock()

    def work(job: tuple[str, str, bool, tuple[int, ...]]) -> None:
        nonlocal shed
        method, path, with_token, expected = job
        try:
            status, retry_after, seconds, digest = client.call(method, path, with_token)
        except OSError as exc:
            with lock:
                failures.append(f"{method} {path}: transport error {exc!r}")
            return
        with lock:
            latencies.append(seconds)
            if status == 503 and retry_after:
                shed += 1
            elif status not in expected:
                failures.append(f"{method} {path}: got {status}, expected {expected}")
            elif baselines is not None and baselines.get((method, path, with_token), digest) != digest:
                failures.append(f"{method} {path}: body differs from its idle baseline")

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=threads) as pool:
        list(pool.map(work, jobs))
    elapsed = time.perf_counter() - started
    ordered = sorted(latencies)
    return {
        "requests": requests,
        "answered": len(latencies),
        "shed_503": shed,
        "failures": len(failures),
        "failure_samples": failures[:5],
        "elapsed_s": round(elapsed, 3),
        "p50_ms": round(percentile(ordered, 0.50) * 1000, 2),
        "p95_ms": round(percentile(ordered, 0.95) * 1000, 2),
        "p99_ms": round(percentile(ordered, 0.99) * 1000, 2),
        "max_ms": round((ordered[-1] if ordered else 0.0) * 1000, 2),
    }


def evaluate(report: dict[str, Any], limits: dict[str, float]) -> list[str]:
    """Names of the limits the report violates (empty means all held)."""
    problems: list[str] = []
    for index, round_ in enumerate(report["rounds"], start=1):
        if round_["failures"]:
            problems.append(f"round {index}: {round_['failures']} incorrect response(s)")
        if round_["answered"] + 0 == 0:
            problems.append(f"round {index}: no request was answered")
        if round_["p99_ms"] > limits["max_p99_ms"]:
            problems.append(
                f"round {index}: p99 {round_['p99_ms']} ms exceeds {limits['max_p99_ms']} ms"
            )
    after = report["after_drain"]
    if after["thread_growth"] > limits["max_thread_growth"]:
        problems.append(f"thread growth {after['thread_growth']} after drain")
    if after["fd_growth"] is not None and after["fd_growth"] > limits["max_fd_growth"]:
        problems.append(f"file-descriptor growth {after['fd_growth']} after drain")
    if report["heap"]["round_two_growth_kib"] > limits["max_heap_growth_kib"]:
        problems.append(
            f"heap grew {report['heap']['round_two_growth_kib']} KiB over the traced round"
        )
    if not after["drained"]:
        problems.append("the server did not drain")
    return problems


def soak(
    requests: int = DEFAULT_REQUESTS,
    threads: int = DEFAULT_THREADS,
    limits: dict[str, float] | None = None,
    *,
    warmup: int | None = None,
    heap_requests: int | None = None,
) -> dict[str, Any]:
    """Run both phases. ``warmup`` and ``heap_requests`` default to fractions of
    ``requests``; the unit tests shrink them to keep their CPU cost small."""
    limits = limits or {
        "max_p99_ms": DEFAULT_MAX_P99_MS,
        "max_thread_growth": DEFAULT_MAX_THREAD_GROWTH,
        "max_fd_growth": DEFAULT_MAX_FD_GROWTH,
        "max_heap_growth_kib": DEFAULT_MAX_HEAP_GROWTH_KIB,
    }
    with tempfile.TemporaryDirectory(prefix="idkmesh-soak-") as tmp:
        store_path = Path(tmp) / "soak.sqlite"
        seed_store(store_path)
        server = create_server(port=0, product_spine_store_path=str(store_path))
        serve = threading.Thread(target=server.serve_forever, daemon=True)
        serve.start()
        client = _Client(server.server_port, server.ui_token)
        try:
            run_round(
                client,
                max(50, requests // 10) if warmup is None else warmup,
                threads,
                SEED - 1,
            )
            baselines = isolated_baselines(client)
            gc.collect()
            threads_before = threading.active_count()
            fds_before = open_fd_count()

            # Latency and correctness are measured untraced: tracemalloc slows
            # every allocation and would distort the percentiles.
            first = run_round(client, requests, threads, SEED, baselines)
            second = run_round(client, requests, threads, SEED + 1, baselines)

            # The memory ceiling gets its own traced pair of rounds. Round one
            # warms any lazily built state; growth is read across round two.
            if heap_requests is None:
                heap_requests = max(100, requests // 3)
            tracemalloc.start()
            run_round(client, heap_requests, threads, SEED + 2)
            gc.collect()
            heap_one = tracemalloc.get_traced_memory()[0]
            run_round(client, heap_requests, threads, SEED + 3)
            gc.collect()
            heap_two = tracemalloc.get_traced_memory()[0]
            tracemalloc.stop()
        finally:
            drained = server.drain(timeout=10.0)
            server.shutdown()
            server.server_close()
            serve.join(timeout=5)
        time.sleep(0.2)  # let per-request daemon threads exit
        gc.collect()
        threads_after = threading.active_count()
        fds_after = open_fd_count()

    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "seed": SEED,
        "threads": threads,
        "limits": limits,
        "deterministic_endpoints_compared": len(baselines),
        "rounds": [first, second],
        "heap": {
            "requests_per_round": heap_requests,
            "after_round_one_kib": round(heap_one / 1024, 1),
            "after_round_two_kib": round(heap_two / 1024, 1),
            "round_two_growth_kib": round((heap_two - heap_one) / 1024, 1),
        },
        "after_drain": {
            "drained": drained,
            "thread_growth": threads_after - threads_before,
            "fd_growth": None if fds_before is None or fds_after is None
            else fds_after - fds_before,
        },
    }
    report["problems"] = evaluate(report, limits)
    report["verdict"] = "pass" if not report["problems"] else "fail"
    return report


def render(report: dict[str, Any]) -> str:
    lines = [f"API load/soak: {report['verdict'].upper()}"]
    for index, round_ in enumerate(report["rounds"], start=1):
        lines.append(
            f"  round {index}: {round_['requests']} requests in {round_['elapsed_s']}s, "
            f"{round_['failures']} incorrect, {round_['shed_503']} shed, "
            f"p50 {round_['p50_ms']} / p95 {round_['p95_ms']} / p99 {round_['p99_ms']} ms"
        )
    heap = report["heap"]
    after = report["after_drain"]
    lines.append(
        f"  heap: +{heap['round_two_growth_kib']} KiB over {heap['requests_per_round']} traced requests; after drain: "
        f"threads {after['thread_growth']:+d}, fds {after['fd_growth']}"
    )
    lines.append(
        f"  bodies compared against idle baseline: {report['deterministic_endpoints_compared']} endpoints"
    )
    lines.extend(f"  PROBLEM: {problem}" for problem in report["problems"])
    for round_ in report["rounds"]:
        lines.extend(f"  sample: {sample}" for sample in round_["failure_samples"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--requests", type=int, default=DEFAULT_REQUESTS,
                        help="requests per round (two rounds run)")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS)
    parser.add_argument("--max-p99-ms", type=float, default=DEFAULT_MAX_P99_MS)
    parser.add_argument("--max-thread-growth", type=int, default=DEFAULT_MAX_THREAD_GROWTH)
    parser.add_argument("--max-fd-growth", type=int, default=DEFAULT_MAX_FD_GROWTH)
    parser.add_argument("--max-heap-growth-kib", type=float,
                        default=DEFAULT_MAX_HEAP_GROWTH_KIB)
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    args = parser.parse_args(argv)
    if args.requests < 1 or args.threads < 1:
        print("error: --requests and --threads must be positive", file=sys.stderr)
        return 2
    try:
        report = soak(
            args.requests,
            args.threads,
            {
                "max_p99_ms": args.max_p99_ms,
                "max_thread_growth": args.max_thread_growth,
                "max_fd_growth": args.max_fd_growth,
                "max_heap_growth_kib": args.max_heap_growth_kib,
            },
        )
    except OSError as exc:
        print(f"error: could not run the soak: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render(report))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
