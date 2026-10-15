"""Issue #744: ``idkmesh api-slo`` operator CLI over the offline SLO evaluators.

Inputs are fed through standard input (``-``) or a few temp files; nothing
here starts a server or contacts a network.
"""
from __future__ import annotations

import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from idkmesh import cli
from idkmesh.api_observability import ApiMetrics
from idkmesh.api_slo import default_slo_contract

SERVICE = "idkmesh-control-tower"
EPOCH = "epoch-sentinel-7"
WINDOW_NANOS = 300 * 1_000_000_000
T0 = 1_000_000_000


def _snapshot(metrics: ApiMetrics, *, in_flight: int = 0, streams: int = 0) -> dict:
    return metrics.document(
        service=SERVICE,
        service_version="0.1",
        in_flight_requests=in_flight,
        max_concurrent_requests=10,
        event_stream_clients=streams,
        max_event_stream_clients=4,
        product_spine_store_configured=False,
    )


def _sample(metrics: dict, at: int, identity: str = EPOCH) -> dict:
    return {
        "process_identity": identity,
        "observed_unix_nano": at,
        "metrics": metrics,
    }


def _recording(*samples: dict) -> dict:
    return {
        "kind": "idkmesh-api-metrics-recording",
        "schema_version": "0.1",
        "samples": list(samples),
    }


def _two_samples(responses, *, overloads=0, nanos=WINDOW_NANOS, streams=0) -> dict:
    metrics = ApiMetrics()
    first = _snapshot(metrics)
    for status, duration in responses:
        metrics.record_response(status=status, duration_ms=duration)
    for _ in range(overloads):
        metrics.note_admission_rejection("overloaded")
    last = _snapshot(metrics, streams=streams)
    return _recording(_sample(first, T0), _sample(last, T0 + nanos))


HEALTHY = [(200, 20.0)] * 100


class ApiSloCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        # Building the full parser dominates the cost of main(); do it once.
        cls.parser = cli.build_parser()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def run_cli(self, argv, stdin: str = "") -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch("sys.stdin", io.StringIO(stdin)), \
                mock.patch.object(cli, "build_parser", return_value=self.parser):
            try:
                code = cli.main(list(argv))
            except SystemExit as exc:  # argparse rejects flags with exit 2
                code = int(exc.code)
        return code, out.getvalue(), err.getvalue()

    def check(self, recording, *extra, stdin_text=None):
        text = json.dumps(recording) if stdin_text is None else stdin_text
        return self.run_cli(
            ["api-slo", "check", "--metrics-interval", "-", "--json", *extra], text)

    def verdict(self, recording, *extra):
        code, out, err = self.check(recording, *extra)
        self.assertEqual(err, "")
        report = json.loads(out)
        self.assertEqual(report["exit_code"], code)
        return code, report, out

    # -- met / breached -------------------------------------------------

    def test_met_exits_zero_and_json_is_stable_and_label_free(self):
        code, report, out = self.verdict(_two_samples(HEALTHY))
        self.assertEqual(code, 0)
        self.assertEqual(report["verdict"], "met")
        self.assertEqual(report["authority"], "none")
        self.assertEqual(report["slo"]["requests"], 100)
        self.assertEqual(
            out, json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True) + "\n")
        self.assertNotIn(SERVICE, out)
        self.assertNotIn(EPOCH, out)

    def test_text_output_is_fixed_vocabulary(self):
        code, out, err = self.run_cli(
            ["api-slo", "check", "--metrics-interval", "-"],
            json.dumps(_two_samples(HEALTHY)))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("verdict: met (exit 0)", out)
        self.assertIn("objective server_error_fraction: met", out)
        self.assertNotIn(SERVICE, out)

    def test_server_error_breach_exits_one(self):
        code, report, _ = self.verdict(_two_samples([(500, 20.0)] * 5 + HEALTHY))
        self.assertEqual(code, 1)
        states = {o["id"]: o["state"] for o in report["slo"]["objectives"]}
        self.assertEqual(states["server_error_fraction"], "breached")

    def test_latency_and_overload_breaches_exit_one(self):
        code, _, _ = self.verdict(_two_samples([(200, 4000.0)] * 50 + HEALTHY))
        self.assertEqual(code, 1)
        code, _, _ = self.verdict(_two_samples(HEALTHY, overloads=1))
        self.assertEqual(code, 1)

    def test_overload_alert_fires_over_consecutive_intervals(self):
        metrics = ApiMetrics()
        samples = [_sample(_snapshot(metrics), T0)]
        for step in (1, 2):
            metrics.record_response(status=200, duration_ms=20.0)
            metrics.note_admission_rejection("overloaded")
            samples.append(_sample(_snapshot(metrics), T0 + step * WINDOW_NANOS))
        code, report, _ = self.verdict(_recording(*samples))
        self.assertEqual(code, 1)
        self.assertTrue(report["overload_alert"]["firing"])
        self.assertEqual(len(report["intervals"]), 2)

    def test_breach_outranks_unknown(self):
        # Full SSE saturation fires at once (for_seconds 0) while the
        # too-short interval leaves the objectives unknown.
        code, report, _ = self.verdict(
            _two_samples(HEALTHY, nanos=1_000_000_000, streams=4))
        self.assertEqual(report["slo"]["status"], "unknown")
        self.assertEqual(code, 1)

    # -- unknown is never zero ------------------------------------------

    def unknown_cases(self):
        too_short = _two_samples(HEALTHY, nanos=WINDOW_NANOS - 1)
        restarted = _two_samples(HEALTHY)
        restarted["samples"][1]["process_identity"] = "another-epoch"
        regressed = _two_samples(HEALTHY)
        regressed["samples"].reverse()
        regressed["samples"][0]["observed_unix_nano"] = T0
        regressed["samples"][1]["observed_unix_nano"] = T0 + WINDOW_NANOS
        malformed = _two_samples(HEALTHY)
        malformed["samples"][1]["metrics"]["requests"] = "SENTINEL-<script>"
        bad_time = _two_samples(HEALTHY)
        bad_time["samples"][1]["observed_unix_nano"] = "soon"
        no_requests = _two_samples([])
        hot = _two_samples(HEALTHY)
        hot["samples"][1]["metrics"] = _snapshot(ApiMetrics(), in_flight=9)
        return {
            "too_short": too_short,
            "restarted": restarted,
            "regressed": regressed,
            "malformed": malformed,
            "bad_time": bad_time,
            "no_requests": no_requests,
            "hot_without_duration": hot,
        }

    def test_untrustworthy_intervals_exit_three_never_zero(self):
        for name, recording in self.unknown_cases().items():
            with self.subTest(name):
                code, report, out = self.verdict(recording)
                self.assertEqual(code, 3)
                self.assertEqual(report["verdict"], "unknown")
                self.assertNotEqual(code, 0)
                self.assertNotIn("SENTINEL", out)
                self.assertNotIn(EPOCH, out)

    def test_specific_unknown_reasons_are_surfaced(self):
        cases = self.unknown_cases()
        reasons = {
            name: self.verdict(cases[name])[1]["slo"].get("reason")
            for name in ("too_short", "restarted", "malformed")
        }
        self.assertEqual(reasons["too_short"], "interval_shorter_than_window")
        self.assertEqual(reasons["restarted"], "interval_not_measured")
        self.assertEqual(reasons["malformed"], "interval_not_measured")
        report = self.verdict(cases["malformed"])[1]
        self.assertEqual(report["intervals"], [{"reason": "invalid_snapshot", "status": "unknown"}])
        self.assertEqual(report["saturation"]["status"], "unknown")

    def test_hot_condition_with_duration_is_unknown_not_met(self):
        _, report, _ = self.verdict(self.unknown_cases()["hot_without_duration"])
        states = {c["id"]: c["state"] for c in report["saturation"]["conditions"]}
        self.assertEqual(states["api_concurrency_hot"], "unknown")
        self.assertEqual(states["sse_saturation"], "met")

    # -- invalid input and flags: exit 2 --------------------------------

    def test_invalid_recordings_exit_two_without_reflecting_content(self):
        good = _two_samples(HEALTHY)
        one_sample = deepcopy(good)
        one_sample["samples"].pop()
        wrong_kind = deepcopy(good)
        wrong_kind["kind"] = "SENTINEL-kind"
        extra = deepcopy(good)
        extra["SENTINEL-extra"] = 1
        bad_sample = deepcopy(good)
        bad_sample["samples"][0] = {"SENTINEL-key": 1}
        for name, text in {
            "not_json": "{SENTINEL",
            "empty": "",
            "array": "[]",
            "nan": '{"kind": NaN}',
            "one_sample": json.dumps(one_sample),
            "wrong_kind": json.dumps(wrong_kind),
            "extra_field": json.dumps(extra),
            "bad_sample": json.dumps(bad_sample),
            "deep": "[" * 100000,
        }.items():
            with self.subTest(name):
                code, out, err = self.check(None, stdin_text=text)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.startswith("error: "))
                self.assertEqual(err.count("\n"), 1)
                self.assertNotIn("SENTINEL", err)

    def test_unreadable_files_exit_two_and_escape_the_path(self):
        missing = str(self.dir / "absent\x1b[31m.json")
        code, out, err = self.run_cli(
            ["api-slo", "check", "--metrics-interval", missing])
        self.assertEqual((code, out), (2, ""))
        self.assertNotIn("\x1b", err)
        self.assertIn("not found", err)
        code, _, err = self.run_cli(
            ["api-slo", "check", "--metrics-interval", str(self.dir)])
        self.assertEqual(code, 2)
        self.assertIn("not a regular file", err)
        binary = self.dir / "binary.json"
        binary.write_bytes(b"\xff\xfe\x00")
        code, _, err = self.run_cli(
            ["api-slo", "check", "--metrics-interval", str(binary)])
        self.assertEqual(code, 2)
        self.assertIn("UTF-8", err)

    def test_oversized_input_is_refused(self):
        with mock.patch.object(cli, "_SLO_MAX_INPUT_BYTES", 10):
            code, _, err = self.check(None, stdin_text=" " * 11)
        self.assertEqual(code, 2)
        self.assertIn("limit", err)

    def test_bad_flags_exit_two(self):
        for argv in (
            ["api-slo"],
            ["api-slo", "check"],
            ["api-slo", "check", "--metrics-interval"],
            ["api-slo", "check", "--metrics-interval", "-", "--bogus"],
            ["api-slo", "evaluate"],
            ["api-slo", "contract", "--metrics-interval", "-"],
        ):
            with self.subTest(argv):
                code, out, _ = self.run_cli(argv)
                self.assertEqual((code, out), (2, ""))

    # -- contracts ------------------------------------------------------

    def write_json(self, name: str, document) -> str:
        path = self.dir / name
        path.write_text(json.dumps(document), encoding="utf-8")
        return str(path)

    def test_contract_prints_the_default_and_validates_a_file(self):
        code, out, err = self.run_cli(["api-slo", "contract", "--json"])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out), default_slo_contract())
        code, out, _ = self.run_cli(["api-slo", "contract"])
        self.assertEqual(code, 0)
        self.assertIn("valid SLO contract", out)
        path = self.write_json("contract-ok.json", default_slo_contract())
        code, out, _ = self.run_cli(["api-slo", "contract", "--contract", path, "--json"])
        self.assertEqual((code, json.loads(out)), (0, default_slo_contract()))

    def test_custom_contract_changes_the_verdict(self):
        recording = _two_samples([(500, 20.0)] * 5 + HEALTHY)
        self.assertEqual(self.verdict(recording)[0], 1)
        relaxed = default_slo_contract()
        relaxed["objectives"][0]["threshold"] = 0.5
        path = self.write_json("contract-relaxed.json", relaxed)
        code, report, _ = self.verdict(recording, "--contract", path)
        self.assertEqual(code, 0)
        self.assertEqual(report["verdict"], "met")

    def test_bad_contracts_exit_two(self):
        relaxed_authority = default_slo_contract()
        relaxed_authority["authority"]["merge"] = True
        unknown_id = default_slo_contract()
        unknown_id["objectives"][0]["id"] = "SENTINEL-objective"
        extra = default_slo_contract()
        extra["SENTINEL-extra"] = 1
        for name, document in {
            "authority": relaxed_authority,
            "unknown_id": unknown_id,
            "extra": extra,
            "array": [],
        }.items():
            path = self.write_json(f"contract-{name}.json", document)
            for argv in (
                ["api-slo", "contract", "--contract", path],
                ["api-slo", "check", "--metrics-interval", "-", "--contract", path],
            ):
                with self.subTest(name, argv=argv[1]):
                    code, out, err = self.run_cli(
                        argv, json.dumps(_two_samples(HEALTHY)))
                    self.assertEqual((code, out), (2, ""))
                    self.assertIn("invalid SLO contract", err)
                    self.assertNotIn("SENTINEL", err)
        code, _, err = self.run_cli(
            ["api-slo", "contract", "--contract", str(self.dir / "nope.json")])
        self.assertEqual(code, 2)
        self.assertIn("not found", err)

    # -- file input and read-only behaviour -----------------------------

    def test_file_input_works_and_nothing_is_written(self):
        sandbox = Path(tempfile.mkdtemp(dir=self.dir))
        path = sandbox / "recording.json"
        path.write_text(json.dumps(_two_samples(HEALTHY)), encoding="utf-8")
        before = {p.name: p.read_bytes() for p in sandbox.iterdir()}
        code, out, err = self.run_cli(
            ["api-slo", "check", "--metrics-interval", str(path), "--json"])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out)["verdict"], "met")
        self.assertEqual(before, {p.name: p.read_bytes() for p in sandbox.iterdir()})


if __name__ == "__main__":
    unittest.main()
