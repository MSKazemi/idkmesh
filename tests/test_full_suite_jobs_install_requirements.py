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




# ---------------------------------------------------------------------------
# A workflow that installs a requirements file must also watch it.
#
# Installing a dependency the workflow does not watch means changing that pin
# does not re-run the job that installs it: the job keeps certifying against a
# dependency set it was never re-tested with.
#
# The exemption is the case that is easy to get wrong, so it is a named branch
# rather than an implicit skip. A workflow with NO `paths:` filter runs on every
# change already, so the requirement is vacuous for it -- `pr-gate.yml`,
# `ci-shadow-outcome.yml` and `ci-shadow-planner.yml` are in exactly that
# position. Counting them as defects inflates the finding, which is how a survey
# of this same class came in at 15 when the answer is 12.
# ---------------------------------------------------------------------------

PATHS_KEY_RE = re.compile(r"^(?P<indent>\s*)paths:\s*$")
LIST_ITEM_RE = re.compile(r"^\s*-\s+(?P<value>\S.*?)\s*$")
REQUIREMENTS_INSTALL_RE = re.compile(
    r"pip\s+install[^\n]*?(?P<file>requirements[A-Za-z0-9._-]*\.txt)"
)


def _strip_yaml_scalar(value):
    """Unquote a YAML list entry written with either quote style, or none.

    Matching only double quotes is a real bug this repository has hit twice: a
    workflow written with single quotes parses to zero watched paths, and every
    file it names then reads as unwatched.
    """

    value = value.split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _paths_filters(text):
    """Each ``paths:`` block in one workflow, as a separate list of entries.

    Blocks are kept separate rather than unioned. A workflow commonly filters
    `push` and `pull_request` independently, and a file watched by one but not
    the other is still skipped by the other -- unioning them hides exactly that,
    which mutation testing caught this guard doing.

    Returns ``None`` when the workflow declares no ``paths:`` key at all, which
    is a different state from declaring one that is empty: the first means
    "runs on everything", the second means the parser failed.
    """

    lines = text.splitlines()
    found_key = False
    blocks = []
    for index, line in enumerate(lines):
        match = PATHS_KEY_RE.match(line)
        if not match:
            continue
        found_key = True
        entries = []
        indent = len(match.group("indent"))
        for follow in lines[index + 1:]:
            stripped = follow.strip()
            if not stripped or stripped.startswith("#"):
                # A comment must not terminate the block. Terminating on the
                # first comment is the second parser bug this class has produced
                # -- an explanatory comment added by a fix defeated the tool that
                # measured the fix.
                continue
            if len(follow) - len(follow.lstrip()) <= indent:
                break
            item = LIST_ITEM_RE.match(follow)
            if item is None:
                break
            entries.append(_strip_yaml_scalar(item.group("value")))
        blocks.append(entries)
    return blocks if found_key else None


def _requirements_installed(text):
    return {match.group("file") for match in REQUIREMENTS_INSTALL_RE.finditer(text)}


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


class WorkflowsWatchWhatTheyInstallTests(unittest.TestCase):
    """Changing a dependency pin must re-run the jobs that install it."""

    def test_a_paths_block_never_parses_to_nothing(self) -> None:
        """The shared precondition of both parser bugs this class has produced.

        A workflow that declares ``paths:`` and yields zero entries is a parser
        failure, not a workflow with no filter. Failing closed on it would blame
        the workflow for the parser's gap, so it raises instead.
        """

        for path in sorted(WORKFLOWS.glob("*.yml")):
            blocks = _paths_filters(path.read_text(encoding="utf-8"))
            if blocks is None:
                continue
            for number, entries in enumerate(blocks, start=1):
                with self.subTest(workflow=path.name, block=number):
                    self.assertTrue(
                        entries,
                        f"{path.name} block {number} declares a paths: filter "
                        f"that parsed to zero entries. That is this test's "
                        f"parser failing, not the workflow being unfiltered -- "
                        f"fix _paths_filters rather than the workflow.",
                    )

    def test_both_quote_styles_and_bare_entries_parse_alike(self) -> None:
        """Matching only double quotes is the bug that over-counted by 3x."""

        double = 'on:\n  push:\n    paths:\n      - "a/b.txt"\n      - "c.py"\n'
        single = "on:\n  push:\n    paths:\n      - 'a/b.txt'\n      - 'c.py'\n"
        bare = "on:\n  push:\n    paths:\n      - a/b.txt\n      - c.py\n"
        expected = [["a/b.txt", "c.py"]]
        for label, text in (("double", double), ("single", single), ("bare", bare)):
            with self.subTest(style=label):
                self.assertEqual(_paths_filters(text), expected)

    def test_a_comment_does_not_terminate_a_paths_block(self) -> None:
        """A fix's own explanatory comment must not defeat the measurement."""

        text = (
            "on:\n  push:\n    paths:\n"
            "      - a/b.txt\n"
            "      # why the next entry is watched\n"
            "      - c.py\n"
        )
        self.assertEqual(_paths_filters(text), [["a/b.txt", "c.py"]])

    def test_a_workflow_without_a_paths_filter_is_exempt(self) -> None:
        """It runs on everything, so it cannot miss a change."""

        self.assertIsNone(_paths_filters("on:\n  push:\n    branches: [main]\n"))

    def test_every_filtered_workflow_watches_what_it_installs(self) -> None:
        offenders = {}
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            installed = _requirements_installed(text)
            if not installed:
                continue
            blocks = _paths_filters(text)
            if blocks is None:
                continue  # unfiltered: runs on every change already
            for number, watched in enumerate(blocks, start=1):
                missing = sorted(n for n in installed if n not in watched)
                if missing:
                    offenders[f"{path.name} (paths block {number})"] = missing
        self.assertEqual(
            offenders,
            {},
            "these workflows install a requirements file they do not watch, so "
            "changing that pin does not re-run the job that installs it: "
            f"{offenders}. Add the file to the workflow's paths: filter, or "
            "remove the filter if the workflow should always run.",
        )
