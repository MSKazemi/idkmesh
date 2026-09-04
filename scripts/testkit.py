#!/usr/bin/env python3
"""Tiered test runner: the single entry point for every gate, local and CI.

The tiers follow the size-and-budget model used by large monorepos (Google's
small/medium/large test sizes, Bazel-style affected-target selection): each
tier owns an explicit CPU-time budget, and a tier that exceeds its budget
fails loudly instead of quietly getting slower every quarter.

    smoke        affected tests only          budget   25 CPU-s  after each edit
    unit         the whole pytest suite       budget   90 CPU-s  before each commit
    integration  unit + schema/link gates     budget  600 CPU-s  before each push
    nightly      everything, sims included    no budget          scheduled

    auto         pick the cheapest tier that covers what actually changed

Design notes
------------
* Standard library only. The gate must run before dependencies are installed
  and must never itself become a reason CI is slow.
* Selection is advisory, never load-bearing: `smoke` narrows to affected tests
  for fast feedback, but `unit` — which is what actually gates a commit — always
  runs everything. Skipping a test you should have run is a far more expensive
  failure than running 870 of them in 34 seconds.
* Results are cached against the tree hash, so re-running a tier that has
  already passed on identical content is free. This is what makes it safe to
  wire into an editor or agent hook that fires constantly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".claude" / "state" / "testkit-cache.json"

# CPU-second ceiling per tier. These are contracts, not targets: crossing one
# is a defect in the test suite, reported as such. Measured in CPU time so a
# busy shared machine cannot fail the gate (see child_cpu).
#
# Calibrated against the measured baseline of ~36 CPU-seconds for the full
# suite, leaving roughly 2.5x headroom before the ceiling bites.
BUDGETS = {"smoke": 25.0, "unit": 90.0, "integration": 600.0, "nightly": None}


def python() -> str:
    """Prefer the project virtualenv so the gate is identical however it is invoked."""
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def run(cmd: list[str], timeout: float | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def child_cpu() -> float:
    """CPU seconds consumed by all reaped child processes so far.

    Budgets are enforced against CPU time, not wall-clock time, because this
    machine is shared with other projects: a neighbouring test run can push the
    load average past 25 and triple our wall-clock while the suite itself has
    not changed at all. CPU time is the load-independent measure of "is the
    suite getting slower", which is the only thing the budget should police.
    """
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


def measured(fn) -> tuple[float, float, object]:
    """Run `fn`, returning (wall seconds, cpu seconds, value)."""
    w0, c0 = time.monotonic(), child_cpu()
    value = fn()
    return time.monotonic() - w0, child_cpu() - c0, value


# --------------------------------------------------------------------------
# Change detection
# --------------------------------------------------------------------------


def changed_files() -> list[Path]:
    """Files differing from HEAD, including untracked ones.

    Uses the working tree rather than the index so the gate sees what the
    developer (or agent) has actually written, not what has been staged.
    """
    out: set[str] = set()
    for cmd in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        code, text = run(cmd)
        if code == 0:
            out.update(line for line in text.splitlines() if line.strip())
    return [ROOT / p for p in sorted(out)]


def tree_fingerprint() -> str:
    """Content hash of every tracked source/test file plus uncommitted changes.

    Two trees with the same fingerprint cannot produce different test results,
    which is what makes the result cache sound.
    """
    h = hashlib.sha256()
    code, tracked = run(["git", "ls-files", "-z"])
    names = tracked.split("\0") if code == 0 else []
    names += [str(p.relative_to(ROOT)) for p in changed_files() if p.exists()]
    for name in sorted(set(n for n in names if n)):
        path = ROOT / name
        if not path.is_file() or path.suffix not in {".py", ".json", ".ini", ".cfg"}:
            continue
        h.update(name.encode())
        try:
            h.update(path.read_bytes())
        except OSError:
            pass
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------
# Test impact analysis (lightweight)
# --------------------------------------------------------------------------


def affected_tests(changed: list[Path]) -> tuple[list[str], bool]:
    """Map changed source files to the test files that exercise them.

    Returns (test paths, complete) where `complete` is False when a change was
    seen that cannot be attributed to specific tests — a conftest, the pytest
    config, or a shared package __init__. In that case the caller must widen to
    the full suite rather than trust the selection.
    """
    tests: set[str] = set()
    complete = True
    test_roots = [ROOT / "tests", ROOT / "interop" / "tests"]

    for path in changed:
        if path.suffix != ".py":
            continue
        rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        name = path.stem

        # A changed test file is itself the thing to run.
        if name.startswith("test_"):
            if path.exists():
                tests.add(str(rel))
            continue

        # Shared infrastructure invalidates any selection.
        if name in {"conftest", "__init__"} or rel.name in {"pytest.ini"}:
            complete = False
            continue

        # Convention: tools/foo.py -> tests/test_foo.py
        for root in test_roots:
            direct = root / f"test_{name}.py"
            if direct.exists():
                tests.add(str(direct.relative_to(ROOT)))

        # Reverse dependency: any test importing the changed module.
        module = str(rel.with_suffix("")).replace(os.sep, ".")
        pattern = re.compile(
            rf"^\s*(from|import)\s+({re.escape(module)}|{re.escape(name)})\b", re.M
        )
        for root in test_roots:
            if not root.exists():
                continue
            for candidate in root.rglob("test_*.py"):
                try:
                    if pattern.search(candidate.read_text(encoding="utf-8", errors="ignore")):
                        tests.add(str(candidate.relative_to(ROOT)))
                except OSError:
                    pass

    return sorted(tests), complete


# --------------------------------------------------------------------------
# Result cache
# --------------------------------------------------------------------------


def cache_read() -> dict:
    try:
        return json.loads(CACHE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def cache_write(tier: str, fingerprint: str, ok: bool, seconds: float, cpu: float) -> None:
    data = cache_read()
    data[tier] = {
        "fingerprint": fingerprint,
        "ok": ok,
        "seconds": round(seconds, 2),
        "cpu": round(cpu, 2),
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


# --------------------------------------------------------------------------
# Tiers
# --------------------------------------------------------------------------


@dataclass
class Result:
    ok: bool
    seconds: float      # wall clock, for the human reading the output
    cpu: float          # CPU time, for the budget contract
    detail: str


def tier_smoke() -> Result:
    changed = changed_files()
    tests, complete = affected_tests(changed)
    if not tests:
        if any(p.suffix == ".py" for p in changed) and not complete:
            return tier_unit()
        return Result(True, 0.0, 0.0, "no affected Python tests")
    wall, cpu, (code, out) = measured(
        lambda: run(
            [python(), "-m", "pytest", "-q", "--no-header", "-x", *tests],
            timeout=600,
        )
    )
    return Result(code == 0, wall, cpu, tail(out))


def tier_unit() -> Result:
    wall, cpu, (code, out) = measured(
        lambda: run(
            [python(), "-m", "pytest", "-q", "--no-header", "-m", "not sim"],
            timeout=1800,
        )
    )
    return Result(code == 0, wall, cpu, tail(out))


def tier_integration() -> Result:
    w0, c0 = time.monotonic(), child_cpu()
    unit = tier_unit()
    parts = [f"pytest: {unit.detail}"]
    ok = unit.ok

    for label, cmd in integration_gates():
        code, out = run(cmd, timeout=600)
        parts.append(f"{label}: {'ok' if code == 0 else 'FAIL'}")
        if code != 0:
            ok = False
            parts.append(tail(out))
    return Result(ok, time.monotonic() - w0, child_cpu() - c0, "\n".join(parts))


def integration_gates() -> list[tuple[str, list[str]]]:
    """The non-pytest checks the PR Gate enforces, reproduced locally.

    Kept in one place so the local gate and CI cannot drift apart.
    """
    gates: list[tuple[str, list[str]]] = []
    link = ROOT / "tools" / "idkgraph_link_check.py"
    if link.exists():
        gates.append(("markdown-links", [python(), str(ROOT / "scripts" / "check_links.py")]))
    for schema in sorted((ROOT / "schemas").glob("*.json")):
        gates.append((f"schema:{schema.name}", [python(), "-m", "json.tool", str(schema)]))
    return gates


def tier_nightly() -> Result:
    w0, c0 = time.monotonic(), child_cpu()
    integration = tier_integration()
    code, out = run([python(), "-m", "pytest", "-q", "--no-header", "-m", "sim"], timeout=None)
    sim_ok = code in (0, 5)  # 5 == no tests matched the marker
    return Result(
        integration.ok and sim_ok,
        time.monotonic() - w0,
        child_cpu() - c0,
        f"{integration.detail}\nsim: {tail(out)}",
    )


def tier_auto() -> tuple[str, Result]:
    """Cheapest tier that covers what changed — the mode hooks should use."""
    changed = changed_files()
    if not changed:
        return "none", Result(True, 0.0, 0.0, "working tree clean")
    if any(p.suffix == ".py" for p in changed):
        return "unit", tier_unit()
    if any(p.suffix in {".json", ".yml", ".yaml", ".md"} for p in changed):
        return "integration", tier_integration()
    return "none", Result(True, 0.0, 0.0, "no test-relevant change")


TIERS = {
    "smoke": tier_smoke,
    "unit": tier_unit,
    "integration": tier_integration,
    "nightly": tier_nightly,
}


def tail(text: str, lines: int = 12) -> str:
    kept = [line for line in text.strip().splitlines() if line.strip()]
    return "\n".join(kept[-lines:])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tier", choices=[*TIERS, "auto"], nargs="?", default="auto")
    parser.add_argument(
        "--no-cache", action="store_true", help="re-run even if this tree already passed"
    )
    parser.add_argument("--quiet", action="store_true", help="one summary line only")
    args = parser.parse_args()

    fingerprint = tree_fingerprint()
    tier = args.tier

    if not args.no_cache and tier != "auto":
        entry = cache_read().get(tier, {})
        if entry.get("fingerprint") == fingerprint and entry.get("ok"):
            print(f"[testkit] {tier}: cached pass ({entry.get('seconds')}s) — tree unchanged")
            return 0

    if tier == "auto":
        tier, result = tier_auto()
        if tier == "none":
            print(f"[testkit] {result.detail}; nothing to run")
            return 0
        entry = cache_read().get(tier, {})
        if not args.no_cache and entry.get("fingerprint") == fingerprint and entry.get("ok"):
            print(f"[testkit] {tier}: cached pass — tree unchanged")
            return 0
    else:
        result = TIERS[tier]()

    cache_write(tier, fingerprint, result.ok, result.seconds, result.cpu)

    budget = BUDGETS.get(tier)
    over = budget is not None and result.cpu > budget
    status = "PASS" if result.ok else "FAIL"
    detail = f"{result.seconds:.1f}s wall / {result.cpu:.1f}s cpu"
    print(
        f"[testkit] {tier}: {status} in {detail}"
        + (f" (budget {budget:.0f} cpu-s)" if budget else "")
    )

    if not args.quiet and result.detail:
        print(result.detail)

    if over:
        print(
            f"[testkit] BUDGET EXCEEDED: {tier} used {result.cpu:.1f} CPU-seconds "
            f"against a {budget:.0f} CPU-second ceiling.\n"
            f"           Profile with: pytest --durations=25\n"
            f"           Then mark the worst offenders `sim` or `slow` and move them "
            f"to a later tier — do not raise the budget.",
            file=sys.stderr,
        )

    # A blown budget fails the gate: that is the only mechanism that reliably
    # stops a fast suite from decaying into a slow one.
    return 0 if (result.ok and not over) else 1


if __name__ == "__main__":
    sys.exit(main())
