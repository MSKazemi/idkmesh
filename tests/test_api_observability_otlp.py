"""Tests for the dependency-free OTLP metrics adapter (#744)."""

from __future__ import annotations

import json
import unittest

from idkmesh.api_observability import ApiMetrics
from idkmesh.otlp_metrics import (
    OTLP_AGGREGATION_TEMPORALITY_CUMULATIVE,
    OtlpMetricsError,
    render_otlp_json,
    to_otlp_export_request,
)


START = 1_700_000_000_000_000_000
NOW = START + 5_000_000_000


def make_document() -> dict:
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


def metric_map(payload: dict) -> dict[str, list[dict]]:
    metrics = payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    by_name: dict[str, list[dict]] = {}
    for metric in metrics:
        by_name.setdefault(metric["name"], []).append(metric)
    return by_name


class OtlpMetricsAdapterTests(unittest.TestCase):
    def test_serializes_otlp_http_json_shape_with_integer_enum(self) -> None:
        payload = to_otlp_export_request(
            make_document(),
            start_time_unix_nano=START,
            time_unix_nano=NOW,
        )
        resource = payload["resourceMetrics"][0]
        attributes = {
            row["key"]: row["value"]
            for row in resource["resource"]["attributes"]
        }
        self.assertEqual(
            attributes["service.name"]["stringValue"],
            "idkmesh-control-tower",
        )
        self.assertEqual(
            attributes["service.version"]["stringValue"], "0.1"
        )

        metrics = metric_map(payload)
        request_sum = metrics["idkmesh.api.http.requests"][0]["sum"]
        self.assertEqual(
            request_sum["aggregationTemporality"],
            OTLP_AGGREGATION_TEMPORALITY_CUMULATIVE,
        )
        self.assertIsInstance(request_sum["aggregationTemporality"], int)
        self.assertEqual(request_sum["dataPoints"][0]["asInt"], "3")
        self.assertEqual(
            request_sum["dataPoints"][0]["startTimeUnixNano"], str(START)
        )
        self.assertEqual(
            request_sum["dataPoints"][0]["timeUnixNano"], str(NOW)
        )

    def test_status_classes_are_fixed_cardinality(self) -> None:
        payload = to_otlp_export_request(
            make_document(),
            start_time_unix_nano=START,
            time_unix_nano=NOW,
        )
        rows = metric_map(payload)["idkmesh.api.http.responses"]
        self.assertEqual(len(rows), 5)
        values = {}
        for metric in rows:
            point = metric["sum"]["dataPoints"][0]
            attrs = {
                item["key"]: item["value"]["stringValue"]
                for item in point["attributes"]
            }
            values[attrs["idkmesh.http.status_class"]] = int(point["asInt"])
        self.assertEqual(
            values,
            {"1xx": 0, "2xx": 1, "3xx": 0, "4xx": 1, "5xx": 1},
        )

    def test_cumulative_latency_buckets_become_otlp_per_bucket_counts(self) -> None:
        document = make_document()
        payload = to_otlp_export_request(
            document,
            start_time_unix_nano=START,
            time_unix_nano=NOW,
        )
        histogram = metric_map(payload)[
            "idkmesh.api.http.request.duration"
        ][0]["histogram"]
        point = histogram["dataPoints"][0]
        cumulative = [item["count"] for item in document["latency_ms"]["buckets"]]
        expected = []
        previous = 0
        for count in cumulative:
            expected.append(count - previous)
            previous = count
        expected.append(document["latency_ms"]["count"] - previous)

        self.assertEqual(
            histogram["aggregationTemporality"],
            OTLP_AGGREGATION_TEMPORALITY_CUMULATIVE,
        )
        self.assertEqual(point["bucketCounts"], [str(v) for v in expected])
        self.assertEqual(
            point["explicitBounds"],
            [item["le_ms"] for item in document["latency_ms"]["buckets"]],
        )
        self.assertEqual(
            sum(int(value) for value in point["bucketCounts"]),
            document["latency_ms"]["count"],
        )

    def test_unimplemented_features_remain_explicit_not_synthetic_success(self) -> None:
        payload = to_otlp_export_request(
            make_document(),
            start_time_unix_nano=START,
            time_unix_nano=NOW,
        )
        rows = metric_map(payload)["idkmesh.api.feature.available"]
        states = {}
        for row in rows:
            point = row["gauge"]["dataPoints"][0]
            attrs = {
                item["key"]: next(iter(item["value"].values()))
                for item in point["attributes"]
            }
            states[attrs["idkmesh.feature"]] = (
                int(point["asInt"]),
                attrs["idkmesh.feature.status"],
            )
        self.assertEqual(states["rate_limiting"], (0, "not_implemented"))
        self.assertEqual(
            states["human_decision_ingestion"],
            (0, "not_implemented"),
        )

    def test_product_spine_state_is_configuration_presence_not_health(self) -> None:
        payload = to_otlp_export_request(
            make_document(),
            start_time_unix_nano=START,
            time_unix_nano=NOW,
        )
        metric = metric_map(payload)["idkmesh.api.dependency.configured"][0]
        point = metric["gauge"]["dataPoints"][0]
        self.assertEqual(point["asInt"], "0")
        rendered = json.dumps(metric)
        self.assertIn("not_configured", rendered)
        self.assertNotIn("healthy", rendered.lower())

    def test_adapter_fails_closed_on_non_monotonic_cumulative_buckets(self) -> None:
        document = make_document()
        document["latency_ms"]["buckets"][1]["count"] = 2
        document["latency_ms"]["buckets"][2]["count"] = 1
        with self.assertRaises(OtlpMetricsError):
            to_otlp_export_request(
                document,
                start_time_unix_nano=START,
                time_unix_nano=NOW,
            )

    def test_adapter_fails_closed_if_privacy_contract_is_relaxed(self) -> None:
        document = make_document()
        document["telemetry"]["payload_labels"] = True
        with self.assertRaises(OtlpMetricsError):
            to_otlp_export_request(
                document,
                start_time_unix_nano=START,
                time_unix_nano=NOW,
            )

    def test_adapter_rejects_invalid_or_reversed_timestamps(self) -> None:
        document = make_document()
        for start, now in ((0, NOW), (START, START - 1), (True, NOW)):
            with self.subTest(start=start, now=now):
                with self.assertRaises(OtlpMetricsError):
                    to_otlp_export_request(
                        document,
                        start_time_unix_nano=start,
                        time_unix_nano=now,
                    )

    def test_render_is_deterministic_strict_json_and_contains_no_secret_fields(self) -> None:
        document = make_document()
        first = render_otlp_json(
            document,
            start_time_unix_nano=START,
            time_unix_nano=NOW,
        )
        second = render_otlp_json(
            document,
            start_time_unix_nano=START,
            time_unix_nano=NOW,
        )
        self.assertEqual(first, second)
        parsed = json.loads(first)
        self.assertIn("resourceMetrics", parsed)
        lowered = first.lower()
        for forbidden in (
            "authorization",
            "x-idkmesh-ui-token",
            "request_id",
            "run_id",
            "work_unit_id",
            "prompt",
            "evidence_report",
        ):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
