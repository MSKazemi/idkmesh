"""Tests for the E9 in-process enterprise conformance harness (#676)."""

from __future__ import annotations

import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import unittest
from unittest import mock

from idkmesh import cli
from idkmesh import enterprise_conformance as conformance
from idkmesh.enterprise_audit import AuditVerification
from idkmesh.enterprise_authz import AuthorizationDecision

ROOT = Path(__file__).resolve().parents[1]

EXERCISED = (
    "unauthorized_actor",
    "cross_tenant_reference",
    "duplicate_event",
    "coordinator_crash_after_dispatch",
    "provider_outage_quota",
    "secret_missing_or_revoked",
    "audit_exporter_unavailable",
    "ledger_restore",
    "stale_identity_policy_cache",
    "high_risk_sod_violation",
)
NOT_EXERCISED = ("stale_claim_retry", "release_provenance")


def _by_id(report: dict) -> dict[str, dict]:
    return {item["id"]: item for item in report["scenarios"]}


def _allow_everything(request, policy):  # stand-in for a broken authorization kernel
    return AuthorizationDecision(
        effect="allow",
        code="authorized",
        message="broken kernel",
        request_id=request.request_id,
        principal_id=request.actor.principal_id,
        action=request.action,
        tenant_id=request.scope.tenant_id,
        project_id=request.scope.project_id,
        resource_type=request.resource.resource_type,
        resource_id=request.resource.resource_id,
        requested_risk=request.risk,
        effective_risk=request.risk,
        data_classification=request.data_classification,
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        identity_revision=request.actor.identity_revision,
        evaluated_at_epoch=request.evaluated_at_epoch,
    )


class ConformanceReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = conformance.run_conformance()
        cls.scenarios = _by_id(cls.report)

    def test_report_shape_and_disclaimer(self) -> None:
        self.assertEqual(self.report["kind"], conformance.REPORT_KIND)
        self.assertEqual(self.report["certification_claim"], "none")
        self.assertIn("not a SOC 2", self.report["disclaimer"])
        self.assertEqual(
            sum(self.report["counts"].values()), len(self.report["scenarios"])
        )
        self.assertEqual(tuple(self.report["counts"]), conformance.STATUSES)

    def test_every_issue_scenario_is_listed(self) -> None:
        self.assertEqual(
            set(self.scenarios), set(EXERCISED) | set(NOT_EXERCISED)
        )

    def test_exercised_scenarios_hold_their_safe_state(self) -> None:
        for scenario_id in EXERCISED:
            with self.subTest(scenario=scenario_id):
                item = self.scenarios[scenario_id]
                self.assertIn(item["status"], {"PASS", "WARN"}, item["observed"])
                self.assertTrue(item["checks"])
                self.assertTrue(all(check["ok"] for check in item["checks"]))

    def test_warn_scenarios_name_their_gap_and_pass_names_none(self) -> None:
        for item in self.report["scenarios"]:
            with self.subTest(scenario=item["id"]):
                if item["status"] == "WARN":
                    self.assertTrue(item["gaps"])
                if item["status"] == "PASS":
                    self.assertEqual(item["gaps"], [])

    def test_unexercised_scenarios_are_unknown_never_pass(self) -> None:
        for scenario_id in NOT_EXERCISED:
            with self.subTest(scenario=scenario_id):
                item = self.scenarios[scenario_id]
                self.assertEqual(item["status"], "UNKNOWN")
                self.assertEqual(item["checks"], [])
                self.assertTrue(item["observed"].startswith("not exercised:"))

    def test_overall_status_is_not_pass_while_scenarios_are_unknown(self) -> None:
        self.assertEqual(self.report["status"], "UNKNOWN")

    def test_report_is_deterministic(self) -> None:
        self.assertEqual(conformance.run_conformance(), self.report)

    def test_evidence_links_resolve_to_tracked_files(self) -> None:
        for item in self.report["scenarios"]:
            for rel in item["evidence"]:
                with self.subTest(scenario=item["id"], path=rel):
                    self.assertTrue((ROOT / rel).is_file())

    def test_report_never_contains_the_fixture_secret(self) -> None:
        self.assertNotIn(conformance._SECRET, json.dumps(self.report))

    def test_overall_status_ordering(self) -> None:
        order = conformance.overall_status
        self.assertEqual(order(["PASS", "WARN"]), "WARN")
        self.assertEqual(order(["WARN", "UNKNOWN"]), "UNKNOWN")
        self.assertEqual(order(["UNKNOWN", "FAIL", "PASS"]), "FAIL")
        self.assertEqual(order(["PASS"]), "PASS")

    def test_unknown_scenario_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            conformance.run_conformance(scenario_ids=("nope",))

    def test_scenarios_can_be_selected_and_use_a_caller_workdir(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report = conformance.run_conformance(
                scenario_ids=("duplicate_event",), workdir=tmp
            )
            self.assertEqual([s["id"] for s in report["scenarios"]], ["duplicate_event"])
            self.assertTrue((Path(tmp) / "duplicate_event" / "runs.sqlite3").is_file())


class ConformanceDetectsBrokenControlsTests(unittest.TestCase):
    """Negative controls: the harness must turn red when a control is broken."""

    def _run(self, *ids: str) -> dict[str, dict]:
        return _by_id(conformance.run_conformance(scenario_ids=ids))

    def test_allow_everything_kernel_fails_authorization_scenarios(self) -> None:
        with mock.patch.object(conformance, "authorize", _allow_everything):
            result = self._run(
                "unauthorized_actor",
                "high_risk_sod_violation",
                "stale_identity_policy_cache",
            )
        for scenario_id, item in result.items():
            with self.subTest(scenario=scenario_id):
                self.assertEqual(item["status"], "FAIL", item["observed"])

    def test_scope_blind_store_fails_cross_tenant_scenario(self) -> None:
        with mock.patch.object(
            conformance, "TenantIsolationError", type("Never", (Exception,), {})
        ):
            result = self._run("cross_tenant_reference")
        self.assertEqual(result["cross_tenant_reference"]["status"], "FAIL")

    def test_ledger_that_never_detects_tampering_fails_restore_scenario(self) -> None:
        def always_ok(self_, *, expected_checkpoint=None):
            return AuditVerification(True, 0, 0, None, ())

        with mock.patch.object(
            conformance.LocalEnterpriseAuditLedger, "verify", always_ok
        ):
            result = self._run("ledger_restore")
        self.assertEqual(result["ledger_restore"]["status"], "FAIL")

    def test_secret_leaking_wrapper_fails_secret_scenario(self) -> None:
        real = conformance.materialize_config_secret

        class Leaky:
            def __init__(self, value: str) -> None:
                self._value = value

            def __repr__(self) -> str:
                return self._value

        def leaky(config, grant, *, environ=None):
            return Leaky(real(config, grant, environ=environ).reveal_for_provider())

        with mock.patch.object(conformance, "materialize_config_secret", leaky):
            result = self._run("secret_missing_or_revoked")
        self.assertEqual(result["secret_missing_or_revoked"]["status"], "FAIL")

    def test_crashing_scenario_is_reported_as_fail(self) -> None:
        def boom(ctx):
            raise RuntimeError("boom")

        broken = conformance.Scenario("boom", "Boom", "never", (), boom)
        with mock.patch.object(conformance, "SCENARIOS", (broken,)):
            report = conformance.run_conformance()
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("RuntimeError", report["scenarios"][0]["observed"])


class ConformanceProviderFaultTests(unittest.TestCase):
    """Failure injection must catch a fail-open probe/router or leaky envelope."""

    def _scenario(self) -> dict:
        report = conformance.run_conformance(scenario_ids=("provider_outage_quota",))
        return _by_id(report)["provider_outage_quota"]

    def test_injected_faults_are_warn_not_full_provider_qualification(self) -> None:
        item = self._scenario()
        self.assertEqual(item["status"], "WARN", item["observed"])
        self.assertGreaterEqual(len(item["checks"]), 20)
        self.assertTrue(all(check["ok"] for check in item["checks"]))
        self.assertEqual(len(item["gaps"]), 1)
        self.assertIn("no actual provider attempt", item["gaps"][0])
        self.assertNotIn(conformance._SECRET, json.dumps(item))
        self.assertEqual(item, self._scenario())

    def test_lying_probe_healthy_causes_failure(self) -> None:
        actual = conformance.probe_connector

        def unsafe_probe(config, registry, **kwargs):
            result = actual(config, registry, **kwargs)
            if result.status == "unavailable":
                return replace(result, status="healthy", failure=None)
            return result

        with mock.patch.object(conformance, "probe_connector", side_effect=unsafe_probe):
            result = self._scenario()
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(not check["ok"] for check in result["checks"]))

    def test_router_admitting_unavailable_connector_causes_failure(self) -> None:
        actual = conformance.explain_route

        def unsafe_route(*args, **kwargs):
            result = actual(*args, **kwargs)
            if result["ineligible"]:
                return {**result, "selected_connection_id": "provider-fault-fixture"}
            return result

        with mock.patch.object(conformance, "explain_route", side_effect=unsafe_route):
            result = self._scenario()
        self.assertEqual(result["status"], "FAIL")

    def test_error_envelope_leaking_credentials_causes_failure(self) -> None:
        actual = conformance.connector_error

        class LeakyEnvelope:
            def __init__(self, safe) -> None:
                self.safe = safe

            def to_envelope(self):
                envelope = self.safe.to_envelope()
                envelope["error"]["details"]["Authorization"] = conformance._SECRET
                return envelope

            def __str__(self):
                return str(self.safe)

        def leaky_error(*args, **kwargs):
            return LeakyEnvelope(actual(*args, **kwargs))

        with mock.patch.object(conformance, "connector_error", side_effect=leaky_error):
            result = self._scenario()
        self.assertEqual(result["status"], "FAIL")
        self.assertNotIn(conformance._SECRET, json.dumps(result))


