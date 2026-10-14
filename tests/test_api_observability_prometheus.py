"""Issue #744: Prometheus text exposition over the canonical metrics document."""
from __future__ import annotations

from copy import deepcopy
import re
import unittest

from idkmesh.api_observability import LATENCY_BUCKETS_MS, ApiMetrics
from idkmesh.otel_metrics import (
    PROMETHEUS_TEXT_CONTENT_TYPE,
    OtlpMetricsInputError,
    render_prometheus_text,
)

SAMPLE = re.compile(
    r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{([a-z_]+="[^"\\\n]*"(,[a-z_]+="[^"\\\n]*")*)\})? '
    r"(-?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?|\+Inf)$"
)
ALLOWED_LABELS = {
    "status_class", "le", "reason", "dependency", "state", "service",
    "service_version",
}


def _document(**overrides):
    metrics = ApiMetrics()
    for status, duration in [(200, 3), (200, 40), (404, 12), (503, 700), (200, 20000)]:
        metrics.record_response(status=status, duration_ms=duration)
    metrics.note_admission_rejection("overloaded")
    metrics.note_admission_rejection("overloaded")
    metrics.note_admission_rejection("draining")
    metrics.note_run_evidence_inspection()
    args = {
        "service": "idkmesh-control-tower",
        "service_version": "0.1",
        "in_flight_requests": 2,
        "max_concurrent_requests": 8,
        "event_stream_clients": 1,
        "max_event_stream_clients": 4,
        "product_spine_store_configured": True,
    }
    args.update(overrides)
    return metrics.document(**args)


def _parse(text):
    samples = {}
    types = {}
    helps = set()
    for line in text.splitlines():
        if line.startswith("# HELP "):
            helps.add(line.split(" ", 3)[2])
        elif line.startswith("# TYPE "):
            _, _, name, kind = line.split(" ")
            types[name] = kind
        else:
            match = SAMPLE.match(line)
            assert match, f"not a valid sample line: {line!r}"
            labels = dict(re.findall(r'([a-z_]+)="([^"]*)"', match.group(3) or ""))
            samples[(match.group(1), tuple(sorted(labels.items())))] = match.group(5)
    return samples, types, helps


