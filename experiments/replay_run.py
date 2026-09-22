#!/usr/bin/env python3
"""Replay a saved two-attempt orchestration run and confirm it reproduces.

This closes a real gap in the R1 local-product loop (see ``ROADMAP.md`` S4):
``experiments/two_attempt_orchestrator.py`` + ``experiments/run_evidence_report.py``
already produce a real, saved WorkUnit -> two isolated attempts -> independent
verification -> evidence report run. Nothing previously replayed one of those
*saved* runs end to end and confirmed, field by field, that it reproduces.

``experiments/run_evidence_report.py`` already ships a ``replay-check`` command
(``compare_replay``) that re-runs a config and compares the *complete*
orchestration run record by digest. That check is sound for the orchestration
run record and the evidence report built from it, because both are
deliberately built to be free of wall-clock/environment fields (see
"Field classification" below). It is not, on its own, a general-purpose
saved-run replay tool: it (a) requires the caller to already know and supply
the original config path separately from the saved run record -- nothing in
a saved ``idkmesh-two-attempt-run`` records which config produced it -- and
(b) has no notion of a raw, unprojected ``VerificationResult`` artifact, which
*does* carry genuinely non-deterministic fields (timestamps, wall-clock
duration, interpreter/platform strings) that a byte-equality check would
wrongly flag as drift.

This module adds two things on top of that existing machinery, without
modifying it:

1. ``capture``: run one orchestration config through the real orchestrator and
   evidence-report pipeline, and save a self-describing bundle under
   ``results/`` that a replay tool can act on *without* being told the
   original config path out of band (a ``replay-source.json`` manifest records
   it). It also captures the raw, unprojected ``VerificationResult`` for every
   attempt that reached verification, which the orchestration run record
   deliberately does not retain in full.

2. ``replay``: given the path to any file in a captured bundle (the
   ``replay-source.json`` manifest, the run record, or the evidence report),
   re-run the exact same config against the exact same fixtures and compare
   the result to the saved bundle -- correctly partitioned into fields that
   MUST match exactly and fields that are EXPECTED TO VARY run to run. See
   "Field classification" below for the justification, field by field. Exits
   non-zero with an itemized diff on any must-match divergence.

Field classification
=====================

The saved orchestration run record (``idkmesh-two-attempt-run``, produced by
``two_attempt_orchestrator.orchestrate``) and the evidence report built from it
(``idkmesh-run-evidence-report``, produced by
``run_evidence_report.build_report``) are held to MUST-MATCH, full-document
equality on replay. This is not an assumption; it follows from reading the
producer code:

* ``two_attempt_orchestrator._verification_record`` projects a full
  ``VerificationResult`` down to
  ``id / verifier_id / status / recommendation / checks[].{id,status,required}
  / semantic_digest / work_unit_digest / result_manifest_digest`` before it is
  ever stored in the run record. None of those fields are timestamps, wall
  durations, hostnames, or interpreter versions.
* ``semantic_digest`` is ``canonical_digest(local_verifier.semantic_signature(...))``,
  and ``local_verifier.semantic_signature`` (``experiments/local_verifier.py``)
  itself keeps only ``status``, ``checks`` (id/status/evidence ids), ``evidence``
  (id/digest), and ``recommendation`` -- again nothing wall-clock- or
  environment-dependent.
* ``two_attempt_orchestrator._result_manifest_record`` projects a worker
  ``ResultManifest`` down to ``id / attempt / worker_id / worker_status /
  digest`` -- also free of anything that varies run to run for a *fixture*
  ResultManifest (the fixtures under ``examples/`` are static files, not
  something generated fresh at run time).
* ``run_evidence_report.build_report`` derives the evidence report purely from
  the orchestration run record (``source_run_digest``, ``summary`` counts,
  ``warnings``, per-attempt projections of the same fields above); the
  ``run-evidence-report-v0.1`` schema (``schemas/run-evidence-report-v0.1.schema.json``)
  has no timestamp/duration/environment property at all.

So a saved run record or evidence report is expected to be byte-identical on
replay given the same config and fixtures, and this tool treats any
divergence there as a real regression, not noise.

The *raw*, unprojected ``VerificationResult`` this tool additionally captures
per attempt (via ``local_verifier.run_fixture`` / ``evaluator_plan_runner.run_fixture``,
the same functions the orchestrator calls internally) is a different story.
Reading the verifier backends that produce it:

* ``local_verifier.utc_now()`` (``datetime.now(timezone.utc)``) is called to
  set ``started_at`` and ``finished_at`` -- real wall-clock time, different on
  every invocation (``experiments/local_verifier.py``, the JSON-fixture and
  unified-diff backends).
* ``resources.wall_seconds`` is ``time.monotonic()`` elapsed between those two
  calls -- depends on machine load/speed, not on the candidate.
* ``provenance.environment.platform`` / ``.python`` are
  ``platform.platform()`` / ``platform.python_version()`` -- depends on which
  machine/interpreter ran the replay (this repository's own gate runs both
  Python 3.11 and 3.13; see ``AGENTS.md``).

Those four leaves are the EXPECTED-TO-VARY set for a raw ``VerificationResult``
sidecar: this tool asserts they are *present* (their absence would itself be a
real regression) but does not compare their values. Every other field --
``status``, ``decision_support``, ``checks``, ``evidence``, ``findings``,
``metrics``, ``provenance.{result_manifest_digest,work_unit_digest,
source_revision,verifier_config_digest}``, ``self_report``, ``worker``,
``work_unit_id`` / ``work_unit_version``, ``extensions`` -- is content derived
from the static WorkUnit/ResultManifest/policy/plan inputs and MUST match
exactly; a divergence there means the candidate was verified differently, not
that a clock ticked.

This tool has no candidate-execution, write, merge, or selection authority. It
only reads saved evidence, re-runs the same replayable fixtures, and reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import evaluator_plan_runner
import local_verifier
from local_verifier import VerifierError, load_json, resolve_output_path, resolve_repo_path
from provenance_integrity import canonical_digest
from run_evidence_report import (
    EvidenceReportError,
    build_report,
    render_markdown,
    validate_report,
    validate_run_record,
)
from two_attempt_orchestrator import OrchestratorError, run_config

ROOT = Path(__file__).resolve().parents[1]
REPLAY_SOURCE_KIND = "idkmesh-replay-source"
REPLAY_SOURCE_VERSION = "0.1"

# Dict-path tuples (as returned by json navigation) inside a raw
# VerificationResult that are expected to differ on every replay. See the
# module docstring "Field classification" section for the line-by-line
# justification of each entry.
VOLATILE_VERIFICATION_RESULT_PATHS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("started_at",),
        ("finished_at",),
        ("resources", "wall_seconds"),
        ("provenance", "environment", "platform"),
        ("provenance", "environment", "python"),
    }
)


class ReplayError(RuntimeError):
    """Raised for invalid replay bundles or comparison inputs."""


@dataclass
class FieldDiff:
    path: str
    saved: Any
    replayed: Any


@dataclass
class ComparisonResult:
    label: str
    must_match_diffs: list[FieldDiff] = field(default_factory=list)
    ignored_but_missing: list[str] = field(default_factory=list)
    ignored_present: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.must_match_diffs and not self.ignored_but_missing


def _path_str(path: tuple[Any, ...]) -> str:
    return "$" + "".join(f"[{part!r}]" if isinstance(part, str) else f"[{part}]" for part in path)


def _diff_values(
    saved: Any,
    replayed: Any,
    path: tuple[Any, ...],
    ignore: frozenset[tuple[str, ...]],
    out: list[FieldDiff],
    ignored_present: list[str],
    ignored_but_missing: list[str],
) -> None:
    """Recursively compare two JSON-ish values, honoring `ignore` leaf paths."""

    str_path = tuple(part for part in path if isinstance(part, str))
    if str_path in ignore:
        missing = saved is _MISSING or replayed is _MISSING
        if missing:
            ignored_but_missing.append(_path_str(path))
        else:
            ignored_present.append(_path_str(path))
        return

    if isinstance(saved, dict) and isinstance(replayed, dict):
        for key in sorted(set(saved) | set(replayed)):
            _diff_values(
                saved.get(key, _MISSING),
                replayed.get(key, _MISSING),
                path + (key,),
                ignore,
                out,
                ignored_present,
                ignored_but_missing,
            )
        return

    if isinstance(saved, list) and isinstance(replayed, list):
        if len(saved) != len(replayed):
            out.append(FieldDiff(_path_str(path + ("<length>",)), len(saved), len(replayed)))
            return
        for index, (saved_item, replayed_item) in enumerate(zip(saved, replayed)):
            _diff_values(
                saved_item,
                replayed_item,
                path + (index,),
                ignore,
                out,
                ignored_present,
                ignored_but_missing,
            )
        return

    if saved != replayed:
        out.append(FieldDiff(_path_str(path), saved, replayed))


class _Missing:
    def __repr__(self) -> str:
        return "<missing>"


_MISSING = _Missing()


def compare_documents(
    label: str,
    saved: dict[str, Any],
    replayed: dict[str, Any],
    *,
    ignore: frozenset[tuple[str, ...]] = frozenset(),
) -> ComparisonResult:
    diffs: list[FieldDiff] = []
    ignored_present: list[str] = []
    ignored_but_missing: list[str] = []
    _diff_values(saved, replayed, (), ignore, diffs, ignored_present, ignored_but_missing)
    return ComparisonResult(
        label=label,
        must_match_diffs=diffs,
        ignored_but_missing=ignored_but_missing,
        ignored_present=ignored_present,
    )


# --------------------------------------------------------------------------
# Config-driven raw VerificationResult recomputation
# --------------------------------------------------------------------------


def _raw_verify(
    config: dict[str, Any],
    work_unit_path: Path,
    attempt_spec: dict[str, Any],
) -> dict[str, Any] | None:
    """Recompute the unprojected VerificationResult for one attempt spec.

    Mirrors the dispatch in ``two_attempt_orchestrator._verification_control``:
    exactly one of ``evaluator_plan`` / ``verifier_policy`` is present on the
    config, and it selects the backend. Returns ``None`` when the attempt has
    no result_manifest/candidate_root to verify (e.g. a `fixture-failure`
    worker adapter never reaches verification).
    """

    if "result_manifest" not in attempt_spec or "candidate_root" not in attempt_spec:
        return None

    result_manifest_path = resolve_repo_path(attempt_spec["result_manifest"])
    candidate_root = resolve_repo_path(attempt_spec["candidate_root"])

    if "evaluator_plan" in config:
        plan_path = resolve_repo_path(config["evaluator_plan"])
        return evaluator_plan_runner.run_fixture(
            work_unit_path=work_unit_path,
            result_manifest_path=result_manifest_path,
            candidate_root=candidate_root,
            plan_path=plan_path,
        )

    policy_path = resolve_repo_path(config["verifier_policy"])
    return local_verifier.run_fixture(
        work_unit_path=work_unit_path,
        result_manifest_path=result_manifest_path,
        candidate_root=candidate_root,
        policy_path=policy_path,
    )


def _verification_sidecar_name(attempt_id: str) -> str:
    return f"verification-result-{attempt_id}.json"


# --------------------------------------------------------------------------
# capture
# --------------------------------------------------------------------------


def capture_bundle(config_path: Path, output_dir: Path) -> dict[str, Any]:
    """Run one orchestration config for real and save a replayable bundle.

    Writes, under `output_dir` (which must resolve under `results/`):
      - run-record.json        (idkmesh-two-attempt-run)
      - evidence-report.json   (idkmesh-run-evidence-report)
      - evidence-report.md
      - verification-result-<attempt_id>.json for every attempt that reached
        verification (raw, unprojected VerificationResult)
      - replay-source.json     (manifest this tool's `replay` command reads)

    Returns the manifest dict that was written to replay-source.json.
    """

    config = load_json(config_path)
    record = run_config(config_path)
    report = build_report(record)

    # Fail closed before writing anything if the caller asked for an output
    # directory outside the non-canonical results/ subtree.
    resolve_output_path(output_dir.relative_to(ROOT).as_posix() + "/_probe")
    output_dir.mkdir(parents=True, exist_ok=True)

    run_record_path = output_dir / "run-record.json"
    evidence_report_json_path = output_dir / "evidence-report.json"
    evidence_report_md_path = output_dir / "evidence-report.md"
    _write_json(run_record_path, record)
    _write_json(evidence_report_json_path, report)
    _write_text(evidence_report_md_path, render_markdown(report))

    work_unit_path = resolve_repo_path(config["work_unit"])
    verification_results: dict[str, str | None] = {}
    for attempt_spec in config["attempts"]:
        attempt_id = attempt_spec["attempt_id"]
        raw = _raw_verify(config, work_unit_path, attempt_spec)
        if raw is None:
            verification_results[attempt_id] = None
            continue
        sidecar_name = _verification_sidecar_name(attempt_id)
        _write_json(output_dir / sidecar_name, raw)
        verification_results[attempt_id] = sidecar_name

    # Artifacts this tool wrote itself are addressed by filename, relative to
    # the bundle directory the manifest lives in (not the repository root), so
    # a captured bundle stays self-describing if it is copied or moved as a
    # unit -- e.g. for the deliberately-corrupted negative-test fixture in
    # tests/test_replay_run.py, or for a human archiving one run's evidence.
    # `config` is the one exception: it deliberately points *out* of the
    # bundle at the (repo-relative) orchestration config that produced it,
    # since that config is shared, reusable input, not part of this run's
    # saved output.
    manifest = {
        "schema_version": REPLAY_SOURCE_VERSION,
        "kind": REPLAY_SOURCE_KIND,
        "config": config_path.relative_to(ROOT).as_posix(),
        "config_digest": canonical_digest(config),
        "run_record": run_record_path.name,
        "evidence_report_json": evidence_report_json_path.name,
        "evidence_report_markdown": evidence_report_md_path.name,
        "verification_results": verification_results,
    }
    _write_json(output_dir / "replay-source.json", manifest)
    return manifest


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------


def _load_manifest(given_path: Path) -> tuple[Path, dict[str, Any]]:
    """Resolve a bundle directory + manifest from any file inside the bundle."""

    given_path = given_path.resolve()
    if given_path.name == "replay-source.json":
        manifest_path = given_path
    else:
        manifest_path = given_path.parent / "replay-source.json"
    if not manifest_path.is_file():
        raise ReplayError(
            f"{given_path} is not part of a captured replay bundle "
            f"(expected {manifest_path} to exist; run `capture` first)"
        )
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != REPLAY_SOURCE_VERSION or manifest.get("kind") != REPLAY_SOURCE_KIND:
        raise ReplayError(f"{manifest_path} is not a recognized replay-source manifest")
    return manifest_path.parent, manifest


@dataclass
class ReplayReport:
    run_id: str
    config: str
    config_drifted: bool
    comparisons: list[ComparisonResult]

    @property
    def ok(self) -> bool:
        return not self.config_drifted and all(c.ok for c in self.comparisons)


def replay_bundle(bundle_path: Path) -> ReplayReport:
    bundle_dir, manifest = _load_manifest(bundle_path)
    config_path = resolve_repo_path(manifest["config"])
    config = load_json(config_path)
    config_digest = canonical_digest(config)
    config_drifted = config_digest != manifest["config_digest"]

    comparisons: list[ComparisonResult] = []
    saved_record = load_json(bundle_dir / manifest["run_record"])

    if not config_drifted:
        replayed_record = run_config(config_path)
        validate_run_record(replayed_record)
        comparisons.append(compare_documents("run-record", saved_record, replayed_record))

        replayed_report = build_report(replayed_record)
        validate_report(replayed_report)
        saved_report = load_json(bundle_dir / manifest["evidence_report_json"])
        comparisons.append(compare_documents("evidence-report", saved_report, replayed_report))

        work_unit_path = resolve_repo_path(config["work_unit"])
        attempts_by_id = {spec["attempt_id"]: spec for spec in config["attempts"]}
        for attempt_id, sidecar_name in manifest["verification_results"].items():
            if sidecar_name is None:
                continue
            if attempt_id not in attempts_by_id:
                raise ReplayError(
                    f"replay-source.json references attempt {attempt_id!r}, which the "
                    f"config {manifest['config']} does not define"
                )
            saved_verification = load_json(bundle_dir / sidecar_name)
            replayed_verification = _raw_verify(config, work_unit_path, attempts_by_id[attempt_id])
            if replayed_verification is None:
                raise ReplayError(
                    f"attempt {attempt_id} had a saved VerificationResult but the config no "
                    "longer resolves one on replay"
                )
            comparisons.append(
                compare_documents(
                    f"verification-result[{attempt_id}]",
                    saved_verification,
                    replayed_verification,
                    ignore=VOLATILE_VERIFICATION_RESULT_PATHS,
                )
            )

    return ReplayReport(
        run_id=saved_record.get("run_id", "<unknown>"),
        config=manifest["config"],
        config_drifted=config_drifted,
        comparisons=comparisons,
    )


def _format_diff(diff: FieldDiff) -> str:
    return f"    {diff.path}: saved={diff.saved!r} replayed={diff.replayed!r}"


def format_report(report: ReplayReport) -> str:
    lines = [f"replay of run_id={report.run_id!r} (config={report.config})"]
    if report.config_drifted:
        lines.append(
            "  FAIL: the orchestration config on disk no longer matches the digest "
            "recorded at capture time; this is not a replay of the same bounded task"
        )
        return "\n".join(lines)

    for comparison in report.comparisons:
        status = "OK" if comparison.ok else "FAIL"
        lines.append(f"  [{status}] {comparison.label}")
        for missing in comparison.ignored_but_missing:
            lines.append(f"    {missing}: expected-to-vary field missing in saved or replayed document")
        for diff in comparison.must_match_diffs:
            lines.append(_format_diff(diff))
        if comparison.ignored_present:
            lines.append(
                f"    ({len(comparison.ignored_present)} expected-to-vary field(s) present and "
                "not compared: " + ", ".join(comparison.ignored_present) + ")"
            )
    lines.append("PASS: replay reproduced every must-match field" if report.ok else "FAIL: replay diverged (see above)")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def cmd_capture(args: argparse.Namespace) -> int:
    config_path = resolve_repo_path(args.config)
    output_dir = resolve_repo_path(args.output_dir)
    manifest = capture_bundle(config_path, output_dir)
    print(f"captured replay bundle for {manifest['config']} under {output_dir.relative_to(ROOT)}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    bundle_path = resolve_repo_path(args.bundle)
    report = replay_bundle(bundle_path)
    print(format_report(report))
    return 0 if report.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser(
        "capture",
        help="Run one orchestration config for real and save a replayable bundle under results/.",
    )
    capture.add_argument("--config", required=True)
    capture.add_argument(
        "--output-dir", required=True, help="Repository-relative directory under results/."
    )
    capture.set_defaults(func=cmd_capture)

    replay = subparsers.add_parser(
        "replay",
        help=(
            "Replay a captured bundle and compare, field by field, must-match vs "
            "expected-to-vary evidence."
        ),
    )
    replay.add_argument(
        "--bundle",
        required=True,
        help=(
            "Repository-relative path to replay-source.json, run-record.json, or "
            "evidence-report.json inside a captured bundle."
        ),
    )
    replay.set_defaults(func=cmd_replay)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (
        ReplayError,
        OrchestratorError,
        EvidenceReportError,
        VerifierError,
        evaluator_plan_runner.EvaluatorPlanError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
