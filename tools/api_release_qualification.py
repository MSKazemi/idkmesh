#!/usr/bin/env python3
"""API release qualification: one repeatable run, one JSON report (issue #745).

Issue 745 asks that "API release qualification is a repeatable CI/release
artifact, not a manual confidence statement". The individual checks already
exist -- the OpenAPI reference gate, the schema compatibility gate, the
contract tests, the fuzz and security matrices, the reliability suites -- but
nothing named them as one set or recorded that the set was run. This tool is
that set:

==============  ==========================================================
group           checks
==============  ==========================================================
contract        ``tools/openapi_ref_check.py``; ``tools/schema_compat_check.py``
                against ``--base``; the OpenAPI, conformance, example and
                Human Decision contract test modules
fuzz            strict-JSON totality and header/media-type boundary fuzz
security        Host, token-bypass, method-confusion and CORS/CSRF matrices
reliability     request limits, overload, drain, slow clients, event stream;
                ``tools/api_load_soak.py`` (concurrent load, thread/fd leaks,
                heap growth)
client          the official Python client
install         ``tools/api_clean_install_demo.py``: build a wheel, install it
                into a fresh venv, run the installed server and client, and
                require the same transcript as the source tree (needs network
                access to fetch the build backend)
==============  ==========================================================

Every check runs as a subprocess with this interpreter, and the report records
the exact command, exit code, duration, and the tail of its output, plus the
git revision and Python version, so a release can attach the file as evidence.

A test module listed here that no longer exists is a ``missing`` check and
fails the run: renaming or deleting a suite must not silently shrink the
qualification. Without ``--base`` the compatibility gate is ``skipped`` (it
cannot run without a revision to diff); ``--strict`` turns every skip into a
failure, which is what a release should use.

Exit codes: 0 every check passed (or was skipped without ``--strict``),
1 at least one check failed or is missing, 2 the run could not start.

Not yet covered, and recorded in the report's ``not_covered`` list rather than
implied: capacity benchmarking, a permission matrix at the HTTP layer, and
proxy/request-smuggling tests for a production adapter. The last two depend on
adapter work that does not exist yet (#743). The authorization kernel's own
role x action x actor-type table is pinned by
``tests/test_enterprise_authz_permission_matrix.py`` (issue #745).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_SCHEMA = "idkmesh-api-release-qualification/v1"
DEFAULT_OUTPUT = Path("results/api-qualification/report.json")
OUTPUT_TAIL_LINES = 12

NOT_COVERED = (
    "capacity benchmarking (the load/soak run is a regression tripwire, not a "
    "throughput figure)",
    "permission matrix at the HTTP layer (the HTTP surface has no principals "
    "yet, issue 743; the authorization kernel's own table is pinned by "
    "tests/test_enterprise_authz_permission_matrix.py)",
    "proxy / request-smuggling tests for a production adapter (issue 743)",
)

CONTRACT_TESTS = (
    "tests/test_openapi_document.py",
    "tests/test_openapi_ref_check.py",
    "tests/test_schema_compat_check.py",
    "tests/test_api_contract_conformance.py",
    "tests/test_example_contract_coverage.py",
    "tests/test_human_decision_api_contracts.py",
)
FUZZ_TESTS = (
    "tests/test_api_qualification_fuzz.py",
    "tests/test_api_header_boundary_fuzz.py",
)
SECURITY_TESTS = (
    "tests/test_api_security_matrix.py",
    "tests/test_api_cors_csrf_matrix.py",
    "tests/test_enterprise_authz_permission_matrix.py",
    "tests/test_enterprise_identity_github.py",
    "tests/test_github_dispatch_authorization.py",
)
RELIABILITY_TESTS = (
    "tests/test_control_tower_limits.py",
    "tests/test_control_tower_events.py",
    "tests/test_control_tower_run_evidence.py",
    "tests/test_control_tower.py",
)
CLIENT_TESTS = ("tests/test_api_client.py",)


@dataclass(frozen=True)
class Check:
    id: str
    group: str
    argv: tuple[str, ...]
    #: Files that must exist for the check to count; a missing one fails it.
    requires: tuple[str, ...] = ()
    #: Set when the check cannot run in this invocation (and why).
    skip_reason: str | None = None


@dataclass(frozen=True)
class Outcome:
    exit_code: int | None
    output: str


Runner = Callable[[Sequence[str], Path], Outcome]


def build_checks(base: str | None, python: str = sys.executable) -> list[Check]:
    """The qualification set, in execution order."""
    compat_skip = None if base else "no --base revision given to diff against"
    compat_argv = [python, "tools/schema_compat_check.py"]
    if base:
        compat_argv += ["--base", base]
    checks = [
        Check(
            "openapi-refs",
            "contract",
            (python, "tools/openapi_ref_check.py"),
            requires=("tools/openapi_ref_check.py", "openapi.yaml"),
        ),
        Check(
            "schema-compat",
            "contract",
            tuple(compat_argv),
            requires=("tools/schema_compat_check.py",),
            skip_reason=compat_skip,
        ),
    ]
    checks.append(
        Check(
            "reliability:load-soak",
            "reliability",
            (python, "tools/api_load_soak.py"),
            requires=("tools/api_load_soak.py",),
        )
    )
    checks.append(
        Check(
            "install:clean-install-demo",
            "install",
            (python, "tools/api_clean_install_demo.py"),
            requires=("tools/api_clean_install_demo.py", "pyproject.toml"),
        )
    )
    for group, modules in (
        ("contract", CONTRACT_TESTS),
        ("fuzz", FUZZ_TESTS),
        ("security", SECURITY_TESTS),
        ("reliability", RELIABILITY_TESTS),
        ("client", CLIENT_TESTS),
    ):
        for module in modules:
            checks.append(
                Check(
                    f"{group}:{Path(module).stem.removeprefix('test_')}",
                    group,
                    (python, "-m", "pytest", "-q", "-p", "no:cacheprovider", module),
                    requires=(module,),
                )
            )
    return checks


def run_subprocess(argv: Sequence[str], cwd: Path) -> Outcome:
    """Run one check; a command that cannot start reports ``exit_code=None``."""
    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
    except OSError as exc:
        return Outcome(None, f"could not start: {exc}")
    return Outcome(completed.returncode, completed.stdout + completed.stderr)


def _tail(output: str) -> list[str]:
    lines = [line for line in output.splitlines() if line.strip()]
    return lines[-OUTPUT_TAIL_LINES:]


def _counts(output: str) -> dict[str, int]:
    """Pytest summary counts (``26 passed, 257 subtests passed``), if present."""
    counts: dict[str, int] = {}
    for number, word in re.findall(r"(\d+) (passed|failed|skipped|errors?)\b", output):
        counts[word.rstrip("s") if word.startswith("error") else word] = int(number)
    return counts


def run_check(check: Check, root: Path, runner: Runner) -> dict:
    record: dict = {
        "id": check.id,
        "group": check.group,
        "command": list(check.argv),
    }
    missing = [path for path in check.requires if not (root / path).exists()]
    if missing:
        record.update(
            status="missing",
            detail=f"required file(s) not found: {', '.join(missing)}",
        )
        return record
    if check.skip_reason:
        record.update(status="skipped", detail=check.skip_reason)
        return record
    started = time.monotonic()
    outcome = runner(check.argv, root)
    record["duration_s"] = round(time.monotonic() - started, 3)
    record["exit_code"] = outcome.exit_code
    record["status"] = "passed" if outcome.exit_code == 0 else "failed"
    record["counts"] = _counts(outcome.output)
    record["output_tail"] = _tail(outcome.output)
    return record


def _git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def verdict(records: Sequence[dict], strict: bool) -> str:
    statuses = {record["status"] for record in records}
    if statuses & {"failed", "missing"}:
        return "fail"
    if strict and "skipped" in statuses:
        return "fail"
    return "pass"


def qualify(
    root: Path,
    base: str | None,
    strict: bool = False,
    runner: Runner = run_subprocess,
    python: str = sys.executable,
) -> dict:
    records = [run_check(check, root, runner) for check in build_checks(base, python)]
    totals: dict[str, int] = {}
    for record in records:
        totals[record["status"]] = totals.get(record["status"], 0) + 1
    return {
        "schema": REPORT_SCHEMA,
        "verdict": verdict(records, strict),
        "strict": strict,
        "base": base,
        "git_revision": _git(root, "rev-parse", "HEAD"),
        "git_dirty": bool(_git(root, "status", "--porcelain")),
        "python": sys.version.split()[0],
        "totals": totals,
        "checks": records,
        "not_covered": list(NOT_COVERED),
    }


def render_summary(report: dict) -> str:
    lines = [f"API release qualification: {report['verdict'].upper()}"]
    for record in report["checks"]:
        extra = record.get("detail") or (
            f"{record['duration_s']:.1f}s" if "duration_s" in record else ""
        )
        lines.append(f"  {record['status']:<8} {record['id']:<48} {extra}".rstrip())
    totals = ", ".join(f"{n} {status}" for status, n in sorted(report["totals"].items()))
    lines.append(f"  totals: {totals}")
    lines.append("  not covered: " + "; ".join(report["not_covered"]))
    if report["git_dirty"]:
        lines.append("  note: the working tree has uncommitted changes")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base",
        help="git revision the schema compatibility gate diffs against "
        "(for example the previous release tag)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat a skipped check as a failure (use for releases)",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"where to write the JSON report (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--root", default=str(REPO_ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not (root / "tools").is_dir():
        print(f"error: {root} does not look like the repository root", file=sys.stderr)
        return 2
    report = qualify(root, args.base, strict=args.strict)
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        print(f"error: cannot write the report: {exc}", file=sys.stderr)
        return 2
    print(render_summary(report))
    print(f"report: {output}")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
