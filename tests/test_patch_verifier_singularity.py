"""There is exactly one patch verifier per backend, and CI names the real one.

``experiments/evaluator_plan_runner.py`` is the only dispatcher: it imports a
patch verifier module and calls it for a named backend. A verifier module the
runner does not import therefore participates in no verification at all.

That is not hypothetical. ``experiments/transformation_patch_verifier.py`` was
the pre-#171 spelling of the v0.4 verifier. #171 replaced it with
``transition_patch_verifier.py`` and rewired the runner, but a later "extract
additive artifacts" commit restored the superseded file. Nothing imported it and
no test covered it, so nothing went red -- while
``evaluator-transformation-calibration.yml`` went on running ``py_compile`` over
it under the step name "Compile calibrated evaluator path". The compile proved
the orphan still parsed; the calibration it then ran went through the runner to
``transition_patch_verifier``. The workflow's own evidence named a module that
took no part in the result.

Two invariants close that gap:

1. every ``experiments/*_patch_verifier.py`` is imported by the runner; and
2. every workflow reference to such a module names one that exists and is
   dispatched -- unless the line is asserting the module's *absence*, which is
   how ``task001-v04-canonical-calibration.yml`` pins the #171 rename.

Invariant 2 is what a stale ``paths:`` trigger breaks silently: before this
test, editing ``transition_patch_verifier.py`` did not trigger the transformation
calibration workflow, because the workflow still watched the orphan's path.
"""

from __future__ import annotations

import ast
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
WORKFLOWS = ROOT / ".github" / "workflows"
RUNNER = EXPERIMENTS / "evaluator_plan_runner.py"

# ``experiments/<stem>.py`` as written inside a workflow, in a ``paths:`` entry
# or on a ``py_compile`` continuation line alike.
REFERENCE_RE = re.compile(r"experiments/(?P<stem>[a-z0-9_]+_patch_verifier)\.py")


def _runner_imports():
    """Return every module name ``evaluator_plan_runner`` imports.

    Parsed rather than grepped so a name inside a docstring or a comment cannot
    make an orphan look dispatched.
    """

    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def _workflow_references():
    """Yield ``(path, line_number, stem, asserts_absence)`` for each reference."""

    paths = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    for path in paths:
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if line.strip().startswith("#"):
                continue
            match = REFERENCE_RE.search(line)
            if match is None:
                continue
            # ``test ! -f <path>`` pins a module that must stay deleted.
            asserts_absence = "! -f" in line
            yield path, number, match.group("stem"), asserts_absence


class PatchVerifierSingularityTest(unittest.TestCase):
    def test_there_is_something_to_check(self):
        """Guard against every assertion below passing vacuously."""

        self.assertTrue(RUNNER.is_file(), f"{RUNNER} is missing")
        modules = list(EXPERIMENTS.glob("*_patch_verifier.py"))
        self.assertGreater(len(modules), 0, "no patch verifier modules were found")
        references = list(_workflow_references())
        self.assertGreater(
            len(references),
            0,
            "no workflow references were parsed; the regex is probably broken",
        )
        self.assertTrue(
            any(absent for *_, absent in references),
            "no absence assertion was parsed; the '! -f' branch is untested",
        )

    def test_every_patch_verifier_module_is_dispatched(self):
        imported = _runner_imports()
        orphans = [
            path.name
            for path in sorted(EXPERIMENTS.glob("*_patch_verifier.py"))
            if path.stem not in imported
        ]
        self.assertEqual(
            orphans,
            [],
            "these patch verifiers are imported by no dispatcher, so they verify "
            f"nothing and must not exist: {orphans}. {RUNNER.name} imports "
            f"{sorted(name for name in imported if name.endswith('_patch_verifier'))}.",
        )

    def test_workflows_only_name_dispatched_verifiers(self):
        imported = _runner_imports()
        problems = []
        for path, number, stem, asserts_absence in _workflow_references():
            exists = (EXPERIMENTS / f"{stem}.py").is_file()
            if asserts_absence:
                if exists:
                    problems.append(
                        f"{path.name}:{number} asserts {stem}.py is gone, but it exists"
                    )
                continue
            if not exists:
                problems.append(f"{path.name}:{number} names {stem}.py, which is missing")
            elif stem not in imported:
                problems.append(
                    f"{path.name}:{number} names {stem}.py, which no dispatcher imports"
                )
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
