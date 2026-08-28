#!/usr/bin/env python3
"""Diagnostic-only positive runtime probe for the frozen node acceptance job.

This intentionally exits zero after printing the frozen candidate's worker
result and captured task logs so evaluator failures can be distinguished from
worker/runtime failures. It has no acceptance or repository-write authority.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

FROZEN = "cbd40c43497ae4feb3a4a5e410dc78766b6cb19c"


def read_if_exists(path: Path) -> str | None:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else None


def main() -> int:
    candidate = Path(sys.argv[1]).resolve()
    actual = subprocess.check_output(["git", "-C", str(candidate), "rev-parse", "HEAD"], text=True).strip()
    if actual != FROZEN:
        print(json.dumps({"error": "candidate-sha-drift", "actual": actual, "expected": FROZEN}, indent=2))
        return 0

    with tempfile.TemporaryDirectory(prefix="idkmesh-positive-probe-") as raw:
        root = Path(raw)
        home = root / "home"
        home.mkdir()
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / "xdg"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
            "PYTHONPATH": str(candidate / "node" / "src"),
            "PYTHONUNBUFFERED": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
        Path(env["XDG_CONFIG_HOME"]).mkdir(parents=True, exist_ok=True)
        fixture = candidate / "node" / "examples" / "work-unit.canonical-smoke.json"
        output = root / "output"
        proc = subprocess.run(
            [sys.executable, "-m", "idkmesh_node", "run", str(fixture), "--output", str(output)],
            cwd=candidate,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        result_path = output / "result-manifest.json"
        payload = {
            "returncode": proc.returncode,
            "cli_stdout": proc.stdout,
            "cli_stderr": proc.stderr,
            "task_stdout": read_if_exists(output / "stdout.txt"),
            "task_stderr": read_if_exists(output / "stderr.txt"),
            "changes_patch": read_if_exists(output / "changes.patch"),
            "result_manifest": json.loads(result_path.read_text()) if result_path.exists() else None,
        }
        print("IDKMESH_POSITIVE_PROBE_BEGIN")
        print(json.dumps(payload, indent=2, sort_keys=True))
        print("IDKMESH_POSITIVE_PROBE_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