class DoctorEnterpriseConformanceCliTests(unittest.TestCase):
    def _main(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["doctor", *argv])
        return code, out.getvalue(), err.getvalue()

    def test_json_output_matches_the_library_report(self) -> None:
        code, out, _ = self._main("--enterprise-conformance", "--json")
        payload = json.loads(out)
        self.assertEqual(payload, conformance.run_conformance())
        self.assertEqual(code, 1)  # UNKNOWN scenarios keep the pilot from passing

    def test_text_output_lists_every_scenario_and_the_disclaimer(self) -> None:
        code, out, _ = self._main("--enterprise-conformance")
        self.assertEqual(code, 1)
        self.assertIn("enterprise conformance: UNKNOWN", out)
        for item in conformance.SCENARIOS:
            self.assertIn(f"- {item.scenario_id}: ", out)
        self.assertIn("not a SOC 2", out)

    def test_exit_zero_when_nothing_fails_or_is_unknown(self) -> None:
        passing = {
            "kind": conformance.REPORT_KIND,
            "status": "WARN",
            "scenarios": [],
            "disclaimer": conformance.DISCLAIMER,
        }
        with mock.patch.object(conformance, "run_conformance", return_value=passing):
            code, _, _ = self._main("--enterprise-conformance")
        self.assertEqual(code, 0)

    def test_flag_cannot_be_combined_with_other_doctor_modes(self) -> None:
        for extra in (
            ("some-profile.json",),
            ("--github", "obs.json"),
            ("--operation", "integration"),
            ("--checked-at", "2026-01-01T00:00:00Z"),
        ):
            with self.subTest(extra=extra):
                code, out, _ = self._main("--enterprise-conformance", *extra)
                self.assertNotEqual(code, 0)
                self.assertNotIn("enterprise conformance:", out)

    def test_help_documents_the_flag(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            cli.main(["doctor", "--help"])
        self.assertIn("--enterprise-conformance", out.getvalue())


if __name__ == "__main__":
    unittest.main()
