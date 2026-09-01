"""Repository-wide CI hygiene invariants for every GitHub Actions workflow.

Three properties are pinned here, each because losing it costs something that
is not recoverable after the fact:

`concurrency`
    Without a group, N pushes to the same ref run N times concurrently and the
    runner minutes are spent computing results nobody reads.

`cancel-in-progress`
    A superseded *pull-request* run should be cancelled. A run on a branch or a
    schedule must not be, because several of these workflows are the only thing
    that uploads the evidence artifact for their commit; cancelling one destroys
    that record and there is nothing left to re-derive it from. So the value
    must be `false` or gated on the event -- never a bare `true`.

    This applies to the *workflow-level* block only. A job-level `concurrency:`
    is scoped by a group key its author chose deliberately -- evolution-loop.yml
    separates advisory `pull_request_target` observations from canonical ones in
    the group expression itself, so a bare `true` is correct there and
    tests/test_evolution_workflow_security.py pins it. Job-level blocks are
    six-space indented, which is what the pattern below excludes.

`timeout-minutes`
    A hung job otherwise occupies a runner slot until the six-hour default
    expires.

Deliberately text-based rather than YAML-parsed: the PR Gate installs only
`pytest` and `requirements-phase0.txt` (jsonschema alone), so `import yaml`
would pass locally and fail in the very gate this file describes -- the same
constraint recorded in tests/test_ci_local_gate_parity.py.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"

JOB_NAME = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
TOP_LEVEL = re.compile(r"^[A-Za-z]")
JOB_TIMEOUT = re.compile(r"^    timeout-minutes:\s*\d+\s*$", re.M)
JOB_USES = re.compile(r"^    uses:\s*\S", re.M)
# Exactly two spaces: a key of the top-level `concurrency:` block. Job-level
# blocks sit at six and are deliberately out of scope (see the module docstring).
CANCEL = re.compile(r"^  cancel-in-progress:\s*(.+?)\s*$", re.M)
CONCURRENCY = re.compile(r"^concurrency:\s*$", re.M)
GROUP = re.compile(r"^\s+group:\s*\S", re.M)


def workflows() -> list[Path]:
    return sorted(WORKFLOW_DIR.glob("*.yml"))


def job_blocks(text: str) -> list[tuple[str, str]]:
    """Return (job name, job body) for each job, by indentation.

    Job names are the only keys at two-space indent inside the `jobs:` mapping,
    so this needs no YAML parser.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("jobs:")), None)
    if start is None:
        return []

    body: list[str] = []
    for line in lines[start + 1 :]:
        if TOP_LEVEL.match(line):  # a sibling of `jobs:` ends the section
            break
        body.append(line)

    heads = [i for i, line in enumerate(body) if JOB_NAME.match(line)]
    blocks = []
    for n, i in enumerate(heads):
        end = heads[n + 1] if n + 1 < len(heads) else len(body)
        name = JOB_NAME.match(body[i]).group(1)
        blocks.append((name, "\n".join(body[i:end])))
    return blocks


class WorkflowCiHygieneTests(unittest.TestCase):
    def test_there_are_workflows_to_check(self) -> None:
        """Guard the guard: a bad glob must not make every test below vacuous."""
        self.assertGreater(len(workflows()), 0, f"no workflows found in {WORKFLOW_DIR}")

    def test_every_workflow_declares_a_concurrency_group(self) -> None:
        for wf in workflows():
            text = wf.read_text(encoding="utf-8")
            with self.subTest(workflow=wf.name):
                self.assertRegex(
                    text,
                    CONCURRENCY,
                    f"{wf.name} has no top-level `concurrency:` block; runs on "
                    f"the same ref will pile up instead of superseding.",
                )
                self.assertRegex(
                    text,
                    GROUP,
                    f"{wf.name} declares `concurrency:` without a `group:`.",
                )

    def test_no_workflow_cancels_runs_outside_pull_requests(self) -> None:
        """Workflow-level only; job-level scoping is the author's to choose."""
        for wf in workflows():
            text = wf.read_text(encoding="utf-8")
            for value in CANCEL.findall(text):
                with self.subTest(workflow=wf.name, value=value):
                    self.assertNotEqual(
                        value,
                        "true",
                        f"{wf.name} sets a workflow-level `cancel-in-progress: "
                        f"true`, which also "
                        f"cancels branch and scheduled runs and can destroy the "
                        f"evidence artifact for a commit. Use `false`, or gate "
                        f"it: ${{{{ github.event_name == 'pull_request' }}}}.",
                    )

    def test_every_job_declares_a_timeout(self) -> None:
        checked = 0
        for wf in workflows():
            for name, block in job_blocks(wf.read_text(encoding="utf-8")):
                if JOB_USES.search(block):
                    continue  # a reusable-workflow call cannot take timeout-minutes
                checked += 1
                with self.subTest(workflow=wf.name, job=name):
                    self.assertRegex(
                        block,
                        JOB_TIMEOUT,
                        f"{wf.name}: job `{name}` has no job-level "
                        f"`timeout-minutes`; a hang would hold a runner for the "
                        f"six-hour default.",
                    )
        self.assertGreater(checked, 0, "no jobs were inspected; the parser is broken")


if __name__ == "__main__":
    unittest.main()
