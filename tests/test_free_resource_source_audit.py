import datetime as dt
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "free_resource_source_audit", ROOT / "scripts" / "free_resource_source_audit.py"
)
audit_tool = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(audit_tool)

REGISTRY_PATH = ROOT / "examples/resources/free-resource-registry-v0.1.json"


def synthetic_registry(offers):
    return {"version": 1, "observed_at": "2026-01-01", "offers": offers}


def offer(oid, checked_at, max_age_days, url="https://example.invalid/doc"):
    return {
        "id": oid,
        "status": "available",
        "source": {"url": url, "checked_at": checked_at, "max_age_days": max_age_days},
    }


class ClassifyTests(unittest.TestCase):
    def test_window_boundaries(self):
        # The last day inside the window is not yet stale; one day past it is.
        self.assertEqual(audit_tool.classify(29, 30, 7), audit_tool.EXPIRING)
        self.assertEqual(audit_tool.classify(30, 30, 7), audit_tool.EXPIRING)
        self.assertEqual(audit_tool.classify(31, 30, 7), audit_tool.STALE)

    def test_warn_days_zero_never_reports_expiring_before_the_last_day(self):
        self.assertEqual(audit_tool.classify(29, 30, 0), audit_tool.FRESH)
        self.assertEqual(audit_tool.classify(30, 30, 0), audit_tool.EXPIRING)

    def test_fresh_offer_far_from_expiry(self):
        self.assertEqual(audit_tool.classify(0, 30, 7), audit_tool.FRESH)


class AuditTests(unittest.TestCase):
    def test_counts_and_ordering(self):
        registry = synthetic_registry(
            [
                offer("b-fresh", "2026-01-01", 90),
                offer("a-stale", "2026-01-01", 10),
                offer("c-expiring", "2026-01-01", 35),
            ]
        )
        report = audit_tool.audit(registry, as_of=dt.date(2026, 2, 1), warn_days=7)
        self.assertEqual(report["counts"], {"fresh": 1, "expiring": 1, "stale": 1})
        # Stalest first, so the most urgent finding is at the top of the report.
        self.assertEqual([o["id"] for o in report["offers"]], ["a-stale", "c-expiring", "b-fresh"])

    def test_expiry_arithmetic_is_exact(self):
        registry = synthetic_registry([offer("x", "2026-08-28", 14)])
        report = audit_tool.audit(registry, as_of=dt.date(2026, 9, 4), warn_days=7)
        record = report["offers"][0]
        self.assertEqual(record["age_days"], 7)
        self.assertEqual(record["days_until_evidence_stale"], 7)
        self.assertEqual(record["evidence_stale_on"], "2026-09-11")

    def test_audit_never_probes_the_network_by_default(self):
        registry = synthetic_registry([offer("x", "2026-01-01", 30)])

        def explode(*args, **kwargs):
            raise AssertionError("audit must not touch the network unless --check-sources is given")

        original = audit_tool.urllib.request.urlopen
        audit_tool.urllib.request.urlopen = explode
        try:
            report = audit_tool.audit(registry, as_of=dt.date(2026, 1, 2), warn_days=7)
        finally:
            audit_tool.urllib.request.urlopen = original
        self.assertFalse(report["sources_checked"])
        self.assertEqual(report["offers"][0]["liveness"], audit_tool.UNCHECKED)

    def test_probe_failure_is_a_finding_not_an_exception(self):
        # An unreachable source must be recorded, never raised: the audit has to
        # finish and report every offer even when one citation is dead.
        result = audit_tool.probe_source("https://example.invalid/definitely-not-there", timeout=0.01)
        self.assertEqual(result["liveness"], audit_tool.UNREACHABLE)
        self.assertIsNotNone(result["error"])


class RealRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_every_offer_is_auditable(self):
        # Guards the coupling: an offer added without source metadata would make
        # the audit blind to it rather than fail loudly.
        report = audit_tool.audit(self.registry, as_of=dt.date(2026, 9, 4), warn_days=7)
        self.assertEqual(report["offer_count"], len(self.registry["offers"]))
        self.assertEqual(
            {o["id"] for o in report["offers"]},
            {o["id"] for o in self.registry["offers"]},
        )

    def test_registry_is_not_stale_at_its_own_observation_date(self):
        # On the day it was observed, nothing in the registry may already be expired.
        observed = dt.date.fromisoformat(self.registry["observed_at"])
        report = audit_tool.audit(self.registry, as_of=observed, warn_days=7)
        self.assertEqual(report["counts"]["stale"], 0, report["offers"])


