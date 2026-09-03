#!/usr/bin/env python3
"""A narrated, sixty-second tour of the IDKMesh acceptance contract.

This is the fastest honest answer to "what does IDKMesh actually do today?".
It tells one story end to end -- a bounded Work Unit is attempted, the worker
files a claim, and the contract decides what may be accepted -- using the real
schemas in ``schemas/`` and the real fixtures in ``examples/``. Nothing here is
mocked or narrated over a stub.

Two of the acts are deliberately *failures*: a worker that accepts its own
output, and a "verifier" that is the worker wearing a different hat. Those are
the project's central claim, so the demo asserts that they are still rejected
and exits non-zero if they ever stop being. Running this is therefore both a
demonstration and a regression test.

Usage::

    python scripts/demo.py           # narrated tour
    python scripts/demo.py --quiet   # assertions only, for CI
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.provenance_integrity import (  # noqa: E402
    IntegrityError,
    validate_integrity,
)
from experiments.harness import (  # noqa: E402
    HarnessError,
    WORKER_RESULT_SCHEMA,
    load_json,
    resolve_repo_path,
    validate_instance,
    validate_manifest_and_work_units,
    validate_verification_result_contract,
    validate_worker_result_contract,
)

MANIFEST = "examples/experiments/phase0-smoke.manifest.json"
WORKER_RESULT = "examples/results/phase0-smoke.result-manifest.json"
VERIFICATION_RESULT = "examples/results/phase0-smoke.verification-result.json"
SELF_ACCEPTED = "examples/results/invalid-self-acceptance.result-manifest.json"
NON_INDEPENDENT = "examples/results/invalid-non-independent.verification-result.json"
BAD_PROVENANCE = "examples/results/invalid-mismatched-provenance.verification-result.json"
WORK_UNIT_FILE = "examples/work-units/phase0-smoke.work-unit.json"


class Narrator:
    """Prints the story, or stays silent under --quiet."""

    def __init__(self, quiet: bool) -> None:
        self.quiet = quiet
        self.color = (
            not quiet
            and sys.stdout.isatty()
            and not os.environ.get("NO_COLOR")
        )

    def _paint(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def act(self, number: int, title: str) -> None:
        if self.quiet:
            return
        print()
        print(self._paint(f"  {number}. {title}", "1"))

    def say(self, text: str) -> None:
        if not self.quiet:
            print(f"     {text}")

    def accepted(self, text: str) -> None:
        if not self.quiet:
            print(f"     {self._paint('ACCEPTED', '32')}  {text}")

    def rejected(self, text: str, reason: str) -> None:
        if not self.quiet:
            print(f"     {self._paint('REJECTED', '31')}  {text}")
            print(f"               {self._paint(reason, '2')}")

    def banner(self, text: str) -> None:
        if not self.quiet:
            print()
            print(self._paint(text, "1"))

    def note(self, text: str) -> None:
        if not self.quiet:
            print(self._paint(f"     {text}", "2"))


def expect_rejection(action: Callable[[], Any]) -> str:
    """Run something that must fail, and return why it failed.

    Raises if the action unexpectedly succeeds -- that would mean the contract
    has stopped enforcing one of the project's core claims.
    """
    try:
        action()
    except (HarnessError, IntegrityError, AssertionError, SystemExit) as exc:
        return str(exc) or exc.__class__.__name__
    raise SystemExit(
        "DEMO FAILED: an input that must be rejected was accepted. "
        "The acceptance contract has regressed."
    )


def first_line(text: str, limit: int = 96) -> str:
    """Pick the most informative line of a validation error.

    Schema errors lead with a "... failed N schema check(s):" header and put the
    actual problem on the next line, so prefer that detail when it is present.
    """
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return "rejected"
    line = lines[1] if len(lines) > 1 and lines[0].endswith(":") else lines[0]
    line = line.lstrip("- ")
    return line if len(line) <= limit else line[: limit - 1] + "\u2026"


def run(quiet: bool) -> int:
    out = Narrator(quiet)

    out.banner("IDKMesh in sixty seconds: who is allowed to say the work is done?")
    out.note("Every object below is a real file in this repository.")

    # ---------------------------------------------------------------- act 1
    out.act(1, "A bounded Work Unit")
    manifest_path = resolve_repo_path(MANIFEST)
    manifest, work_units = validate_manifest_and_work_units(manifest_path)
    work_unit_id, work_unit = next(iter(work_units.items()))
    required = [v["id"] for v in work_unit["validators"] if v["required"]]
    out.say(f"Work Unit {work_unit_id!r} from manifest {manifest['id']!r}.")
    out.say(
        f"It is a {work_unit['kind']} task that names its own validators up front: "
        f"{', '.join(required) or '(none required)'}."
    )
    out.note(
        "A worker receives a bounded contract -- not unlimited authority over the project."
    )

    # ---------------------------------------------------------------- act 2
    out.act(2, "A worker attempts it and files a claim")
    worker_result = validate_worker_result_contract(
        resolve_repo_path(WORKER_RESULT), work_units
    )
    out.say(
        f"Worker {worker_result['worker']['id']!r} reports status "
        f"{worker_result['status']!r}."
    )
    out.note("This is a claim about the work. It is not yet an acceptance of it.")

    # ---------------------------------------------------------------- act 3
    out.act(3, "The worker tries to accept its own output")
    self_accepted = load_json(resolve_repo_path(SELF_ACCEPTED))
    claim = self_accepted["self_report"]["claims"][0]
    reason = expect_rejection(
        lambda: validate_instance(self_accepted, WORKER_RESULT_SCHEMA, SELF_ACCEPTED)
    )
    out.say(f"Worker {self_accepted['worker']['id']!r} says: {claim!r}")
    out.rejected(
        "the result manifest is not a valid worker claim",
        first_line(reason),
    )
    out.note("Worker completion is never self-acceptance. This is the whole point.")

    # ---------------------------------------------------------------- act 4
    out.act(4, "An independent verifier looks at the same work")
    verification = validate_verification_result_contract(
        resolve_repo_path(VERIFICATION_RESULT), worker_result, work_units
    )
    independence = verification["independence"]
    out.accepted(
        f"verifier {verification['verifier']['id']!r} returned "
        f"{verification['status']!r}"
    )
    out.say(
        f"It is a separate actor from the worker "
        f"(independent_from_worker={independence['independent_from_worker']}, "
        f"shared_model_family={independence['shared_model_family']})."
    )
    out.note(
        "Independence is declared and checked as evidence -- not assumed from good intentions."
    )

    # ---------------------------------------------------------------- act 5
    out.act(5, "The worker comes back wearing a verifier badge")
    non_independent = load_json(resolve_repo_path(NON_INDEPENDENT))
    reason = expect_rejection(
        lambda: validate_verification_result_contract(
            resolve_repo_path(NON_INDEPENDENT), worker_result, work_units
        )
    )
    out.say(
        f"The 'verifier' id is {non_independent['verifier']['id']!r} -- the same actor "
        f"that did the work."
    )
    out.rejected("the verification does not count", first_line(reason))
    out.note("A verifier correlated with the worker adds volume, not evidence.")

    # ---------------------------------------------------------------- act 6
    out.act(6, "Someone edits the provenance to make the story fit")
    bad_provenance = load_json(resolve_repo_path(BAD_PROVENANCE))
    standalone_work_unit = load_json(resolve_repo_path(WORK_UNIT_FILE))
    out.say(
        "This one is shape-valid, declares itself independent, and recommends "
        f"{bad_provenance['decision_support']['recommendation']!r}."
    )
    reason = expect_rejection(
        lambda: validate_integrity(standalone_work_unit, worker_result, bad_provenance)
    )
    out.rejected("the verification does not bind to what was actually run", first_line(reason))
    out.note("Evidence must reference the exact artifact it claims to have checked.")

    # ---------------------------------------------------------------- close
    out.banner("That is the contract: bounded work, independent verification, bound evidence.")
    if not quiet:
        print(
            "     Three things were accepted only because they earned it, and three\n"
            "     were rejected even though every one of them said 'passed'.\n"
        )
        print("     Next steps:")
        print("       python experiments/harness.py validate    the full contract check")
        print("       make test                                 the unit suite")
        print("       CONTRIBUTING.md                           how to send a change")
        print()
    else:
        print("demo: ok (3 accepted, 3 rejected as required)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="run the assertions without the narration (used by CI)",
    )
    args = parser.parse_args()
    try:
        return run(args.quiet)
    except (HarnessError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"demo: FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
