"""``idkmesh local-loop``: the R1 local product loop, wired end to end.

ROADMAP.md S4 ("R1 -- Finish one real local product loop") describes the
target experience as one runnable, explainable chain:

    bounded repository task -> WorkUnit -> two or more isolated attempts
    -> canonical candidate bundles -> independent verification
    -> evidence report -> exact replay -> human decision

Every stage of that chain already exists as real, tested code under
``experiments/``:

* ``experiments/two_attempt_orchestrator.py`` dispatches two isolated
  worker attempts against one WorkUnit and routes each through independent
  verification (``experiments/local_verifier.py`` or
  ``experiments/evaluator_plan_runner.py``);
* ``experiments/run_evidence_report.py`` turns one orchestration run into a
  non-selecting evidence report;
* ``experiments/replay_run.py`` captures a self-describing, replayable
  bundle of both of the above (plus the raw per-attempt
  ``VerificationResult`` evidence) and can later confirm it reproduces.

This module is the thin logic layer behind the ``idkmesh local-loop``
subcommand (``idkmesh/cli.py``), the same split ``gate-audit`` already uses
against ``idkmesh/gate_audit.py``. It validates one orchestration config and
its referenced WorkUnit, delegates the actual dispatch/verify/report/capture
work to ``experiments/replay_run.capture_bundle`` (which itself delegates to
the two modules above), and renders a human-readable summary that names the
produced evidence bundle and the next, deliberately manual, human-gated
steps: recording a decision (``experiments/record_human_decision.py``) and
confirming the run replays (``experiments/replay_run.py``).

The CLI verb is ``local-loop`` rather than ``run`` because ``idkmesh run``
already names an unrelated command (durable Product Spine run bookkeeping;
see ``idkmesh/cli.py``'s ``run create``/``run status``/``run cancel``) that
explicitly does not dispatch, verify, or accept anything. This module does
exactly that dispatch/verify work, so it needed its own verb.

``idkmesh local-loop`` never records a decision and never replays on its own
behalf -- ROADMAP.md's pipeline keeps ``-> human decision`` a separate,
human-gated step, and replay is a *confirmation* a human or CI job runs
against the bundle this command produces, not a thing this command does to
itself.

Unlike ``idkmesh/gate_audit.py``, this module is not stdlib-only. It needs:

1. a repository checkout. ``experiments/`` is a research tree deliberately
   NOT packaged into the installable ``idkmesh`` wheel (``pyproject.toml``
   ships only ``packages = ["idkmesh"]``; see
   ``docs/decisions/ADR-0012-optional-verification-dependency.md`` for why
   the line is drawn there). A real, non-editable ``pip install idkmesh``
   has no ``experiments/`` tree beside it, so ``idkmesh local-loop`` raises
   ``LocalLoopSetupError`` with that explained, rather than crash on a bare
   ``ModuleNotFoundError``.
2. the optional ``idkmesh[verify]`` extra (``jsonschema``), because real
   independent verification is real JSON Schema validation. If it is
   missing, importing ``experiments/local_verifier.py`` itself raises an
   ``ImportError`` with an actionable install message (see its module
   docstring); this module does not catch or reword that message, so the
   exact PR #554 wording reaches the caller unmodified.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

__all__ = [
    "LocalLoopError",
    "LocalLoopSetupError",
    "render_summary",
    "run_work_unit",
]


class LocalLoopSetupError(RuntimeError):
    """``idkmesh local-loop`` cannot operate in this environment (see module docstring)."""


class LocalLoopError(RuntimeError):
    """A user-fixable problem with the config, WorkUnit, or the run itself."""


def _find_experiments_dir() -> Path | None:
    """Locate this checkout's ``experiments/`` directory, or ``None``.

    Walks up from this file's own location rather than from the current
    working directory, so ``idkmesh local-loop`` behaves the same regardless
    of where it is invoked from. In an editable install or a
    ``PYTHONPATH=.`` checkout, ``idkmesh/local_loop.py``'s parent *is* the
    repository root and ``experiments/`` is found on the first step. In a
    real wheel install, the walk exhausts ``site-packages/.../`` without
    ever finding it, which is the correct answer: there is no
    ``experiments/`` to run.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "experiments"
        if (candidate / "two_attempt_orchestrator.py").is_file():
            return candidate
    return None


_experiments_cache: dict[str, Any] = {}


