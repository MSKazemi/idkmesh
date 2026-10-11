"""Tests for tools/api_clean_install_demo.py (issue #747).

The real run builds a wheel and a virtual environment, so it is a release-time
check (``make qualify-api``), not a unit test. These tests cover what can be
verified cheaply and exactly: what gets staged, how the server announcement is
parsed, how steps map to a verdict and exit code, and that the demo script
prints only stable fields.

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import api_clean_install_demo as demo

REPO_ROOT = Path(__file__).resolve().parents[1]


class StagingTests(unittest.TestCase):
    def test_only_the_installable_files_are_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "src"
            demo.stage_source(REPO_ROOT, target)
            names = {p.name for p in target.iterdir()}
            self.assertEqual(names, {"pyproject.toml", "README.md", "LICENSE", "idkmesh"})
            self.assertTrue((target / "idkmesh" / "api_client.py").exists())
            self.assertFalse(list(target.rglob("__pycache__")))

    def test_staging_leaves_the_working_tree_untouched(self):
        before = sorted(p.name for p in REPO_ROOT.iterdir())
        with tempfile.TemporaryDirectory() as tmp:
            demo.stage_source(REPO_ROOT, Path(tmp) / "src")
        self.assertEqual(sorted(p.name for p in REPO_ROOT.iterdir()), before)


class AnnouncementTests(unittest.TestCase):
    def test_the_server_url_line_is_parsed(self):
        match = demo.URL_PATTERN.search("IDKMesh Control Tower: http://127.0.0.1:43257/\n")
        self.assertEqual(match.group(1), "43257")
        self.assertIsNone(demo.URL_PATTERN.search("IDKMesh Control Tower: http://example.com:80/"))

    def test_free_port_is_a_usable_loopback_port(self):
        self.assertGreater(demo.free_port(), 0)


class DemoScriptTests(unittest.TestCase):
    def test_the_transcript_carries_only_stable_fields(self):
        # Request ids and timestamps would make transcripts differ run to run.
        for forbidden in ("\"request_id\"", "timestamp", "uptime", "\"pid\""):
            self.assertNotIn(forbidden, demo.DEMO_SCRIPT)
        self.assertIn("snapshot_digest", demo.DEMO_SCRIPT)
        self.assertIn("json.loads(SAMPLE_REPORT)", demo.DEMO_SCRIPT)

    def test_the_demo_script_compiles(self):
        compile(demo.DEMO_SCRIPT, "<demo>", "exec")


class VerdictTests(unittest.TestCase):
    def run_main(self, verdict):
        report = {"schema": demo.REPORT_SCHEMA, "steps": [], "verdict": verdict}
        buffer = io.StringIO()
        with mock.patch.object(demo, "demo", return_value=report), \
                contextlib.redirect_stdout(buffer):
            return demo.main([]), buffer.getvalue()

    def test_exit_codes_distinguish_failure_from_an_unusable_environment(self):
        self.assertEqual(self.run_main("pass")[0], 0)
        self.assertEqual(self.run_main("fail")[0], 1)
        self.assertEqual(self.run_main("could-not-run")[0], 2)

    def test_render_lists_every_step(self):
        report = {
            "verdict": "pass",
            "steps": [{"step": "wheel-builds", "status": "passed", "detail": "x.whl"}],
        }
        text = demo.render(report)
        self.assertIn("API clean-install demo: PASS", text)
        self.assertIn("wheel-builds", text)

    def test_a_non_repository_root_exits_2(self):
        self.assertEqual(demo.main(["--root", "/nonexistent-root"]), 2)

    def test_an_unbuildable_environment_is_not_reported_as_a_package_failure(self):
        with mock.patch.object(demo, "_run", side_effect=demo.EnvironmentUnavailable("no network")):
            report = demo.demo(REPO_ROOT)
        self.assertEqual(report["verdict"], "could-not-run")
        self.assertIn("no network", report["error"])

    def test_a_step_failure_is_a_failure(self):
        with mock.patch.object(demo, "_run", side_effect=demo.StepFailed("nope")):
            report = demo.demo(REPO_ROOT)
        # StepFailed raised from inside _run is not an environment problem.
        self.assertEqual(report["verdict"], "fail")


if __name__ == "__main__":
    unittest.main()
