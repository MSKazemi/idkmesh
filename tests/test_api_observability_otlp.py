"""Tests for the dependency-free OTLP metrics adapter (issue #744)."""

from __future__ import annotations

import json
import unittest

from idkmesh.api_observability import ApiMetrics, LATENCY_BUCKETS_MS
from idkmesh.otel_metrics import (
    OtlpMetricsInputError,
    build_otlp_metrics_request,
)

START = 1_000_000_000
END = 2_000_000_000


def _document() -> dict:
    metrics = ApiMetrics()
    metrics.record_response(status=200, duration_ms=4.0)
    metrics.record_response(status=404, duration_ms=17.0)
    metrics.record_response(status=503, duration_ms=1200.0)
    metrics.note_admission_rejection("overloaded")
    metrics.note_run_evidence_inspection()
    return metrics.document(
        service="idkmesh-control-tower",
        service_version="0.1",
        in_flight_requests=2,
        max_concurrent_requests=16,
        event_stream_clients=1,
        max_event_stream_clients=8,
        product_spine_store_configured=False,
    )


def _metrics_by_name(payload: dict) -> dict[str, dict]:
    metrics = payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    return {metric["name"]: metric for metric in metrics}


class OtlpMetricsAdapterTests(unittest.TestCase):
    def test_maps_canonical_document_to_otlp_json_without_sensitive_labels(self) -> None:
        payload = build_otlp_metrics_request(
            _document(),
            start_time_unix_nano=START,
            time_unix_nano=END,
        )
        metrics = _metrics_by_name(payload)

        request_points = metrics["idkmesh.api.requests"]["sum"]["dataPoints"]
        by_class = {
            point["attributes"][0]["value"]["stringValue"]: int(point["asInt"])
            for point in request_points
        }
        self.assertEqual(
            by_class,
            {"1xx": 0, "2xx": 1, "3xx": 0, "4xx": 1, "5xx": 1},
        )
        self.assertEqual(
            metrics["idkmesh.api.requests"]["sum"]["aggregationTemporality"],
            2,
        )
        self.assertTrue(metrics["idkmesh.api.requests"]["sum"]["isMonotonic"])

        histogram = metrics["idkmesh.api.request.duration"]["histogram"]
        point = histogram["dataPoints"][0]
        self.assertEqual(histogram["aggregationTemporality"], 2)
        self.assertEqual(point["count"], "3")
        self.assertEqual(point["explicitBounds"], list(LATENCY_BUCKETS_MS))
        self.assertEqual(sum(int(value) for value in point["bucketCounts"]), 3)
        self.assertEqual(len(point["bucketCounts"]), len(LATENCY_BUCKETS_MS) + 1)
        self.assertEqual(point["bucketCounts"][0], "1")
        self.assertEqual(point["bucketCounts"][2], "1")
        self.assertEqual(point["bucketCounts"][8], "1")

        resource_attributes = payload["resourceMetrics"][0]["resource"]["attributes"]
        resource = {
            item["key"]: item["value"]
            for item in resource_attributes
        }
        self.assertEqual(
            resource["service.name"]["stringValue"],
            "idkmesh-control-tower",
        )
        self.assertEqual(resource["service.version"]["stringValue"], "0.1")

        rendered = json.dumps(payload, sort_keys=True).lower()
        for forbidden in (
            "authorization",
            "x-idkmesh-ui-token",
            "request_id",
            "run_id",
            "work_unit_id",
            "prompt",
            "evidence_report",
            "http.target",
            "url.path",
            "url.query",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_adapter_is_deterministic_and_transport_free(self) -> None:
        document = _document()
        first = build_otlp_metrics_request(
            document,
            start_time_unix_nano=START,
            time_unix_nano=END,
        )
        second = build_otlp_metrics_request(
            document,
            start_time_unix_nano=START,
            time_unix_nano=END,
        )
        self.assertEqual(first, second)

    def test_cumulative_source_buckets_become_per_bucket_otlp_counts(self) -> None:
        document = _document()
        source = [bucket["count"] for bucket in document["latency_ms"]["buckets"]]
        payload = build_otlp_metrics_request(
            document,
            start_time_unix_nano=START,
            time_unix_nano=END,
        )
        point = _metrics_by_name(payload)["idkmesh.api.request.duration"][
            "histogram"
        ]["dataPoints"][0]
        otlp_counts = [int(value) for value in point["bucketCounts"]]

        rebuilt = []
        running = 0
        for count in otlp_counts[:-1]:
            running += count
            rebuilt.append(running)
        self.assertEqual(rebuilt, source)
        self.assertEqual(running + otlp_counts[-1], document["latency_ms"]["count"])

    def test_invalid_timestamps_fail_closed(self) -> None:
        document = _document()
        bad_values = (
            (0, END),
            (START, 0),
            (END, START),
            (True, END),
        )
        for start, end in bad_values:
            with self.subTest(start=start, end=end):
                with self.assertRaises(OtlpMetricsInputError):
                    build_otlp_metrics_request(
                        document,
                        start_time_unix_nano=start,
                        time_unix_nano=end,
                    )

    def test_inconsistent_status_totals_fail_closed(self) -> None:
        document = _document()
        document["requests"]["by_status_class"]["2xx"] += 1
        with self.assertRaisesRegex(
            OtlpMetricsInputError, "sum of status-class counters"
        ):
            build_otlp_metrics_request(
                document,
                start_time_unix_nano=START,
                time_unix_nano=END,
            )

    def test_nonmonotonic_cumulative_histogram_fails_closed(self) -> None:
        document = _document()
        document["latency_ms"]["buckets"][3]["count"] = 0
        with self.assertRaisesRegex(OtlpMetricsInputError, "nondecreasing"):
            build_otlp_metrics_request(
                document,
                start_time_unix_nano=START,
                time_unix_nano=END,
            )

    def test_unimplemented_counters_cannot_be_manufactured(self) -> None:
        document = _document()
        document["operations"]["human_decision_ingestions_total"] = 1
        with self.assertRaisesRegex(
            OtlpMetricsInputError, "human-decision ingestion"
        ):
            build_otlp_metrics_request(
                document,
                start_time_unix_nano=START,
                time_unix_nano=END,
            )


if __name__ == "__main__":
    unittest.main()
