"""Issue #744: safe telemetry interval comparisons, no collector network I/O."""
from copy import deepcopy
import unittest

from idkmesh.api_observability import ApiMetrics
from idkmesh.otel_metrics import evaluate_api_metrics_interval


def _snapshot(metrics):
    return metrics.document(
        service="idkmesh-control-tower",
        service_version="0.1",
        in_flight_requests=0,
        max_concurrent_requests=4,
        event_stream_clients=0,
        max_event_stream_clients=2,
        product_spine_store_configured=False,
    )


class ApiMetricsIntervalTests(unittest.TestCase):
    def compare(self, first, last, **kwargs):
        args = {
            "before_process_identity": "collector-attested-epoch-1",
            "after_process_identity": "collector-attested-epoch-1",
            "before_time_unix_nano": 1_000_000_000,
            "after_time_unix_nano": 2_000_000_000,
        }
        args.update(kwargs)
        return evaluate_api_metrics_interval(first, last, **args)

    def test_valid_interval_and_fixed_cardinality(self):
        metrics = ApiMetrics()
        before = _snapshot(metrics)
        for status, duration in [(200, 5), (200, 1500), (503, 100), (404, 10)]:
            metrics.record_response(status=status, duration_ms=duration)
        metrics.note_admission_rejection("overloaded")
        result = self.compare(before, _snapshot(metrics))
        self.assertEqual(result["status"], "measured")
        self.assertEqual(result["requests"], 4)
        self.assertEqual(result["server_errors"], 1)
        self.assertEqual(result["server_error_fraction"], 0.25)
        self.assertEqual(result["within_1000ms"], 3)
        self.assertEqual(result["within_1000ms_fraction"], 0.75)
        self.assertEqual(result["overload_rejections"], 1)
        self.assertNotIn("collector-attested-epoch-1", repr(result))

    def test_restart_is_unknown_even_with_increasing_counts(self):
        metrics = ApiMetrics()
        first = _snapshot(metrics)
        metrics.record_response(status=200, duration_ms=10)
        self.assertEqual(
            self.compare(first, _snapshot(metrics), after_process_identity="epoch-2")["reason"],
            "process_changed",
        )

    def test_malformed_privacy_or_schema_does_not_leak(self):
        metrics = ApiMetrics()
        first = _snapshot(metrics)
        metrics.record_response(status=500, duration_ms=10)
        after = _snapshot(metrics)
        after["telemetry"]["payload_labels"] = True
        after["service"] = "secret-user-token"
        result = self.compare(first, after)
        self.assertEqual(result, {
            "status": "unknown", "reason": "invalid_snapshot", "authority": "none",
        })
        self.assertNotIn("secret-user-token", str(result))

    def test_regressed_counter_is_unknown(self):
        metrics = ApiMetrics()
        first = _snapshot(metrics)
        metrics.record_response(status=200, duration_ms=10)
        last = _snapshot(metrics)
        bad = deepcopy(last)
        bad["requests"]["total"] = 0
        self.assertEqual(self.compare(last, first)["reason"], "counter_regression")
        self.assertEqual(self.compare(first, bad)["reason"], "invalid_snapshot")

    def test_zero_traffic_and_bad_clock_are_unknown(self):
        metrics = ApiMetrics()
        doc = _snapshot(metrics)
        self.assertEqual(self.compare(doc, doc)["reason"], "no_requests")
        self.assertEqual(
            self.compare(doc, doc, after_time_unix_nano=1_000_000_000)["reason"],
            "timestamps_not_increasing",
        )