class PrometheusTextTests(unittest.TestCase):
    def test_output_is_valid_text_exposition_with_help_and_type(self):
        text = render_prometheus_text(_document())
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))
        samples, types, helps = _parse(text)
        self.assertEqual(set(types), helps)
        for name, _labels in samples:
            base = re.sub(r"_(bucket|sum|count)$", "", name)
            self.assertIn(name if name in types else base, types, name)
        self.assertEqual(types["idkmesh_api_requests_total"], "counter")
        self.assertEqual(types["idkmesh_api_request_duration_seconds"], "histogram")
        self.assertEqual(types["idkmesh_api_in_flight_requests"], "gauge")
        self.assertIn("0.0.4", PROMETHEUS_TEXT_CONTENT_TYPE)

    def test_counters_gauges_and_status_classes_match_the_snapshot(self):
        samples, _types, _ = _parse(render_prometheus_text(_document()))

        def value(name, **labels):
            return samples[(name, tuple(sorted(labels.items())))]

        self.assertEqual(value("idkmesh_api_requests_total", status_class="2xx"), "3")
        self.assertEqual(value("idkmesh_api_requests_total", status_class="4xx"), "1")
        self.assertEqual(value("idkmesh_api_requests_total", status_class="5xx"), "1")
        self.assertEqual(value("idkmesh_api_requests_total", status_class="1xx"), "0")
        self.assertEqual(value("idkmesh_api_in_flight_requests"), "2")
        self.assertEqual(value("idkmesh_api_max_concurrent_requests"), "8")
        self.assertEqual(value("idkmesh_api_event_stream_clients"), "1")
        self.assertEqual(value("idkmesh_api_max_event_stream_clients"), "4")
        self.assertEqual(
            value("idkmesh_api_admission_rejections_total", reason="overloaded"), "2"
        )
        self.assertEqual(
            value("idkmesh_api_admission_rejections_total", reason="draining"), "1"
        )
        self.assertEqual(value("idkmesh_api_run_evidence_inspections_total"), "1")

    def test_histogram_is_cumulative_in_seconds_and_ends_at_count(self):
        samples, _types, _ = _parse(render_prometheus_text(_document()))
        buckets = [
            (labels[0][1], int(v))
            for (name, labels), v in samples.items()
            if name == "idkmesh_api_request_duration_seconds_bucket"
        ]
        self.assertEqual(len(buckets), len(LATENCY_BUCKETS_MS) + 1)
        self.assertEqual(buckets[-1], ("+Inf", 5))
        counts = [c for _le, c in buckets]
        self.assertEqual(counts, sorted(counts))
        bounds = [float(le) for le, _ in buckets[:-1]]
        self.assertEqual(bounds, [b / 1000.0 for b in LATENCY_BUCKETS_MS])
        self.assertEqual(dict(buckets)["0.005"], 1)   # 3 ms
        self.assertEqual(dict(buckets)["1"], 4)       # all but the 20 s response
        self.assertEqual(dict(buckets)["10"], 4)
        self.assertEqual(
            samples[("idkmesh_api_request_duration_seconds_count", ())], "5"
        )
        self.assertAlmostEqual(
            float(samples[("idkmesh_api_request_duration_seconds_sum", ())]),
            (3 + 40 + 12 + 700 + 20000) / 1000.0,
        )

    def test_dependency_state_is_a_stateset_not_a_health_claim(self):
        for configured, hot in ((True, "configured_unprobed"), (False, "not_configured")):
            samples, _t, _h = _parse(
                render_prometheus_text(
                    _document(product_spine_store_configured=configured)
                )
            )
            states = {
                dict(labels)["state"]: v
                for (name, labels), v in samples.items()
                if name == "idkmesh_api_dependency_state"
            }
            self.assertEqual(set(states), {"not_configured", "configured_unprobed"})
            self.assertEqual({s for s, v in states.items() if v == "1"}, {hot})

    def test_unimplemented_signals_are_omitted_not_exported_as_zero(self):
        text = render_prometheus_text(_document())
        self.assertNotIn("rate_limit", text)
        self.assertNotIn("human_decision", text)
        self.assertNotIn("rate_limited", text)

    def test_label_names_are_a_closed_set(self):
        samples, _t, _h = _parse(render_prometheus_text(_document()))
        seen = {k for (_n, labels) in samples for k, _v in labels}
        self.assertLessEqual(seen, ALLOWED_LABELS)

    def test_output_is_deterministic_and_does_not_mutate_input(self):
        document = _document()
        before = deepcopy(document)
        self.assertEqual(
            render_prometheus_text(document), render_prometheus_text(document)
        )
        self.assertEqual(document, before)

    def test_unsafe_service_identity_is_rejected_not_escaped(self):
        for service in (
            'evil"} 1\n# injected',
            "has space",
            "new\nline",
            "back\\slash",
            "x" * 129,
        ):
            with self.subTest(service=service[:20]):
                with self.assertRaises(OtlpMetricsInputError):
                    render_prometheus_text(_document(service=service))
        with self.assertRaises(OtlpMetricsInputError):
            render_prometheus_text(_document(service_version="1\n2"))

    def test_relaxed_or_inconsistent_documents_fail_closed(self):
        base = _document()
        cases = {
            "privacy flag": lambda d: d["telemetry"].update(query_labels=True),
            "authority": lambda d: d["authority"].update(git_push=True),
            "rate limit counter": lambda d: d["admission"].update(
                rate_limit_rejections_total=5
            ),
            "decision counter": lambda d: d["operations"].update(
                human_decision_ingestions_total=1
            ),
            "total mismatch": lambda d: d["requests"].update(total=99),
            "bucket regression": lambda d: d["latency_ms"]["buckets"][3].update(count=0),
            "unknown dependency": lambda d: d["dependencies"]["product_spine_store"]
            .update(state="healthy"),
        }
        for name, fn in cases.items():
            with self.subTest(case=name):
                document = deepcopy(base)
                fn(document)
                with self.assertRaises(OtlpMetricsInputError):
                    render_prometheus_text(document)
        with self.assertRaises(OtlpMetricsInputError):
            render_prometheus_text([])  # type: ignore[arg-type]

    def test_no_request_derived_text_can_appear_in_output(self):
        # The document has no field that carries request data; assert the
        # rendered text contains only the fixed vocabulary plus service identity.
        text = render_prometheus_text(_document())
        for token in re.findall(r'"([^"]*)"', text):
            self.assertRegex(
                token,
                r"^(\+Inf|[0-9.]+|[0-9]xx|overloaded|draining|product_spine_store|"
                r"not_configured|configured_unprobed|idkmesh-control-tower|0\.1)$",
            )


if __name__ == "__main__":
    unittest.main()