class ExitCodeTests(unittest.TestCase):
    """The exit code is what a scheduled audit is actually gated on."""

    def run_cli(self, *args):
        import subprocess
        import sys

        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "free_resource_source_audit.py"), *args],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

    def test_stale_offer_fails_by_default(self):
        result = self.run_cli("--as-of", "2027-01-01", "--format", "text")
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_fail_on_never_reports_without_failing(self):
        result = self.run_cli("--as-of", "2027-01-01", "--format", "text", "--fail-on", "never")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("STALE", result.stdout)

    def test_expiring_does_not_fail_under_default_policy(self):
        # 2026-09-04 has two offers inside the 7-day warning window and none stale.
        result = self.run_cli("--as-of", "2026-09-04", "--format", "text")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("WARN", result.stdout)

    def test_expiring_fails_when_explicitly_requested(self):
        result = self.run_cli("--as-of", "2026-09-04", "--format", "text", "--fail-on", "expiring")
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_unreachable_does_not_fail_unless_opted_in(self):
        # No --check-sources, so nothing is probed and the flag cannot trip.
        result = self.run_cli("--as-of", "2026-09-04", "--fail-on-unreachable", "--format", "text")
        self.assertEqual(result.returncode, 0, result.stdout)


class SelfTestTests(unittest.TestCase):
    def test_self_test_passes(self):
        self.assertEqual(audit_tool._self_test(), 0)



class FieldNamingTests(unittest.TestCase):
    """A per-offer date field must say whose clock it is on.

    ``evidence_stale_on`` is ``checked_at + max_age_days`` -- the day our own
    recorded reading of the offer's terms ages out. It says nothing about the
    provider. The earlier name, ``expires_on``, was read as a provider deadline
    within an hour of shipping: a reviewer reported it as a free-tier credential
    lapsing the next day, which would have been a false statement about a third
    party. This registry holds no expiry date for any offer.
    """

    def _offer_records(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        report = audit_tool.audit(registry, as_of=dt.date(2026, 9, 4), warn_days=7)
        self.assertTrue(report["offers"], "no offers; this guard would be vacuous")
        return report["offers"]

    def test_offer_records_carry_the_evidence_named_fields(self) -> None:
        for record in self._offer_records():
            self.assertIn("evidence_stale_on", record)
            self.assertIn("days_until_evidence_stale", record)

    def test_no_offer_field_claims_the_offer_itself_expires(self) -> None:
        offending = sorted(
            {key for record in self._offer_records() for key in record if "expir" in key}
        )

        self.assertEqual(
            offending,
            [],
            "these per-offer keys read as a claim about the provider, but hold "
            f"arithmetic over our own checked_at: {offending}",
        )


class WorkflowSurfacingTests(unittest.TestCase):
    """The warning window must be visible without opening a green run's log.

    ``--fail-on stale`` turns the run red only once evidence has ALREADY aged
    out. The state this audit exists to catch -- evidence about to age out -- is
    reported on a run that is green, and nobody reads the log of a green run. So
    the freshness report is written to the job summary, where it shows on the run
    page itself.
    """

    WORKFLOW = ROOT / ".github/workflows/free-resource-source-audit.yml"

    def _freshness_step(self) -> str:
        text = self.WORKFLOW.read_text(encoding="utf-8")
        start = text.index("name: Report registry freshness")
        end = text.find("\n      - name:", start)
        return text[start : end if end != -1 else len(text)]

    def test_the_freshness_report_reaches_the_job_summary(self) -> None:
        self.assertIn("GITHUB_STEP_SUMMARY", self._freshness_step())

    def test_a_failing_audit_still_re_raises_its_status(self) -> None:
        """Capturing stdout must not swallow the red build.

        The tool prints its whole report and *then* exits non-zero, so the step
        captures first and re-raises afterwards. Losing the re-raise would make
        a stale registry report itself green.
        """
        step = self._freshness_step()

        self.assertIn("--fail-on stale", step)
        self.assertIn('exit "$status"', step)

if __name__ == "__main__":
    unittest.main()
