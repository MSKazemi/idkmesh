"""Drift guard for ``docs/LOCAL_LOOP_TUTORIAL.md`` (refs #16).

The tutorial walks a newcomer through ``idkmesh local-loop``, then
``idkmesh local-loop-replay`` and ``idkmesh local-loop-record-decision``, and
quotes the output. Each claim is re-derived here
from the document itself, so a renamed config, a changed count, or a renamed
bundle file fails this test instead of misleading a reader:

* every ``idkmesh local-loop CONFIG`` path in the tutorial exists;
* every documented ``local-loop`` command is run in-process through
  ``idkmesh.cli.main`` and must exit 0, and the ``- Label: value`` summary lines
  printed in the tutorial must equal the live output;
* the documented bundle listing equals the real directory listing;
* the documented ``local-loop-replay`` and ``local-loop-record-decision``
  commands run in-process against the bundle the first command wrote: replay
  must print PASS and exit 0 without touching the bundle, and the decision
  must be bound to the report digest with every authority flag false;
* the next steps ``local-loop`` prints (and saves as ``NEXT_STEPS.md``) name
  those same two commands and the real bundle paths.

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
import unittest
import uuid
from pathlib import Path
from unittest import mock

from idkmesh.cli import main as cli_main
from idkmesh.local_loop import _load_experiments

_EXPERIMENTS = _load_experiments()
canonical_digest = _EXPERIMENTS["replay_run"].canonical_digest
_local_verifier = _EXPERIMENTS["local_verifier"]
_REAL_LOAD_SCHEMA = _local_verifier.load_schema
_SCHEMA_CACHE: dict[tuple[str, int, int], dict[str, object]] = {}


def _load_schema_checked_once(path: Path) -> dict[str, object]:
    """``local_verifier.load_schema`` that meta-validates each schema file once.

    ``load_schema`` re-runs ``Draft202012Validator.check_schema`` on every call
    and each verification loads three schemas, so most of this file's CPU was
    the same unchanged repository schemas being re-checked against the
    metaschema (cProfile). The first load of a given file state still goes
    through the real ``load_schema`` (parse + ``check_schema``); only repeat
    loads of an unchanged file reuse the result. Instance validation, which is
    what the documented commands exercise, still runs in full on every call.
    """
    stat = Path(path).stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[key] = _REAL_LOAD_SCHEMA(path)
    return _SCHEMA_CACHE[key]

REPO_ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = REPO_ROOT / "docs" / "LOCAL_LOOP_TUTORIAL.md"

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


def _documented_follow_up(verb: str) -> list[str]:
    """argv (after ``idkmesh``) of the single documented ``verb`` command."""
    found = [
        shlex.split(_joined_command(body))[1:]
        for lang, body in _blocks()
        if lang == "bash" and _joined_command(body).startswith(f"idkmesh {verb} ")
    ]
    assert len(found) == 1, f"tutorial must document exactly one `idkmesh {verb}` command"
    return found[0]


def _documented_ls_listing(output_dir: str) -> set[str]:
    blocks = _blocks()
    for index, (lang, body) in enumerate(blocks):
        if lang == "bash" and _joined_command(body) == f"ls {output_dir}":
            return set(blocks[index + 1][1].split())
    raise AssertionError(f"tutorial has no `ls {output_dir}` block")


class LocalLoopTutorialTests(unittest.TestCase):
    """Each documented ``local-loop`` command runs ONCE, in ``setUpClass``.

    The unit tier has a hard CPU budget and each loop costs real time, so the
    tests below assert on those shared runs instead of re-running the command.
    The bundle listing is captured immediately after each run, before the replay
    and decision test writes ``human-decision-record.json`` into run 0's bundle.
    The printed output is kept too, for the next-steps assertions.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.enterClassContext(
            mock.patch.object(_local_verifier, "load_schema", _load_schema_checked_once)
        )
        (REPO_ROOT / "results").mkdir(exist_ok=True)
        cls.scratch = REPO_ROOT / "results" / f"local-loop-tutorial-test-{uuid.uuid4().hex[:8]}"
        cls.scratch.mkdir()
        cls.addClassCleanup(shutil.rmtree, cls.scratch, ignore_errors=True)
        cls.loops: list[dict[str, object]] = []
        for number, run in enumerate(_documented_local_loop_runs()):
            target = (cls.scratch / f"run-{number}").relative_to(REPO_ROOT).as_posix()
            argv = list(run["argv"])  # type: ignore[arg-type]
            argv[argv.index("--output-dir") + 1] = target
            code, stdout = cls._run_cli(argv)
            listing = (
                {path.name for path in (REPO_ROOT / target).iterdir()}
                if (REPO_ROOT / target).is_dir()
                else set()
            )
            cls.loops.append(
                {"run": run, "target": target, "code": code, "stdout": stdout, "listing": listing}
            )

    @staticmethod
    def _run_cli_full(argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli_main(argv)
        return code, out.getvalue(), err.getvalue()

    @classmethod
    def _run_cli(cls, argv: list[str]) -> tuple[int, str]:
        code, out, _ = cls._run_cli_full(argv)
        return code, out

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
        self.assertEqual(len(self.loops), 2)
        for number, loop in enumerate(self.loops):
            run = loop["run"]
            with self.subTest(config=run["config"]):  # type: ignore[index]
                documented = dict(run["summary"])  # type: ignore[index, arg-type]
                self.assertEqual(
                    sorted(documented),
                    ["Control errors", "Inconclusive", "Rejected", "Supported", "Verification disagreement"],
                )
                self.assertEqual(loop["code"], 0, loop["stdout"])
                self.assertEqual(dict(SUMMARY_RE.findall(str(loop["stdout"]))), documented)
                if number == 0:
                    self.assertEqual(loop["listing"], _documented_ls_listing(str(run["output_dir"])))  # type: ignore[index]

    def test_failed_worker_documented_as_control_error_with_no_verification_file(self) -> None:
        loop = self.loops[1]
        self.assertEqual(loop["code"], 0)
        listing = loop["listing"]
        self.assertIn("verification-result-attempt-001.json", listing)  # type: ignore[operator]
        self.assertNotIn("verification-result-attempt-002.json", listing)  # type: ignore[operator]
        report = json.loads(
            (REPO_ROOT / str(loop["target"]) / "evidence-report.json").read_text(encoding="utf-8")
        )
        states = {item["attempt_id"]: item for item in report["attempts"]}
        self.assertIn("worker_error", json.dumps(states["attempt-002"]))
        self.assertIs(report["authority"]["merge"], False)

    def test_printed_next_steps_name_the_documented_commands(self) -> None:
        loop = self.loops[0]
        target = str(loop["target"])
        stdout = str(loop["stdout"])
        saved = (REPO_ROOT / target / "NEXT_STEPS.md").read_text(encoding="utf-8")
        self.assertEqual(saved, stdout)
        for text in (stdout, saved):
            self.assertIn(f"idkmesh local-loop-replay {target}/replay-source.json", text)
            self.assertIn(f"idkmesh local-loop-record-decision {target}/evidence-report.json", text)
            self.assertIn(f"--output {target}/human-decision-record.json", text)
            self.assertNotIn("python experiments/", text)

    def test_documented_replay_and_human_decision_run(self) -> None:
        loop = self.loops[0]
        self.assertEqual(loop["code"], 0)
        documented_dir = str(loop["run"]["output_dir"])  # type: ignore[index]
        target = str(loop["target"])
        bundle = REPO_ROOT / target

        def retarget(argv: list[str]) -> list[str]:
            return [arg.replace(documented_dir, target) for arg in argv]

        before = {path.name: path.read_bytes() for path in bundle.iterdir()}
        replay_code, replay_out, replay_err = self._run_cli_full(
            retarget(_documented_follow_up("local-loop-replay"))
        )
        self.assertEqual(replay_code, 0, replay_out + replay_err)
        self.assertIn("PASS: replay reproduced every must-match field", replay_out)
        self.assertEqual(
            {path.name: path.read_bytes() for path in bundle.iterdir()},
            before,
            "replay must not write into or alter the bundle",
        )

        record_code, record_out, record_err = self._run_cli_full(
            retarget(_documented_follow_up("local-loop-record-decision"))
        )
        self.assertEqual(record_code, 0, record_out + record_err)
        record = json.loads((bundle / "human-decision-record.json").read_text(encoding="utf-8"))
        self.assertEqual(record["decision"], "accept")
        self.assertEqual(record["selected_attempt_id"], "attempt-001")
        self.assertEqual(
            record["authority"],
            {"canonical_state_write": False, "git_push": False, "merge": False},
        )
        # Bound to the evidence report that was decided on, and that report is untouched.
        report = json.loads((bundle / "evidence-report.json").read_text(encoding="utf-8"))
        self.assertEqual(record["evidence_report"]["digest"], canonical_digest(report))
        self.assertIn(record["evidence_report"]["digest"], record_out)
        self.assertEqual((bundle / "evidence-report.json").read_bytes(), before["evidence-report.json"])

    def test_tutorial_states_its_limits(self) -> None:
        text = TUTORIAL.read_text(encoding="utf-8")
        for phrase in ("result-bundle", "issues/804", "experiments/replay_run.py", "still work"):
            self.assertIn(phrase, text)
        self.assertNotIn("not an `idkmesh` subcommand", text)
        self.assertNotIn("{{", text)


if __name__ == "__main__":
    unittest.main()
