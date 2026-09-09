#!/usr/bin/env python3
"""A narrated, sixty-second tour of the IDKMesh acceptance contract.

Validate committed synthetic fixtures using the real repository validators.
No worker, model, external verifier, or human reviewer runs in this demo.
A fixture passing a contract check is not proof of a live actor's identity,
independence, task correctness, or authority to integrate a change.

The four deliberately invalid fixtures must be rejected. Only a contract or
integrity exception counts as that evidence; unrelated failures propagate.

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
    WORK_UNIT_SCHEMA,
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
UNBOUNDED_WORK_UNIT = "examples/work-units/invalid-missing-security.work-unit.json"


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
    """Return a contract rejection, never mistake an unrelated crash for one."""
    try:
        action()
    except (HarnessError, IntegrityError) as exc:
        return str(exc) or exc.__class__.__name__
    raise HarnessError(
        "DEMO FAILED: an input that must be rejected was accepted. "
        "The acceptance contract has regressed."
    )


def first_line(text: str, limit: int = 96) -> str:
    """Pick the most informative line of a validation error."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return "rejected"
    line = lines[1] if len(lines) > 1 and lines[0].endswith(":") else lines[0]
    line = line.lstrip("- ")
    return line if len(line) <= limit else line[: limit - 1] + "\u2026"


def run(quiet: bool) -> int:
    out = Narrator(quiet)

    out.banner("IDKMesh in sixty seconds: who is allowed to say the work is done?")
    out.note("Synthetic fixture validation only: no live worker or verifier is executed.")
    out.note("ACCEPTED below means contract-valid fixture, not accepted work or merge authority.")

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
    out.act(2, "A task that never says what a worker may touch")
    unbounded = load_json(resolve_repo_path(UNBOUNDED_WORK_UNIT))
    reason = expect_rejection(
        lambda: validate_instance(unbounded, WORK_UNIT_SCHEMA, UNBOUNDED_WORK_UNIT)
    )
    out.say(
        f"Work Unit {unbounded['id']!r} is a {unbounded['kind']} task with no security contract."
    )
    out.rejected("this fixture is not a dispatchable contract", first_line(reason))
    out.note("The security contract is required before dispatch; this demo dispatches nothing.")

    # ---------------------------------------------------------------- act 3
    out.act(3, "A recorded worker result makes a claim")
    worker_result = validate_worker_result_contract(
        resolve_repo_path(WORKER_RESULT), work_units
    )
    out.say(
        f"Worker fixture {worker_result['worker']['id']!r} reports status "
        f"{worker_result['status']!r}."
    )
    out.note("This is a claim about the work. It is not yet an acceptance of it.")

    # ---------------------------------------------------------------- act 4
    out.act(4, "The worker tries to accept its own output")
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

    # ---------------------------------------------------------------- act 5
    out.act(5, "A verification fixture declares a separate actor")
    verification = validate_verification_result_contract(
        resolve_repo_path(VERIFICATION_RESULT), worker_result, work_units
    )
    independence = verification["independence"]
    out.accepted(
        f"verification fixture {verification['verifier']['id']!r} is contract-valid; "
        f"declared status {verification['status']!r}"
    )
    out.say(
        f"The fixture declares independence "
        f"(independent_from_worker={independence['independent_from_worker']}, "
        f"shared_model_family={independence['shared_model_family']})."
    )
    out.note(
        "This checks declaration consistency, not live identity or statistical independence."
    )

    # ---------------------------------------------------------------- act 6
    out.act(6, "The worker comes back wearing a verifier badge")
    non_independent = load_json(resolve_repo_path(NON_INDEPENDENT))
    reason = expect_rejection(
        lambda: validate_verification_result_contract(
            resolve_repo_path(NON_INDEPENDENT), worker_result, work_units
        )
    )
    out.say(
        f"The 'verifier' id is {non_independent['verifier']['id']!r} -- the same actor "
        f"named by the worker fixture."
    )
    out.rejected("the verification does not count", first_line(reason))
    out.note("The worker cannot satisfy this independent-verifier contract itself.")

    # ---------------------------------------------------------------- act 7
    out.act(7, "Someone edits the provenance to make the story fit")
    bad_provenance = load_json(resolve_repo_path(BAD_PROVENANCE))
    standalone_work_unit = load_json(resolve_repo_path(WORK_UNIT_FILE))
    out.say(
        "This one is shape-valid, declares itself independent, and recommends "
        f"{bad_provenance['decision_support']['recommendation']!r}."
    )
    reason = expect_rejection(
        lambda: validate_integrity(standalone_work_unit, worker_result, bad_provenance)
    )
    out.rejected("the verification does not bind to the supplied artifacts", first_line(reason))
    out.note("Evidence must reference the exact artifact it claims to have checked.")

    # ---------------------------------------------------------------- close
    out.banner("That is the contract: bounded work, independent verification, bound evidence.")
    if not quiet:
        print(
            "     Three fixture checks passed and four invalid fixtures were rejected.\n"
            "     This demonstrates contract validation, not live execution or approval.\n"
        )
        print("     Next steps:")
        print("       python experiments/harness.py validate    the full contract check")
        print("       PYTHONPATH=. python -m pytest -q          the full test suite")
        print("       CONTRIBUTING.md                           how to send a change")
        print()
    else:
        print("demo: ok (3 accepted, 4 rejected as required; synthetic fixtures only)")
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
    except SystemExit as exc:
        # Even exit(0) is incomplete evidence when a validator terminates the tour.
        print(f"demo: FAILED: unexpected validator exit {exc.code!r}", file=sys.stderr)
        return 1
    except (HarnessError, IntegrityError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"demo: FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