def _load_experiments() -> dict[str, Any]:
    """Import and cache the ``experiments/`` modules ``local-loop`` delegates to.

    Raises ``LocalLoopSetupError`` if this is not a repository checkout.
    Raises a bare ``ImportError`` -- unmodified -- if ``jsonschema`` (the
    ``verify`` extra) is not installed; ``experiments/local_verifier.py``
    crafts that message itself, so it is deliberately not caught or
    reworded here.
    """
    if _experiments_cache:
        return _experiments_cache

    experiments_dir = _find_experiments_dir()
    if experiments_dir is None:
        raise LocalLoopSetupError(
            "'idkmesh local-loop' orchestrates experiments/ tooling that is "
            "deliberately not packaged into the installable idkmesh wheel "
            "(pyproject.toml ships only the 'idkmesh' package -- see "
            "docs/decisions/ADR-0012-optional-verification-dependency.md for "
            "why). It only works from a repository checkout. Clone "
            "https://github.com/MSKazemi/idkmesh, then from the checkout "
            "root either run `pip install -e '.[verify]'` and use the "
            "installed 'idkmesh' entry point, or run "
            "`PYTHONPATH=. python -m idkmesh.cli local-loop ...` directly."
        )
    if str(experiments_dir) not in sys.path:
        sys.path.insert(0, str(experiments_dir))

    import evaluator_plan_runner
    import local_verifier
    import replay_run
    import run_evidence_report
    import two_attempt_orchestrator

    _experiments_cache.update(
        experiments_dir=experiments_dir,
        evaluator_plan_runner=evaluator_plan_runner,
        local_verifier=local_verifier,
        replay_run=replay_run,
        run_evidence_report=run_evidence_report,
        two_attempt_orchestrator=two_attempt_orchestrator,
    )
    return _experiments_cache


def _repo_root(modules: dict[str, Any]) -> Path:
    return modules["experiments_dir"].parent


def _default_output_dir(run_id: str) -> str:
    return f"results/idkmesh-local-loop/{run_id}"


def run_work_unit(config_path: str, output_dir: str | None = None) -> dict[str, Any]:
    """Run the R1 local product loop for one two-attempt orchestration config.

    Validates the config and its referenced WorkUnit, dispatches the two
    isolated attempts through the existing orchestrator, routes each through
    independent verification, and captures a self-describing, replayable
    evidence bundle (run record, evidence report JSON + Markdown, raw
    per-attempt VerificationResult evidence, and a replay manifest) under
    ``output_dir`` -- exactly ``experiments/replay_run.py capture``'s output,
    since that already is the full dispatch -> verify -> evidence -> replay
    chain this command exists to wire up.

    Returns a summary dict; never records a human decision and never
    replays on its own behalf, matching ROADMAP.md S4's pipeline. Raises
    ``LocalLoopSetupError`` / ``ImportError`` for environment problems (see
    module docstring) and ``LocalLoopError`` for anything wrong with the
    config, the WorkUnit, the requested output directory, or the run
    itself.
    """
    modules = _load_experiments()
    local_verifier = modules["local_verifier"]
    two_attempt_orchestrator = modules["two_attempt_orchestrator"]
    replay_run = modules["replay_run"]
    root = _repo_root(modules)

    known_errors = (
        local_verifier.VerifierError,
        two_attempt_orchestrator.OrchestratorError,
        two_attempt_orchestrator.WorkerAttemptError,
        modules["run_evidence_report"].EvidenceReportError,
        modules["evaluator_plan_runner"].EvaluatorPlanError,
        replay_run.ReplayError,
    )

    try:
        resolved_config_path = two_attempt_orchestrator.resolve_repo_path(config_path)
    except local_verifier.VerifierError as exc:
        raise LocalLoopError(str(exc)) from exc
    if not resolved_config_path.is_file():
        raise LocalLoopError(
            f"orchestration config not found: {config_path} "
            f"(resolved to {resolved_config_path})"
        )

    try:
        config = local_verifier.load_json(resolved_config_path)
        two_attempt_orchestrator.validate_config(config)
    except known_errors as exc:
        raise LocalLoopError(f"{config_path}: {exc}") from exc

    # Validate the referenced WorkUnit up front, against its own schema, so a
    # malformed WorkUnit fails with a WorkUnit-shaped error naming the
    # WorkUnit file, rather than surfacing only as an opaque
    # verification_error deep inside one attempt's run record.
    work_unit_ref = config["work_unit"]
    try:
        work_unit_path = two_attempt_orchestrator.resolve_repo_path(work_unit_ref)
        work_unit = local_verifier.load_json(work_unit_path)
        local_verifier.validate_schema(
            work_unit, local_verifier.WORK_UNIT_SCHEMA, "Work Unit"
        )
    except known_errors as exc:
        raise LocalLoopError(f"{work_unit_ref}: {exc}") from exc

    run_id = config["run_id"]
    output_dir_raw = output_dir or _default_output_dir(run_id)
    try:
        resolved_output_dir = two_attempt_orchestrator.resolve_output_path(output_dir_raw)
    except known_errors as exc:
        raise LocalLoopError(str(exc)) from exc

    if resolved_output_dir.exists() and any(resolved_output_dir.iterdir()):
        raise LocalLoopError(
            f"--output-dir {output_dir_raw} already exists and is not empty; "
            "idkmesh local-loop never overwrites a previous run's evidence "
            "bundle -- pass a different --output-dir"
        )

    try:
        manifest = replay_run.capture_bundle(resolved_config_path, resolved_output_dir)
    except known_errors as exc:
        raise LocalLoopError(str(exc)) from exc

    record = local_verifier.load_json(resolved_output_dir / manifest["run_record"])
    report = local_verifier.load_json(resolved_output_dir / manifest["evidence_report_json"])

    result = {
        "run_id": run_id,
        "config_path": resolved_config_path.relative_to(root).as_posix(),
        "work_unit": dict(record["work_unit"]),
        "output_dir": resolved_output_dir.relative_to(root).as_posix(),
        "manifest": manifest,
        "record": record,
        "report": report,
    }

    # Save the human-readable summary next to the rest of the evidence
    # bundle, in addition to printing it, so the next-step commands stay
    # discoverable without re-running `idkmesh local-loop`.
    next_steps_path = resolved_output_dir / "NEXT_STEPS.md"
    next_steps_path.write_text(render_summary(result) + "\n", encoding="utf-8")
    result["next_steps_path"] = next_steps_path.relative_to(root).as_posix()

    return result


