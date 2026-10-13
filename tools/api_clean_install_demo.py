#!/usr/bin/env python3
"""Clean-install and reproducible-demo check for the IDKMesh API (issue #747).

The beta release gate requires "clean install and reproducible demo". This tool
performs one, end to end, in a throwaway directory:

1. stage the installable files (``pyproject.toml``, ``README.md``, ``LICENSE``,
   ``idkmesh/``) and **build a wheel** from that copy, so the working tree is
   never touched;
2. create a **fresh virtual environment** and install only that wheel, with no
   index and no dependencies (the package is dependency-free by design);
3. from a different working directory, in isolated mode, confirm ``idkmesh``
   imports from the new environment's ``site-packages`` and not from this
   checkout, and that the ``idkmesh`` entry point answers ``--help``;
4. start the **installed** ``idkmesh control-tower`` on a free loopback port with
   a session token;
5. run a short client demo against it with the installed Python client: read
   ``/api/v1/status`` and have the server inspect the bundled sample run
   evidence report, verifying the snapshot digest;
6. run the **same demo** from this source tree against a source-tree server and
   require the two transcripts to be byte-identical -- the installed package
   behaves exactly like the source it was built from.

The transcript contains only stable fields (kind, API version, capabilities,
snapshot digest), never request ids or timestamps, so equality is meaningful.

Step 1 needs ``setuptools`` (fetched into pip's build environment) and so
network access to a package index unless one is already cached. When the build
environment itself cannot be created, the run is reported as *could not run*
(exit 2) rather than as a failure of the package.

Exit codes: 0 every step passed, 1 a step failed, 2 the environment could not
build or install (see the report), no verdict on the package.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_SCHEMA = "idkmesh-api-clean-install-demo/v1"
STAGED = ("pyproject.toml", "README.md", "LICENSE")
TOKEN = "clean-install-demo-token-" + "0" * 16
STARTUP_TIMEOUT_S = 20.0
STEP_TIMEOUT_S = 180
URL_PATTERN = re.compile(r"IDKMesh Control Tower: http://127\.0\.0\.1:(\d+)/")

# Identical code runs against both servers; only stable fields are printed.
DEMO_SCRIPT = """
import json, sys
from idkmesh.api_client import ControlTowerClient
from idkmesh.control_tower_ui import SAMPLE_REPORT

