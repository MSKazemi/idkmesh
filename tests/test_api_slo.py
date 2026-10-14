"""Issue #744: machine-readable SLO contract and offline evaluators."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

from idkmesh.api_observability import ApiMetrics
from idkmesh.api_slo import (
    SloContractError,
    default_slo_contract,
    evaluate_overload_alert,
    evaluate_saturation_conditions,
    evaluate_slo_interval,
    validate_slo_contract,
)
from idkmesh.otel_metrics import evaluate_api_metrics_interval

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    import jsonschema

ROOT = Path(__file__).resolve().parents[1]
WINDOW_NANOS = 300 * 1_000_000_000


def _snapshot(metrics, *, in_flight=0, streams=0):
    return metrics.document(
        service="idkmesh-control-tower",
        service_version="0.1",
        in_flight_requests=in_flight,
        max_concurrent_requests=10,
        event_stream_clients=streams,
        max_event_stream_clients=4,
        product_spine_store_configured=False,
    )


def _interval(responses, *, overloads=0, nanos=WINDOW_NANOS):
    metrics = ApiMetrics()
    before = _snapshot(metrics)
    for status, duration in responses:
        metrics.record_response(status=status, duration_ms=duration)
    for _ in range(overloads):
        metrics.note_admission_rejection("overloaded")
    return evaluate_api_metrics_interval(
        before,
        _snapshot(metrics),
        before_process_identity="epoch-1",
        after_process_identity="epoch-1",
        before_time_unix_nano=1_000_000_000,
        after_time_unix_nano=1_000_000_000 + nanos,
    )


class SloContractTests(unittest.TestCase):
    def test_default_contract_is_valid_and_matches_documented_targets(self):
        contract = validate_slo_contract(default_slo_contract())
        self.assertEqual(contract["window_seconds"], 300)
        by_id = {o["id"]: o for o in contract["objectives"]}
        self.assertEqual(by_id["server_error_fraction"]["threshold"], 0.01)
        self.assertEqual(by_id["latency_within_1000ms_fraction"]["threshold"], 0.95)
        self.assertEqual(
            by_id["overload_rejections"]["alert_after_consecutive_intervals"], 2
        )
        alerts = {a["id"]: a for a in contract["saturation_alerts"]}
        self.assertEqual(alerts["api_concurrency_hot"]["threshold"], 0.8)
        self.assertEqual(alerts["sse_saturation"]["threshold"], 1.0)

    def test_default_contract_returns_independent_copies(self):
        first = default_slo_contract()
        first["objectives"].clear()
        self.assertEqual(len(default_slo_contract()["objectives"]), 3)

    def test_committed_example_is_exactly_the_default_contract(self):
        example = json.loads(
            (ROOT / "examples/api/api-slo-contract.example.json").read_text("utf-8")
        )
        self.assertEqual(example, default_slo_contract())

    def test_contract_validation_is_fail_closed(self):
        def mutate(fn):
            contract = default_slo_contract()
            fn(contract)
            return contract

        bad = {
            "extra top-level key": mutate(lambda c: c.update(endpoint="http://x")),
            "missing key": mutate(lambda c: c.pop("claim")),
            "wrong kind": mutate(lambda c: c.update(kind="other")),
            "measured claim": mutate(lambda c: c.update(claim="measured")),
            "zero window": mutate(lambda c: c.update(window_seconds=0)),
            "bool window": mutate(lambda c: c.update(window_seconds=True)),
            "huge window": mutate(lambda c: c.update(window_seconds=10**9)),
            "authority merge": mutate(lambda c: c["authority"].update(merge=True)),
            "authority extra": mutate(lambda c: c["authority"].update(deploy=False)),
            "unknown objective id": mutate(
                lambda c: c["objectives"][0].update(id="path_latency")
            ),
            "objective order": mutate(lambda c: c["objectives"].reverse()),
            "dropped objective": mutate(lambda c: c["objectives"].pop()),
            "extra objective key": mutate(
                lambda c: c["objectives"][0].update(label="x")
            ),
            "error threshold 0": mutate(
                lambda c: c["objectives"][0].update(threshold=0)
            ),
            "error threshold >1": mutate(
                lambda c: c["objectives"][0].update(threshold=1.5)
            ),
            "error threshold nan": mutate(
                lambda c: c["objectives"][0].update(threshold=float("nan"))
            ),
            "error comparison": mutate(
                lambda c: c["objectives"][0].update(comparison="at_least")
            ),
            "latency bound": mutate(
                lambda c: c["objectives"][1].update(latency_bound_ms=500.0)
            ),
            "overload float": mutate(
                lambda c: c["objectives"][2].update(threshold=0.5)
            ),
            "overload consecutive 0": mutate(
                lambda c: c["objectives"][2].update(
                    alert_after_consecutive_intervals=0
                )
            ),
            "alert unknown id": mutate(
                lambda c: c["saturation_alerts"][0].update(id="x")
            ),
            "alert threshold 0": mutate(
                lambda c: c["saturation_alerts"][1].update(threshold=0)
            ),
            "alert negative duration": mutate(
                lambda c: c["saturation_alerts"][0].update(for_seconds=-1)
            ),
            "not an object": [],
        }
        for name, contract in bad.items():
            with self.subTest(case=name):
                with self.assertRaises(SloContractError):
                    validate_slo_contract(contract)

    @unittest.skipUnless(HAS_JSONSCHEMA, "requires jsonschema")
    def test_schema_accepts_default_and_rejects_relaxations(self):
        schema = json.loads(
            (ROOT / "schemas/idkmesh-api-slo-contract-v0.1.schema.json").read_text(
                "utf-8"
            )
        )
        validator = jsonschema.Draft202012Validator(schema)
        self.assertEqual([], list(validator.iter_errors(default_slo_contract())))
        for name, fn in {
            "authority": lambda c: c["authority"].update(merge=True),
            "extra": lambda c: c.update(url="http://x"),
            "objective id": lambda c: c["objectives"][0].update(id="x"),
            "latency bound": lambda c: c["objectives"][1].update(latency_bound_ms=5),
            "claim": lambda c: c.update(claim="measured"),
        }.items():
            with self.subTest(case=name):
                contract = default_slo_contract()
                fn(contract)
                self.assertNotEqual([], list(validator.iter_errors(contract)))

    def test_python_validator_rejects_relaxations_the_schema_also_rejects(self):
        # The strict Python validator must reject these structural relaxations,
        # which the schema test above also rejects (guards drift between the two).
        for fn in (
            lambda c: c["authority"].update(git_push=True),
            lambda c: c.update(profile="multi_user"),
            lambda c: c["objectives"][1].update(latency_bound_ms=5),
        ):
            contract = default_slo_contract()
            fn(contract)
            with self.assertRaises(SloContractError):
                validate_slo_contract(contract)


class SloIntervalTests(unittest.TestCase):
    def test_healthy_interval_meets_every_objective(self):
        interval = _interval([(200, 10)] * 99 + [(404, 20)])
        result = evaluate_slo_interval(interval)
        self.assertEqual(result["status"], "evaluated")
        self.assertTrue(result["all_met"])
        self.assertEqual(result["authority"], "none")
        self.assertEqual(result["interval_seconds"], 300.0)
        self.assertEqual(
            [o["state"] for o in result["objectives"]], ["met"] * 3
        )

    def test_client_errors_do_not_breach_the_server_error_objective(self):
        result = evaluate_slo_interval(_interval([(404, 5)] * 50))
        self.assertTrue(result["all_met"])

    def test_error_budget_boundary_is_strict_less_than(self):
        # exactly 1% 5xx: threshold is "less than 1%", so this breaches.
        result = evaluate_slo_interval(_interval([(500, 5)] + [(200, 5)] * 99))
        states = {o["id"]: o["state"] for o in result["objectives"]}
        self.assertEqual(states["server_error_fraction"], "breached")
        self.assertFalse(result["all_met"])
        # just under 1%: met.
        result = evaluate_slo_interval(_interval([(500, 5)] + [(200, 5)] * 100))
        states = {o["id"]: o["state"] for o in result["objectives"]}
        self.assertEqual(states["server_error_fraction"], "met")

    def test_latency_boundary_is_at_least_95_percent(self):
        slow = [(200, 1500)]
        result = evaluate_slo_interval(_interval([(200, 1000)] * 95 + slow * 5))
        states = {o["id"]: o["state"] for o in result["objectives"]}
        self.assertEqual(states["latency_within_1000ms_fraction"], "met")
        result = evaluate_slo_interval(_interval([(200, 1000)] * 94 + slow * 6))
        states = {o["id"]: o["state"] for o in result["objectives"]}
        self.assertEqual(states["latency_within_1000ms_fraction"], "breached")

    def test_any_overload_rejection_breaches_the_overload_objective(self):
        result = evaluate_slo_interval(_interval([(200, 5)] * 10, overloads=1))
        states = {o["id"]: o["state"] for o in result["objectives"]}
        self.assertEqual(states["overload_rejections"], "breached")

    def test_short_interval_is_unknown_not_met(self):
        result = evaluate_slo_interval(
            _interval([(200, 5)] * 10, nanos=WINDOW_NANOS - 1)
        )
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "interval_shorter_than_window")
        self.assertNotIn("all_met", result)

    def test_longer_interval_is_accepted_and_reports_its_length(self):
        result = evaluate_slo_interval(
            _interval([(200, 5)] * 10, nanos=2 * WINDOW_NANOS)
        )
        self.assertEqual(result["interval_seconds"], 600.0)

    def test_unknown_or_malformed_intervals_are_never_met(self):
        measured = _interval([(200, 5)] * 5)
        hostile = [
            {"status": "unknown", "reason": "process_changed", "authority": "none"},
            None,
            "measured",
            [],
            {},
            {**measured, "authority": "merge"},
            {**measured, "requests": 0},
            {**measured, "requests": True},
            {**measured, "server_error_fraction": float("nan")},
            {**measured, "server_error_fraction": -0.1},
            {**measured, "within_1000ms_fraction": 1.5},
            {**measured, "overload_rejections": -1},
            {**measured, "interval_nanoseconds": "300"},
        ]
        for interval in hostile:
            with self.subTest(interval=repr(interval)[:60]):
                result = evaluate_slo_interval(interval)
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(result["reason"], "interval_not_measured")
                self.assertEqual(result["authority"], "none")
                self.assertNotIn("all_met", result)

    def test_unknown_result_never_reflects_hostile_input(self):
        secret = "sk-test-SECRET-sentinel"
        result = evaluate_slo_interval({"status": secret, "requests": secret})
        self.assertNotIn(secret, json.dumps(result))

    def test_custom_contract_changes_the_verdict_and_invalid_one_raises(self):
        contract = default_slo_contract()
        contract["objectives"][0]["threshold"] = 0.5
        interval = _interval([(500, 5)] + [(200, 5)] * 9)
        self.assertEqual(
            evaluate_slo_interval(interval, contract)["objectives"][0]["state"],
            "met",
        )
        self.assertEqual(
            evaluate_slo_interval(interval)["objectives"][0]["state"], "breached"
        )
        contract["authority"]["merge"] = True
        with self.assertRaises(SloContractError):
            evaluate_slo_interval(interval, contract)

    def test_evaluation_does_not_mutate_inputs(self):
        interval = _interval([(200, 5)] * 5)
        contract = default_slo_contract()
        before = (deepcopy(interval), deepcopy(contract))
        evaluate_slo_interval(interval, contract)
        self.assertEqual((interval, contract), before)


class OverloadAlertTests(unittest.TestCase):
    def test_fires_only_after_two_consecutive_breaches(self):
        ok = _interval([(200, 5)] * 5)
        bad = _interval([(200, 5)] * 5, overloads=2)
        self.assertFalse(evaluate_overload_alert([ok, bad])["firing"])
        self.assertFalse(evaluate_overload_alert([bad, ok])["firing"])
        result = evaluate_overload_alert([ok, bad, bad])
        self.assertTrue(result["firing"])
        self.assertEqual(result["consecutive_intervals"], 2)
        self.assertEqual(result["authority"], "none")

    def test_not_enough_or_unknown_intervals_are_unknown_not_quiet(self):
        bad = _interval([(200, 5)] * 5, overloads=1)
        self.assertEqual(
            evaluate_overload_alert([bad])["reason"], "not_enough_intervals"
        )
        self.assertEqual(evaluate_overload_alert([])["status"], "unknown")
        restart = {"status": "unknown", "reason": "process_changed", "authority": "none"}
        result = evaluate_overload_alert([bad, restart])
        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("firing", result)

    def test_non_sequence_is_rejected(self):
        self.assertEqual(evaluate_overload_alert("ab")["status"], "unknown")
        self.assertEqual(evaluate_overload_alert(None)["status"], "unknown")


class SaturationTests(unittest.TestCase):
    def conditions(self, **kwargs):
        result = evaluate_saturation_conditions(_snapshot(ApiMetrics(), **kwargs))
        return {c["id"]: c for c in result["conditions"]}

    def test_below_thresholds_are_not_met(self):
        conditions = self.conditions(in_flight=7, streams=3)
        self.assertFalse(conditions["api_concurrency_hot"]["condition_met"])
        self.assertFalse(conditions["sse_saturation"]["condition_met"])

    def test_at_thresholds_are_met_and_duration_is_not_evaluated(self):
        conditions = self.conditions(in_flight=8, streams=4)
        self.assertTrue(conditions["api_concurrency_hot"]["condition_met"])
        self.assertTrue(conditions["sse_saturation"]["condition_met"])
        self.assertEqual(conditions["api_concurrency_hot"]["for_seconds"], 300)
        for condition in conditions.values():
            self.assertIs(condition["duration_evaluated"], False)

    def test_relaxed_or_malformed_snapshots_are_unknown_and_not_reflected(self):
        secret = "Bearer-SECRET-sentinel"
        snapshot = _snapshot(ApiMetrics())
        for name, fn in {
            "privacy flag": lambda d: d["telemetry"].update(path_labels=True),
            "authority": lambda d: d["authority"].update(merge=True),
            "kind": lambda d: d.update(kind=secret),
            "service": lambda d: d.update(service=7),
        }.items():
            with self.subTest(case=name):
                document = deepcopy(snapshot)
                fn(document)
                result = evaluate_saturation_conditions(document)
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(result["reason"], "invalid_snapshot")
                self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(evaluate_saturation_conditions([])["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