def render_summary(result: dict[str, Any]) -> str:
    """Render the human-readable summary printed by ``idkmesh local-loop``
    and saved alongside the evidence bundle as ``NEXT_STEPS.md``.

    Names exactly two next, human-gated steps -- recording a decision and
    confirming replay -- with the commands to run them, and nothing this
    command did not itself do: it produces evidence, it does not decide or
    replay.
    """
    output_dir = result["output_dir"]
    manifest = result["manifest"]
    report = result["report"]
    summary = report["summary"]
    work_unit = result["work_unit"]

    evidence_report_json = f"{output_dir}/{manifest['evidence_report_json']}"
    evidence_report_md = f"{output_dir}/{manifest['evidence_report_markdown']}"
    replay_source = f"{output_dir}/replay-source.json"

    lines = [
        f"# idkmesh local-loop: {result['run_id']}",
        "",
        f"WorkUnit `{work_unit['id']}` v{work_unit['version']} "
        f"-> {summary['attempt_count']} isolated attempt(s) "
        f"-> independent verification -> evidence report.",
        "",
        f"- Supported: {summary['supported']}",
        f"- Rejected: {summary['rejected']}",
        f"- Inconclusive: {summary['inconclusive']}",
        f"- Control errors: {summary['control_errors']}",
        f"- Verification disagreement: "
        f"{'yes' if summary['verification_disagreement'] else 'no'}",
        "",
        "## Evidence bundle",
        "",
        f"- Evidence report (human-readable): `{evidence_report_md}`",
        f"- Evidence report (machine-readable): `{evidence_report_json}`",
        f"- Run record: `{output_dir}/{manifest['run_record']}`",
        f"- Replay manifest: `{replay_source}`",
    ]
    sidecars = [
        name for name in manifest["verification_results"].values() if name is not None
    ]
    for name in sidecars:
        lines.append(f"- Raw VerificationResult: `{output_dir}/{name}`")

    if report["warnings"]:
        lines += ["", "## Warnings", ""]
        lines += [f"- {warning}" for warning in report["warnings"]]

    lines += [
        "",
        "## Next steps (human-gated -- not run automatically)",
        "",
        "This report is decision support, not acceptance authority; nothing "
        "above selects, merges, or integrates a candidate. Two manual steps "
        "remain:",
        "",
        "1. Record a human integration decision against the evidence report:",
        "",
        "   ```bash",
        "   python experiments/record_human_decision.py record \\",
        f"     --evidence-report {evidence_report_json} \\",
        f"     --output {output_dir}/human-decision-record.json \\",
        f"     --decision-id {result['run_id']}.decision.001 \\",
        "     --decision {accept|reject|escalate} \\",
        "     --rationale \"<why>\" \\",
        "     --decider-id <your-id>",
        "   ```",
        "",
        "2. Confirm this run replays exactly (optional, but recommended "
        "before trusting the evidence long-term):",
        "",
        "   ```bash",
        f"   python experiments/replay_run.py replay --bundle {replay_source}",
        "   ```",
        "",
    ]
    return "\n".join(lines)