client = ControlTowerClient(sys.argv[1], sys.argv[2], timeout=10)
status = client.status()
inspected = client.inspect_run_evidence(json.loads(SAMPLE_REPORT))
print(json.dumps({
    "status_kind": status.value["kind"],
    "api_version": status.value["api_version"],
    "capabilities": status.value.get("capabilities"),
    "snapshot_digest": inspected.value["snapshot_digest"],
    "request_ids_present": bool(status.request_id and inspected.request_id),
}, sort_keys=True))
"""


class EnvironmentUnavailable(RuntimeError):
    """The machine could not build or install; says nothing about the package."""


class StepFailed(RuntimeError):
    """A step ran and the package did not behave as required."""


def _run(argv: Sequence[str], *, cwd: Path, env: dict[str, str] | None = None,
         timeout: int = STEP_TIMEOUT_S) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(argv), cwd=cwd, env=env, capture_output=True, text=True,
            errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EnvironmentUnavailable(f"could not run {argv[0]}: {exc}") from exc


def _tail(text: str, lines: int = 8) -> str:
    return "\n".join([line for line in text.splitlines() if line.strip()][-lines:])


def wheel_build_problem(
    built: subprocess.CompletedProcess[str], dist: Path,
) -> str | None:
    """Why no installable ``idkmesh`` wheel exists, or ``None`` when one does.

    Distinguishes a failed build from a build that exits 0 while producing the
    wrong wheel (an old pip can silently emit ``UNKNOWN-0.0.0`` from a valid
    ``pyproject.toml``). The message is release evidence and always carries the
    exit code, what actually appeared in the wheel directory, and the build's
    own output -- never an empty string.
    """
    produced = sorted(path.name for path in dist.glob("*.whl"))
    if built.returncode == 0 and any(name.startswith("idkmesh-") for name in produced):
        return None
    detail = _tail(built.stderr or built.stdout) or "(the build printed nothing)"
    if built.returncode != 0:
        return f"wheel build failed (exit {built.returncode}): {detail}"
    found = ", ".join(produced) or "no wheels at all"
    return f"wheel build produced no idkmesh-*.whl (found: {found}): {detail}"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stage_source(root: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    for name in STAGED:
        source = root / name
        if source.exists():
            shutil.copy2(source, destination / name)
    shutil.copytree(
        root / "idkmesh", destination / "idkmesh",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python"
    )


def venv_script(venv: Path, name: str) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin") / (
        name + (".exe" if os.name == "nt" else "")
    )


def run_demo(python: Sequence[str], base_url: str, *, cwd: Path,
             env: dict[str, str] | None = None) -> dict[str, Any]:
    done = _run([*python, "-c", DEMO_SCRIPT, base_url, TOKEN], cwd=cwd, env=env, timeout=60)
    if done.returncode != 0:
        raise StepFailed(f"demo client failed: {_tail(done.stderr or done.stdout)}")
    try:
        return json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise StepFailed(f"demo client printed no transcript: {_tail(done.stdout)}") from exc


def start_installed_server(venv: Path, workdir: Path) -> tuple[subprocess.Popen[str], int]:
    env = {**os.environ, "IDKMESH_CONTROL_TOWER_TOKEN": TOKEN, "PYTHONUNBUFFERED": "1"}
    env.pop("PYTHONPATH", None)
    process = subprocess.Popen(
        [str(venv_script(venv, "idkmesh")), "control-tower", "--no-browser", "--port", "0"],
        cwd=workdir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    seen = []
    assert process.stdout is not None
    while time.monotonic() < deadline:
        line = process.stdout.readline()
        if not line:
            if process.poll() is not None:
                break
            continue
        seen.append(line)
        match = URL_PATTERN.search(line)
        if match:
            return process, int(match.group(1))
    process.kill()
    raise StepFailed("installed server did not announce a URL: " + _tail("".join(seen)))


def demo(root: Path = REPO_ROOT) -> dict[str, Any]:
    from idkmesh.control_tower_ui import TOKEN_ENV, create_server  # source tree

    steps: list[dict[str, Any]] = []

    def record(name: str, detail: str = "") -> None:
        steps.append({"step": name, "status": "passed", "detail": detail})

    report: dict[str, Any] = {"schema": REPORT_SCHEMA, "steps": steps}
    with tempfile.TemporaryDirectory(prefix="idkmesh-clean-install-") as tmp:
        work = Path(tmp)
        process: subprocess.Popen[str] | None = None
        try:
            stage_source(root, work / "src")
            built = _run(
                [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(work / "dist"), "."],
                cwd=work / "src",
            )
            problem = wheel_build_problem(built, work / "dist")
            if problem is not None:
                raise EnvironmentUnavailable(problem)
            wheels = sorted((work / "dist").glob("idkmesh-*.whl"))
            record("wheel-builds", wheels[0].name)

            venv = work / "venv"
            made = _run([sys.executable, "-m", "venv", str(venv)], cwd=work)
            if made.returncode != 0:
                raise EnvironmentUnavailable("venv creation failed: " + _tail(made.stderr))
            installed = _run(
                [str(venv_python(venv)), "-m", "pip", "install", "--no-deps", "--no-index",
                 "--disable-pip-version-check", "-q", str(wheels[0])],
                cwd=work,
            )
            if installed.returncode != 0:
                raise EnvironmentUnavailable("wheel install failed: " + _tail(installed.stderr))
            record("fresh-venv-install", "wheel only, no index, no dependencies")

            outside = work / "elsewhere"
            outside.mkdir()
            probe = _run(
                [str(venv_python(venv)), "-I", "-c",
                 "import idkmesh,sys;print(idkmesh.__file__)"],
                cwd=outside,
            )
            location = Path(probe.stdout.strip()) if probe.returncode == 0 else None
            if location is None or not location.resolve().is_relative_to(venv.resolve()):
                raise StepFailed(f"idkmesh did not import from the new environment: {probe.stdout or probe.stderr}")
            record("imports-from-site-packages", str(location.relative_to(work)))

            for command in (["--help"], ["control-tower", "--help"]):
                helped = _run([str(venv_script(venv, "idkmesh")), *command], cwd=outside)
                if helped.returncode != 0 or "usage:" not in helped.stdout:
                    raise StepFailed(f"`idkmesh {' '.join(command)}` failed: {_tail(helped.stderr)}")
            record("entry-point-help", "idkmesh --help, idkmesh control-tower --help")

            process, port = start_installed_server(venv, outside)
            record("installed-server-starts", f"127.0.0.1:{port}")
            installed_transcript = run_demo(
                [str(venv_python(venv)), "-I"], f"http://127.0.0.1:{port}", cwd=outside
            )
            record("installed-client-demo", installed_transcript["snapshot_digest"])

            os.environ[TOKEN_ENV] = TOKEN
            server = create_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                env = {**os.environ, "PYTHONPATH": str(root)}
                source_transcript = run_demo(
                    [sys.executable], f"http://127.0.0.1:{server.server_port}", cwd=root, env=env
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
                os.environ.pop(TOKEN_ENV, None)
            record("source-client-demo", source_transcript["snapshot_digest"])

            if installed_transcript != source_transcript:
                raise StepFailed(
                    "installed and source transcripts differ: "
                    f"{installed_transcript} != {source_transcript}"
                )
            report["transcript"] = installed_transcript
            record("installed-equals-source", "byte-identical stable transcript")
            report["verdict"] = "pass"
        except EnvironmentUnavailable as exc:
            report.update(verdict="could-not-run", error=str(exc))
        except StepFailed as exc:
            steps.append({"step": "failure", "status": "failed", "detail": str(exc)})
            report.update(verdict="fail", error=str(exc))
        finally:
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
    return report


def render(report: dict[str, Any]) -> str:
    lines = [f"API clean-install demo: {report['verdict'].upper()}"]
    for step in report["steps"]:
        lines.append(f"  {step['status']:<7} {step['step']:<28} {step['detail']}".rstrip())
    if report.get("error"):
        lines.append(f"  error: {report['error']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    parser.add_argument("--root", default=str(REPO_ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not (root / "idkmesh").is_dir() or not (root / "pyproject.toml").exists():
        print(f"error: {root} does not look like the repository root", file=sys.stderr)
        return 2
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    report = demo(root)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render(report))
    return {"pass": 0, "fail": 1}.get(report["verdict"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
