#!/usr/bin/env python3
"""Cross-object provenance integrity checks for IDKMesh verification contracts.

JSON Schema validates each document's shape. This module validates relationships
that only become meaningful when a Work Unit, worker ResultManifest, and
independent VerificationResult are considered together.

It performs no task execution, network access, provider calls, or paid compute.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


class IntegrityError(RuntimeError):
    """Raised when declared provenance does not bind to the referenced objects."""


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise IntegrityError(f"{path} must contain a JSON object")
    return value


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def resolve_repo_path(raw: str) -> Path:
    path = (ROOT / raw).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise IntegrityError(f"path escapes repository root: {raw}") from exc
    return path


def validate_integrity(
    work_unit: dict[str, Any],
    worker_result: dict[str, Any],
    verification_result: dict[str, Any],
) -> dict[str, str]:
    """Validate cryptographic and lineage bindings across the three contracts."""

    if worker_result.get("work_unit_id") != work_unit.get("id"):
        raise IntegrityError("worker ResultManifest references a different Work Unit id")
    if worker_result.get("work_unit_version") != work_unit.get("version"):
        raise IntegrityError("worker ResultManifest references a different Work Unit version")

    work_unit_digest = canonical_digest(work_unit)
    declared_worker_work_unit_digest = worker_result.get("provenance", {}).get(
        "work_unit_digest"
    )
    if declared_worker_work_unit_digest != work_unit_digest:
        raise IntegrityError(
            "worker ResultManifest work_unit_digest mismatch: "
            f"expected {work_unit_digest}, got {declared_worker_work_unit_digest}"
        )

    if verification_result.get("result_manifest_id") != worker_result.get("id"):
        raise IntegrityError("VerificationResult references a different ResultManifest id")
    for field in ("work_unit_id", "work_unit_version", "attempt"):
        if verification_result.get(field) != worker_result.get(field):
            raise IntegrityError(
                f"VerificationResult {field} does not match worker ResultManifest"
            )

    worker_result_digest = canonical_digest(worker_result)
    verification_provenance = verification_result.get("provenance", {})
    if verification_provenance.get("result_manifest_digest") != worker_result_digest:
        raise IntegrityError(
            "VerificationResult result_manifest_digest mismatch: "
            f"expected {worker_result_digest}, got "
            f"{verification_provenance.get('result_manifest_digest')}"
        )
    if verification_provenance.get("work_unit_digest") != work_unit_digest:
        raise IntegrityError(
            "VerificationResult work_unit_digest mismatch: "
            f"expected {work_unit_digest}, got "
            f"{verification_provenance.get('work_unit_digest')}"
        )

    worker_source_revision = worker_result.get("provenance", {}).get("source_revision")
    if verification_provenance.get("source_revision") != worker_source_revision:
        raise IntegrityError(
            "VerificationResult source_revision does not match worker provenance"
        )

    worker_id = worker_result.get("worker", {}).get("id")
    independence = verification_result.get("independence", {})
    if independence.get("worker_id_observed") != worker_id:
        raise IntegrityError(
            "VerificationResult independence.worker_id_observed does not match worker id"
        )
    if independence.get("independent_from_worker") is True:
        verifier_id = verification_result.get("verifier", {}).get("id")
        if verifier_id == worker_id:
            raise IntegrityError(
                "VerificationResult claims independence but verifier id equals worker id"
            )

    return {
        "work_unit_digest": work_unit_digest,
        "result_manifest_digest": worker_result_digest,
        "source_revision": str(worker_source_revision),
    }


def load_triplet(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_json(resolve_repo_path(args.work_unit)),
        load_json(resolve_repo_path(args.worker_result)),
        load_json(resolve_repo_path(args.verification_result)),
    )


def cmd_check(args: argparse.Namespace) -> int:
    work_unit, worker_result, verification_result = load_triplet(args)
    bindings = validate_integrity(work_unit, worker_result, verification_result)
    print(
        "OK: verification provenance is bound to exact Work Unit and worker ResultManifest; "
        f"work_unit={bindings['work_unit_digest']} "
        f"result_manifest={bindings['result_manifest_digest']}"
    )
    return 0


def cmd_self_test(args: argparse.Namespace) -> int:
    work_unit, worker_result, verification_result = load_triplet(args)
    bindings = validate_integrity(work_unit, worker_result, verification_result)

    invalid_path = resolve_repo_path(args.invalid_verification_result)
    invalid_result = load_json(invalid_path)
    try:
        validate_integrity(work_unit, worker_result, invalid_result)
    except IntegrityError:
        pass
    else:
        raise IntegrityError(
            f"negative fixture {invalid_path} unexpectedly passed provenance integrity"
        )

    print(
        "OK: positive provenance bindings verified and mismatched-digest fixture rejected; "
        f"work_unit={bindings['work_unit_digest']} "
        f"result_manifest={bindings['result_manifest_digest']}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-unit",
        default="examples/work-units/phase0-smoke.work-unit.json",
    )
    parser.add_argument(
        "--worker-result",
        default="examples/results/phase0-smoke.result-manifest.json",
    )
    parser.add_argument(
        "--verification-result",
        default="examples/results/phase0-smoke.verification-result.json",
    )
    parser.add_argument(
        "--invalid-verification-result",
        default="examples/results/invalid-mismatched-provenance.verification-result.json",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Validate the positive fixture and require the negative provenance fixture to fail.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return cmd_self_test(args) if args.self_test else cmd_check(args)
    except (IntegrityError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
