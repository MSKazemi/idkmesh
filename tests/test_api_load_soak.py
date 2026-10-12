"""Tests for tools/api_load_soak.py (issue #745).

One small real run proves the tool measures what it claims against the live
server; the rest drive ``evaluate`` with fabricated reports so every limit is
shown to trip, without spending more server time.

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import copy
import unittest
from unittest import mock

import pytest
from tools import api_load_soak as soak

LIMITS = {
    "max_p99_ms": 2000.0,
    "max_thread_growth": 2,
    "max_fd_growth": 4,
    "max_heap_growth_kib": 4096,
}


def _healthy_report():
    round_ = {
        "requests": 100, "answered": 100, "shed_503": 0, "failures": 0,
        "failure_samples": [], "elapsed_s": 1.0, "p50_ms": 5.0, "p95_ms": 9.0,
        "p99_ms": 12.0, "max_ms": 20.0,
    }
    return {
        "rounds": [dict(round_), dict(round_)],
        "heap": {"requests_per_round": 100, "round_two_growth_kib": 10.0},
        "after_drain": {"drained": True, "thread_growth": 0, "fd_growth": 0},
    }


class PercentileTests(unittest.TestCase):
    def test_nearest_rank(self):
        values = [float(n) for n in range(1, 101)]
        self.assertEqual(soak.percentile(values, 0.50), 50.0)
        self.assertEqual(soak.percentile(values, 0.99), 99.0)
        self.assertEqual(soak.percentile(values, 1.0), 100.0)
        self.assertEqual(soak.percentile([], 0.99), 0.0)
        self.assertEqual(soak.percentile([7.0], 0.99), 7.0)


class EvaluateTests(unittest.TestCase):
    def test_a_healthy_report_has_no_problems(self):
        self.assertEqual(soak.evaluate(_healthy_report(), LIMITS), [])

    def test_each_limit_trips_independently(self):
        cases = {
            "incorrect": lambda r: r["rounds"][0].update(failures=3),
            "silence": lambda r: r["rounds"][1].update(answered=0),
            "p99": lambda r: r["rounds"][1].update(p99_ms=5000.0),
            "threads": lambda r: r["after_drain"].update(thread_growth=50),
            "fds": lambda r: r["after_drain"].update(fd_growth=50),
            "heap": lambda r: r["heap"].update(round_two_growth_kib=99999.0),
            "drain": lambda r: r["after_drain"].update(drained=False),
        }
        for name, mutate in cases.items():
            with self.subTest(limit=name):
                report = copy.deepcopy(_healthy_report())
                mutate(report)
                self.assertTrue(soak.evaluate(report, LIMITS), name)

    def test_an_unmeasurable_fd_count_is_not_a_failure(self):
        report = _healthy_report()
        report["after_drain"]["fd_growth"] = None
        self.assertEqual(soak.evaluate(report, LIMITS), [])


class LiveSoakTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = soak.soak(requests=24, threads=3, warmup=6, heap_requests=24)

    def test_every_response_was_correct_and_the_run_passes(self):
        self.assertEqual(self.report["problems"], [])
        self.assertEqual(self.report["verdict"], "pass")
        for round_ in self.report["rounds"]:
            self.assertEqual(round_["failures"], 0)
            self.assertEqual(round_["answered"], 24)

    def test_bodies_are_compared_against_an_idle_baseline(self):
        # Most endpoints are byte-stable when idle; those must stay identical
        # under load (corruption / cross-request bleed would show here).
        self.assertGreaterEqual(self.report["deterministic_endpoints_compared"], 5)

    @pytest.mark.slow  # live soak under load (~1.2 CPU-s)

    def test_a_body_that_drifts_under_load_is_reported(self):
        client = mock.Mock()
        client.call.return_value = (200, False, 0.001, "different-digest")
        baselines = {("GET", "/api/v1/status", True): "idle-digest"}
        with mock.patch.object(soak, "PLAN", (("GET", "/api/v1/status", True, (200,)),)):
            result = soak.run_round(client, 3, 1, 1, baselines)
        self.assertEqual(result["failures"], 3)
        self.assertIn("differs from its idle baseline", result["failure_samples"][0])

    def test_the_server_drains_and_leaves_nothing_behind(self):
        after = self.report["after_drain"]
        self.assertTrue(after["drained"])
        self.assertLessEqual(after["thread_growth"], LIMITS["max_thread_growth"])

    def test_the_same_measurement_fails_against_an_impossible_limit(self):
        # Bite check on the real report: a ceiling below any possible growth
        # (growth can be small or even negative under load, so a negative cap)
        # must be reported rather than ignored.
        impossible = dict(LIMITS, max_heap_growth_kib=-1e9)
        self.assertTrue(any("heap" in p for p in soak.evaluate(self.report, impossible)))

    def test_render_names_the_verdict(self):
        self.assertIn("API load/soak: PASS", soak.render(self.report))


class CliTests(unittest.TestCase):
    def test_invalid_arguments_exit_2(self):
        self.assertEqual(soak.main(["--requests", "0"]), 2)
        self.assertEqual(soak.main(["--threads", "0"]), 2)


if __name__ == "__main__":
    unittest.main()
