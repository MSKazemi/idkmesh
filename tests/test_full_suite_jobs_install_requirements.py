"""A job that runs the whole test tree must install what the tree needs.

Tests in this repository guard their own imports: a module needing `jsonschema`
calls ``unittest.skipUnless`` rather than erroring at collection, because several
narrow workflows deliberately run on a bare interpreter. That is the right shape
for a focused job, and the wrong shape for a job that discovers everything --
there, a missing dependency turns into a *silent* reduction in coverage.

``randomness-lab.yml`` was exactly that. It triggers on ``tests/**``, runs
``python -m unittest discover -s tests -v`` across all of ``tests/``, and
installed nothing. Run 33829428765 reported a green ``test`` check on three
Python versions over 1451 tests -- and 72 of its 74 skips read "requires
jsonschema" or "requires requirements-phase0.txt": schema validation, ACE
lineage contracts, example contract coverage, Phase B2 evidence and the patch
evaluator safety tests. None of them ran. Nothing said so louder than a skip dot.

The rule is therefore about scope, not about any one workflow: a step that
discovers the whole tree may not run in a job with no dependency install. A job
that names a pattern (``-p 'test_thing.py'``) is free to stay bare -- that is a
deliberate stdlib-only check, and this test does not touch it.

"Installs the dependency" is not enough on its own, because the tree's needs
grow. An earlier form of this guard accepted any ``pip install`` naming
``requirements`` or ``jsonschema``; under it, ``randomness-lab`` could install
``requirements-phase0.txt`` -- which is only ``jsonschema`` -- and still skip
every test guarded on ``pytest``, silently, while the guard stayed green. So the
requirement is derived from the tree instead of hard-coded: whatever modules
``tests/`` guards with ``find_spec`` are what a whole-tree job must install, and
``-r`` is followed into the requirements file to see what it actually provides.
Add a new optional dependency to the tree and this guard names the jobs that
must now install it.

Names are compared as written: this assumes a module's import name matches its
distribution name, which holds for ``jsonschema`` and ``pytest``. A dependency
whose names differ needs an entry in ``DISTRIBUTION_ALIASES``.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# A job begins at six-space indentation under `jobs:`; steps are deeper.
JOB_RE = re.compile(r"^  (?P<name>[A-Za-z0-9_-]+):\s*$")
DISCOVER_RE = re.compile(r"unittest\s+discover\s+-s\s+tests(?!\S)")
PATTERN_RE = re.compile(r"\s-p\s")
PYTEST_RE = re.compile(r"(?<![-\w])pytest(?!\S)")
# Import name -> distribution name, for the cases where they differ.
DISTRIBUTION_ALIASES = {}
PIP_INSTALL_RE = re.compile(r"pip\s+install\s+(?P<args>.*)$")
# Strip a version specifier, extra, or environment marker from `pkg[x]>=1,<2 ; y`.
DIST_RE = re.compile(r"^[A-Za-z0-9._-]+")


def _runs_whole_tree(line):
    """True when `line` runs every test, rather than a named subset."""

    # `pip install pytest jsonschema` names pytest without running it.
    if "pip install" in line:
        return False
    if DISCOVER_RE.search(line) and not PATTERN_RE.search(line):
        return True
    match = PYTEST_RE.search(line)
    if match is None:
        return False
    # `pytest tests/test_one.py` names its subset; bare `pytest -q` does not.
    rest = line[match.end() :]
    return not any(
        token.endswith(".py") or "/" in token for token in rest.split()
    )


def _jobs(text):
    """Yield ``(job_name, body)`` for each job in one workflow's text.

    Split textually: the PR Gate installs ``jsonschema`` and nothing else, so a
    guard that imported PyYAML would fail collection for the whole file.
    """

    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.rstrip() == "jobs:")
    except StopIteration:
        return
    current, body = None, []
    for line in lines[start + 1 :]:
        match = JOB_RE.match(line)
        if match:
            if current is not None:
                yield current, "\n".join(body)
            current, body = match.group("name"), []
        elif current is not None:
            body.append(line)
    if current is not None:
        yield current, "\n".join(body)


def _whole_tree_jobs():
    """Yield ``(path, job_name, body)`` for jobs running the undivided tree."""

    paths = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    for path in paths:
        for name, body in _jobs(path.read_text(encoding="utf-8")):
            runs_everything = any(
                _runs_whole_tree(line)
                for line in body.splitlines()
                if not line.strip().startswith("#")
            )
            if runs_everything:
                yield path, name, body


def _requirements_distributions(spec):
    """Return the distribution names a ``-r <spec>`` file provides."""

    path = ROOT / spec
    if not path.is_file():
        return set()
    names = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = DIST_RE.match(line)
        if match:
            names.add(match.group(0).lower())
    return names


def _installed_distributions(body):
    """Every distribution a job's ``pip install`` lines make available.

    ``-r`` is followed into the requirements file, because a job that installs
    ``requirements-phase0.txt`` is installing whatever that file pins today, not
    whatever it pinned when this guard was written.
    """

    names = set()
    for raw in body.splitlines():
        line = raw.split("#", 1)[0]
        match = PIP_INSTALL_RE.search(line)
        if match is None:
            continue
        tokens = match.group("args").split()
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in ("-r", "--requirement"):
                index += 1
                if index < len(tokens):
                    names |= _requirements_distributions(tokens[index])
            elif not token.startswith("-"):
                dist = DIST_RE.match(token)
                if dist:
                    names.add(dist.group(0).lower())
            index += 1
    return names


def _required_distributions():
    """Third-party modules ``tests/`` guards with ``find_spec``.

    These are exactly the imports the tree treats as optional, which is the same
    thing as saying: these are the tests that vanish, quietly, when a job runs
    without them.
    """

    required = set()
    for path in sorted((ROOT / "tests").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name != "find_spec" or not node.args:
                continue
            first = node.args[0]
            if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
                continue
            module = first.value.split(".")[0]
            if module in sys.stdlib_module_names:
                continue
            required.add(DISTRIBUTION_ALIASES.get(module, module).lower())
    return required


class FullSuiteJobsInstallRequirementsTest(unittest.TestCase):
    def test_there_is_something_to_check(self):
        """Guard against the assertion below passing vacuously."""

        self.assertTrue(WORKFLOWS.is_dir(), f"{WORKFLOWS} is missing")
        found = list(_whole_tree_jobs())
        self.assertGreater(
            len(found),
            0,
            "no whole-tree test job was parsed; the matcher is probably broken",
        )

    def test_the_tree_declares_optional_dependencies(self):
        """Guard against the assertion below passing vacuously."""

        required = _required_distributions()
        self.assertTrue(
            required,
            "no find_spec-guarded module was found in tests/, so the check below "
            "would pass no matter what the workflows install. Either the tree "
            "genuinely has no optional dependency, or _required_distributions "
            "has stopped matching how they are declared.",
        )

    def test_whole_tree_jobs_install_everything_the_tree_needs(self):
        required = _required_distributions()
        missing = {}
        for path, name, body in _whole_tree_jobs():
            absent = sorted(required - _installed_distributions(body))
            if absent:
                missing[f"{path.name}:{name}"] = absent
        self.assertEqual(
            missing,
            {},
            "these jobs discover the whole tests/ tree without installing "
            "everything the tree guards on, so those tests skip themselves while "
            f"the job still reports success: {missing}. Either add the missing "
            "distribution to that job's pip install, or scope the run with -p so "
            "it is a deliberate stdlib-only check.",
        )


if __name__ == "__main__":
    unittest.main()
