"""Tests for tools/api_release_qualification.py (issue #745).

The tool's real run is the release gate; these tests drive it through an
injected runner so they spend no subprocess time, and pin the properties that
make the report trustworthy: a vanished suite fails the run, a skip is never
silently a pass under ``--strict``, and the set it runs matches the files on
disk.

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import api_release_qualification as aq

REPO_ROOT = Path(__file__).resolve().parents[1]


def _runner(failing=(), codes=None):
    calls = []

    def run(argv, cwd):
        calls.append(tuple(argv))
        joined = " ".join(argv)
        if any(name in joined for name in failing):
            return aq.Outcome(1, "1 failed, 3 passed in 0.1s\nFAILED boom")
        return aq.Outcome(0, "26 passed, 257 subtests passed in 1.2s")

    run.calls = calls
    return run


class CheckSetTests(unittest.TestCase):
    def test_every_listed_suite_exists_in_the_repository(self):
        for check in aq.build_checks("origin/main"):
            for path in check.requires:
                with self.subTest(check=check.id, path=path):
                    self.assertTrue((REPO_ROOT / path).exists(), path)

    def test_check_ids_are_unique_and_grouped(self):
        checks = aq.build_checks(None)
        ids = [check.id for check in checks]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            {check.group for check in checks},
            {"contract", "fuzz", "security", "reliability", "client", "install"},
        )

    def test_the_fuzz_and_security_slices_are_part_of_the_set(self):
        ids = {check.id for check in aq.build_checks(None)}
        self.assertIn("fuzz:api_qualification_fuzz", ids)
        self.assertIn("fuzz:api_header_boundary_fuzz", ids)
        self.assertIn("security:api_security_matrix", ids)
        self.assertIn("security:api_cors_csrf_matrix", ids)
        self.assertIn("reliability:load-soak", ids)
        self.assertIn("install:clean-install-demo", ids)

    def test_compat_gate_is_skipped_without_a_base(self):
        by_id = {c.id: c for c in aq.build_checks(None)}
        self.assertIsNotNone(by_id["schema-compat"].skip_reason)
        by_id = {c.id: c for c in aq.build_checks("v1.0.0")}
        self.assertIsNone(by_id["schema-compat"].skip_reason)
        self.assertEqual(by_id["schema-compat"].argv[-2:], ("--base", "v1.0.0"))


class QualifyTests(unittest.TestCase):
    def qualify(self, **kwargs):
        runner = kwargs.pop("runner", None) or _runner()
        return aq.qualify(REPO_ROOT, kwargs.pop("base", "origin/main"), runner=runner, **kwargs)

    def test_all_green_passes_and_records_counts(self):
        report = self.qualify()
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["totals"], {"passed": len(report["checks"])})
        first = report["checks"][0]
        self.assertEqual(first["exit_code"], 0)
        self.assertEqual(first["counts"]["passed"], 26)

    def test_one_failing_check_fails_the_run_and_keeps_its_output(self):
        report = self.qualify(runner=_runner(failing=("test_api_security_matrix",)))
        self.assertEqual(report["verdict"], "fail")
        failed = [c for c in report["checks"] if c["status"] == "failed"]
        self.assertEqual([c["id"] for c in failed], ["security:api_security_matrix"])
        self.assertIn("FAILED boom", failed[0]["output_tail"])
        self.assertEqual(failed[0]["counts"]["failed"], 1)

    def test_skip_passes_by_default_and_fails_under_strict(self):
        self.assertEqual(self.qualify(base=None)["verdict"], "pass")
        report = self.qualify(base=None, strict=True)
        self.assertEqual(report["verdict"], "fail")
        self.assertEqual(report["totals"]["skipped"], 1)

    def test_a_command_that_cannot_start_is_a_failure_not_a_pass(self):
        def cannot_start(argv, cwd):
            return aq.Outcome(None, "could not start: nope")

        report = self.qualify(runner=cannot_start)
        self.assertEqual(report["verdict"], "fail")
        self.assertTrue(all(c["status"] == "failed" for c in report["checks"]))

    def test_a_vanished_suite_fails_the_run_instead_of_shrinking_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools").mkdir()
            runner = _runner()
            report = aq.qualify(root, "origin/main", runner=runner)
        self.assertEqual(report["verdict"], "fail")
        self.assertTrue(all(c["status"] == "missing" for c in report["checks"]))
        self.assertEqual(runner.calls, [])

    def test_report_is_json_and_states_what_it_does_not_cover(self):
        report = self.qualify()
        json.dumps(report)
        self.assertEqual(report["schema"], aq.REPORT_SCHEMA)
        self.assertTrue(report["not_covered"])
        summary = aq.render_summary(report)
        self.assertIn("API release qualification: PASS", summary)
        self.assertIn("not covered", summary)


class CountParsingTests(unittest.TestCase):
    def test_pytest_summary_counts(self):
        self.assertEqual(
            aq._counts("1 failed, 2 passed, 1 skipped in 0.3s"),
            {"failed": 1, "passed": 2, "skipped": 1},
        )
        self.assertEqual(aq._counts("no summary"), {})


if __name__ == "__main__":
    unittest.main()
