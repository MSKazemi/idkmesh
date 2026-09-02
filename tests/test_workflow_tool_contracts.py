"""Pin the CLI contracts that workflows must honour when invoking repo tools.

A workflow that calls a tool with arguments the tool rejects fails only when
that workflow actually runs. For a scheduled workflow that can be days, and the
failure is a red run nobody is watching rather than a red pull request. These
tests move that feedback to the ordinary test suite, where the PR Gate sees it.

The concrete case this was written for: `collaboration-observables.yml` invoked
`tools/idkgraph_observatory.py --output-dir results/observatory`. The observatory
walks the repository tree, so it refuses to write its artifacts inside that tree
-- writing there would make a later scan observe its own output -- and exits 2.
The step had never once succeeded.

Deliberately text-based rather than YAML-parsed: the PR Gate installs only
`pytest` and `requirements-phase0.txt` (jsonschema alone), so `import yaml`
would pass locally and fail in the very gate this file describes.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
OBSERVATORY = "tools/idkgraph_observatory.py"

# A `python <script>.py` command and the rest of its line, following `\`
# continuations. The continuation alternative must come first: `[^\n]` would
# otherwise consume the backslash and stop at the first wrapped line, which hides
# most of the arguments in this repository -- they are nearly all multi-line.
INVOCATION = re.compile(r"python3?\s+(?:-u\s+)?((?:[\w./-]+/)?[\w.-]+\.py)((?:\\\n|[^\n])*)")
DECLARED_FLAG = re.compile(r"""add_argument\(\s*["'](--[A-Za-z0-9][A-Za-z0-9\-_]*)["']""")
USED_FLAG = re.compile(r"(?<![\w-])(--[A-Za-z0-9][A-Za-z0-9\-_]*)")

# Captures the value after --output-dir, with surrounding quotes left in place so
# they can be stripped explicitly rather than silently swallowed by the pattern.
OUTPUT_DIR = re.compile(r"--output-dir[=\s]+(\S+)")


def workflows_invoking_observatory() -> list[tuple[Path, str]]:
    found = []
    for wf in sorted(WORKFLOW_DIR.glob("*.yml")):
        text = wf.read_text(encoding="utf-8")
        # `on: paths:` filters name the script without invoking it; only a
        # `python .../idkgraph_observatory.py` command line counts.
        if re.search(rf"python3?\s+{re.escape(OBSERVATORY)}", text):
            found.append((wf, text))
    return found


class ObservatoryOutputDirTests(unittest.TestCase):
    def test_at_least_one_workflow_invokes_the_observatory(self) -> None:
        """Guard the guard: a pattern that matches nothing must not pass silently."""
        self.assertNotEqual(
            workflows_invoking_observatory(),
            [],
            f"no workflow invokes {OBSERVATORY}; this guard has stopped guarding "
            f"anything and its pattern needs updating.",
        )

    def test_observatory_output_dir_is_always_outside_the_scanned_tree(self) -> None:
        checked = 0
        for wf, text in workflows_invoking_observatory():
            for raw in OUTPUT_DIR.findall(text):
                value = raw.strip("\"'")
                checked += 1
                with self.subTest(workflow=wf.name, output_dir=value):
                    self.assertTrue(
                        value.startswith("/") or value.startswith("$"),
                        f"{wf.name} passes --output-dir {value!r} to "
                        f"{OBSERVATORY}. That is a repository-relative path, so "
                        f"the artifacts would land inside the tree the "
                        f"observatory scans; the tool rejects this and exits 2. "
                        f'Use an absolute path or "$RUNNER_TEMP/...".',
                    )
        self.assertGreater(checked, 0, "no --output-dir arguments were inspected")


class WorkflowFlagContractTests(unittest.TestCase):
    """Every flag a workflow passes must be one the script declares.

    argparse rejects an unknown option with exit code 2, so a renamed or
    mistyped flag breaks the workflow at run time and nowhere earlier. On a
    scheduled workflow that means a red run nobody is watching -- the same way
    `collaboration-observables.yml` failed for days above.
    """

    def _resolve(self, script_rel: str) -> Path | None:
        script = ROOT / script_rel
        if script.is_file():
            return script
        if "/" in script_rel:
            # Some workflows check this repository out under a path (e.g.
            # `path: evaluator`), so the command line carries a prefix that does
            # not exist inside the repository itself.
            alt = ROOT / script_rel.split("/", 1)[1]
            if alt.is_file():
                return alt
        return None

    def _pairs(self):
        """(workflow, script path, declared flags, used flags) per invocation."""
        for wf in sorted(WORKFLOW_DIR.glob("*.yml")):
            text = wf.read_text(encoding="utf-8")
            for match in INVOCATION.finditer(text):
                script = self._resolve(match.group(1))
                if script is None:
                    continue
                source = script.read_text(encoding="utf-8")
                if "add_argument" not in source:
                    continue  # not an argparse CLI; nothing to contract
                yield (
                    wf.name,
                    match.group(1),
                    set(DECLARED_FLAG.findall(source)),
                    set(USED_FLAG.findall(match.group(2))),
                )

    def test_the_scan_reaches_multi_line_invocations(self) -> None:
        """Guard the guard: a scan that stops at the first line continuation proves nothing.

        Nearly every tool invocation here wraps across lines, so a scan that only
        saw single-line commands would report a clean result while checking a
        small fraction of the arguments.
        """
        total = sum(len(used) for _, _, _, used in self._pairs())
        self.assertGreater(
            total,
            200,
            f"only {total} flag uses were seen; the invocation pattern has "
            f"stopped following backslash continuations.",
        )

    def test_workflows_pass_only_flags_the_script_declares(self) -> None:
        for wf_name, script_rel, declared, used in self._pairs():
            for flag in sorted(used - declared):
                with self.subTest(workflow=wf_name, script=script_rel, flag=flag):
                    self.fail(
                        f"{wf_name} passes {flag} to {script_rel}, which does not "
                        f"declare it. argparse exits 2 on an unknown option, so "
                        f"this breaks the workflow at run time. Declared: "
                        f"{', '.join(sorted(declared)) or '(none)'}."
                    )


if __name__ == "__main__":
    unittest.main()
