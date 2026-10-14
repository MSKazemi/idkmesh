"""Drift guard for ``docs/LOCAL_LOOP_TUTORIAL.md`` (refs #16).

The tutorial walks a newcomer through ``idkmesh local-loop``, a replay and a
recorded human decision, and quotes the output. Each claim is re-derived here
from the document itself, so a renamed config, a changed count, or a renamed
bundle file fails this test instead of misleading a reader:

* every ``idkmesh local-loop CONFIG`` path in the tutorial exists;
* every documented ``local-loop`` command is run in-process through
  ``idkmesh.cli.main`` and must exit 0, and the ``- Label: value`` summary lines
  printed in the tutorial must equal the live output;
* the documented bundle listing equals the real directory listing;
* the documented ``replay_run.py replay`` and ``record_human_decision.py record``
  commands run against the bundle the first command wrote.

Class-based on purpose: ``tests/test_documented_test_counts.py`` counts
module-level ``test_*`` functions and this file must not shift them. Everything
runs in-process because a subprocess per command costs real CPU on the CI
runner. Standard library plus ``jsonschema`` only, which CI installs.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import shlex
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

from idkmesh.cli import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = REPO_ROOT / "docs" / "LOCAL_LOOP_TUTORIAL.md"
EXPERIMENTS = REPO_ROOT / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import record_human_decision  # noqa: E402
import replay_run  # noqa: E402

FENCE_RE = re.compile(r"^```(\w+)\n(.*?)^```$", re.DOTALL | re.MULTILINE)
SUMMARY_RE = re.compile(r"^- (Supported|Rejected|Inconclusive|Control errors|Verification disagreement): (.+)$", re.MULTILINE)


def _blocks() -> list[tuple[str, str]]:
    return [(lang, body) for lang, body in FENCE_RE.findall(TUTORIAL.read_text(encoding="utf-8"))]


def _joined_command(body: str) -> str:
    return " ".join(line.strip().rstrip("\\").strip() for line in body.splitlines()).strip()


def _documented_local_loop_runs() -> list[dict[str, object]]:
    """Each ``idkmesh local-loop`` command with the summary block that follows it."""
    blocks = _blocks()
    runs: list[dict[str, object]] = []
    for index, (lang, body) in enumerate(blocks):
        command = _joined_command(body)
        if lang != "bash" or not command.startswith("idkmesh local-loop "):
            continue
        argv = shlex.split(command)[1:]
        if "--help" in argv:
            continue
        output_dir = argv[argv.index("--output-dir") + 1]
        following = blocks[index + 1][1] if index + 1 < len(blocks) else ""
        runs.append(
            {
                "argv": argv,
                "config": argv[1],
                "output_dir": output_dir,
                "summary": dict(SUMMARY_RE.findall(following)),
            }
        )
    return runs


def _documented_ls_listing(output_dir: str) -> set[str]:
    blocks = _blocks()
    for index, (lang, body) in enumerate(blocks):
        if lang == "bash" and _joined_command(body) == f"ls {output_dir}":
            return set(blocks[index + 1][1].split())
    raise AssertionError(f"tutorial has no `ls {output_dir}` block")


class LocalLoopTutorialTests(unittest.TestCase):
    def setUp(self) -> None:
        (REPO_ROOT / "results").mkdir(exist_ok=True)
        self.scratch = REPO_ROOT / "results" / f"local-loop-tutorial-test-{uuid.uuid4().hex[:8]}"
        self.scratch.mkdir()
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)

    def _relocate(self, text: str, documented_dir: str, name: str) -> str:
        target = (self.scratch / name).relative_to(REPO_ROOT).as_posix()
        return text.replace(documented_dir, target)

    def _run_cli(self, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli_main(argv)
        return code, out.getvalue()

    def test_documented_configs_exist(self) -> None:
        runs = _documented_local_loop_runs()
        self.assertEqual(
            [run["config"] for run in runs],
            [
                "examples/orchestration/two-attempt-evaluator-plan-good-vs-bad.json",
                "examples/orchestration/two-attempt-worker-failure.json",
            ],
        )
        for run in runs:
            self.assertTrue((REPO_ROOT / str(run["config"])).is_file(), run["config"])
            self.assertTrue(str(run["output_dir"]).startswith("results/"), run["output_dir"])

    def test_documented_commands_produce_documented_counts(self) -> None:
        for number, run in enumerate(_documented_local_loop_runs()):
            with self.subTest(config=run["config"]):
                documented = dict(run["summary"])  # type: ignore[arg-type]
                self.assertEqual(
                    sorted(documented),
                    ["Control errors", "Inconclusive", "Rejected", "Supported", "Verification disagreement"],
                )
                target = (self.scratch / f"run-{number}").relative_to(REPO_ROOT).as_posix()
                argv = list(run["argv"])  # type: ignore[arg-type]
                argv[argv.index("--output-dir") + 1] = target

                code, stdout = self._run_cli(argv)

                self.assertEqual(code, 0, stdout)
                self.assertEqual(dict(SUMMARY_RE.findall(stdout)), documented)
                listing = {path.name for path in (REPO_ROOT / target).iterdir()}
                expected_bundle = _documented_ls_listing(str(run["output_dir"])) if number == 0 else None
                if expected_bundle is not None:
                    self.assertEqual(listing, expected_bundle)

    def test_failed_worker_documented_as_control_error_with_no_verification_file(self) -> None:
        run = _documented_local_loop_runs()[1]
        target = (self.scratch / "failure").relative_to(REPO_ROOT).as_posix()
        argv = list(run["argv"])  # type: ignore[arg-type]
        argv[argv.index("--output-dir") + 1] = target
        code, _ = self._run_cli(argv)
        self.assertEqual(code, 0)
        listing = {path.name for path in (REPO_ROOT / target).iterdir()}
        self.assertIn("verification-result-attempt-001.json", listing)
        self.assertNotIn("verification-result-attempt-002.json", listing)
        report = json.loads((REPO_ROOT / target / "evidence-report.json").read_text(encoding="utf-8"))
        states = {item["attempt_id"]: item for item in report["attempts"]}
        self.assertIn("worker_error", json.dumps(states["attempt-002"]))
        self.assertIs(report["authority"]["merge"], False)

    def test_documented_replay_and_human_decision_run(self) -> None:
        first = _documented_local_loop_runs()[0]
        documented_dir = str(first["output_dir"])
        target = (self.scratch / "bundle").relative_to(REPO_ROOT).as_posix()
        argv = list(first["argv"])  # type: ignore[arg-type]
        argv[argv.index("--output-dir") + 1] = target
        code, _ = self._run_cli(argv)
        self.assertEqual(code, 0)

        scripted = {}
        for lang, body in _blocks():
            command = _joined_command(body)
            if lang == "bash" and command.startswith("python experiments/replay_run.py replay"):
                scripted["replay"] = shlex.split(command)[2:]
            if lang == "bash" and command.startswith("python experiments/record_human_decision.py record"):
                scripted["record"] = shlex.split(command)[2:]
        self.assertEqual(sorted(scripted), ["record", "replay"])

        replay_argv = [self._relocate(arg, documented_dir, "bundle") for arg in scripted["replay"]]
        out = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["replay_run.py", *replay_argv]),
            contextlib.redirect_stdout(out),
        ):
            replay_code = replay_run.main()
        self.assertEqual(replay_code, 0, out.getvalue())
        self.assertIn("PASS: replay reproduced every must-match field", out.getvalue())

        record_argv = [self._relocate(arg, documented_dir, "bundle") for arg in scripted["record"]]
        out = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["record_human_decision.py", *record_argv]),
            contextlib.redirect_stdout(out),
        ):
            record_code = record_human_decision.main()
        self.assertEqual(record_code, 0, out.getvalue())
        record = json.loads(
            (REPO_ROOT / target / "human-decision-record.json").read_text(encoding="utf-8")
        )
        self.assertEqual(record["decision"], "accept")
        self.assertEqual(record["selected_attempt_id"], "attempt-001")
        self.assertEqual(
            record["authority"],
            {"canonical_state_write": False, "git_push": False, "merge": False},
        )

    def test_tutorial_states_its_limits(self) -> None:
        text = TUTORIAL.read_text(encoding="utf-8")
        for phrase in ("result-bundle", "issues/804", "not an `idkmesh` subcommand"):
            self.assertIn(phrase, text)
        self.assertNotIn("{{", text)


if __name__ == "__main__":
    unittest.main()
