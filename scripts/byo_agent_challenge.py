#!/usr/bin/env python3
"""Evaluate the public BYO-agent ResultManifest conformance challenge.

This is a deterministic onboarding/conformance evaluator, not a hidden benchmark.
It validates embedded candidate manifests against the repository's canonical
ResultManifest v0.1 JSON Schema, then compares those outcomes with a participant's
boolean classifications. It performs no network calls and grants no integration
authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SCHEMA = Path("schemas/result-manifest.schema.json")
CHALLENGE_VERSION = 1
SUBMISSION_VERSION = 1
REPORT_VERSION = 1


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _non_negative_number(value: Any, name: str) -> float:
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{name} must be numeric",
    )
    result = float(value)
    _require(math.isfinite(result) and result >= 0.0, f"{name} must be finite and >= 0")
    return result


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_non_finite,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"cannot read {label} {path}: {error}") from error
    _require(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def _git_blob_sha(content: bytes) -> str:
    prefix = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(prefix + content).hexdigest()


def validate_challenge(challenge: dict[str, Any]) -> None:
    _require(
        challenge.get("version") == CHALLENGE_VERSION,
        f"challenge version must be {CHALLENGE_VERSION}",
    )
    challenge_id = challenge.get("challenge_id")
    _require(isinstance(challenge_id, str) and challenge_id, "challenge_id must be non-empty")
    _require(
        challenge.get("schema") == CANONICAL_SCHEMA.as_posix(),
        "challenge must use the canonical ResultManifest schema",
    )
    schema_blob = challenge.get("schema_git_blob_sha")
    _require(
        isinstance(schema_blob, str)
        and len(schema_blob) == 40
        and all(character in "0123456789abcdef" for character in schema_blob),
        "schema_git_blob_sha must be a lowercase 40-character Git object id",
    )
    source_revision = challenge.get("source_revision")
    _require(
        isinstance(source_revision, str) and source_revision,
        "source_revision must be non-empty",
    )
    cases = challenge.get("cases")
    _require(isinstance(cases, list) and cases, "cases must be a non-empty array")
    seen: set[str] = set()
    for index, case in enumerate(cases):
        _require(isinstance(case, dict), f"cases[{index}] must be an object")
        case_id = case.get("case_id")
        _require(
            isinstance(case_id, str) and case_id,
            f"cases[{index}].case_id must be non-empty",
        )
        _require(case_id not in seen, f"duplicate challenge case_id: {case_id}")
        seen.add(case_id)
        _require(
            isinstance(case.get("manifest"), dict),
            f"cases[{index}].manifest must be an object",
        )


def validate_submission(submission: dict[str, Any], challenge: dict[str, Any]) -> None:
    _require(
        submission.get("version") == SUBMISSION_VERSION,
        f"submission version must be {SUBMISSION_VERSION}",
    )
    _require(
        submission.get("challenge_id") == challenge["challenge_id"],
        "submission challenge_id does not match challenge",
    )

    participant = submission.get("participant")
    _require(isinstance(participant, dict), "participant must be an object")
    _require(
        participant.get("kind") in {"human", "ai_agent", "human_ai"},
        "participant.kind must be human, ai_agent, or human_ai",
    )
    source_revision = participant.get("source_revision")
    _require(
        isinstance(source_revision, str) and source_revision,
        "participant.source_revision must be non-empty",
    )
    for field in ("tool", "model"):
        value = participant.get(field)
        if value is not None:
            _require(
                isinstance(value, str) and value,
                f"participant.{field} must be a non-empty string when present",
            )

    measurements = submission.get("measurements", {})
    _require(isinstance(measurements, dict), "measurements must be an object")
    for field in ("wall_seconds", "human_review_minutes"):
        if field in measurements:
            _non_negative_number(measurements[field], f"measurements.{field}")

    answers = submission.get("answers")
    _require(isinstance(answers, list), "answers must be an array")
    expected_ids = {case["case_id"] for case in challenge["cases"]}
    answer_ids: set[str] = set()
    for index, answer in enumerate(answers):
        _require(isinstance(answer, dict), f"answers[{index}] must be an object")
        case_id = answer.get("case_id")
        _require(
            isinstance(case_id, str) and case_id,
            f"answers[{index}].case_id must be non-empty",
        )
        _require(case_id in expected_ids, f"unknown case_id in submission: {case_id}")
        _require(case_id not in answer_ids, f"duplicate submission case_id: {case_id}")
        answer_ids.add(case_id)
        _require(
            isinstance(answer.get("schema_valid"), bool),
            f"answers[{index}].schema_valid must be boolean",
        )
    missing = expected_ids - answer_ids
    _require(not missing, f"submission is missing cases: {', '.join(sorted(missing))}")
    _require(
        len(answers) == len(expected_ids),
        "submission must contain exactly one answer per challenge case",
    )


def _decode_pinned_schema(
    challenge: dict[str, Any], schema_bytes: bytes
) -> dict[str, Any]:
    _require(isinstance(schema_bytes, bytes), "schema_bytes must be bytes")
    actual_blob_sha = _git_blob_sha(schema_bytes)
    _require(
        actual_blob_sha == challenge["schema_git_blob_sha"],
        "canonical schema blob differs from the challenge pin; use the recorded source revision or version the challenge",
    )
    try:
        schema = json.loads(schema_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"canonical schema is not valid UTF-8 JSON: {error}") from error
    _require(isinstance(schema, dict), "canonical schema must be a JSON object")
    return schema


def _error_signature(errors: list[Any]) -> dict[str, str] | None:
    if not errors:
        return None
    first = errors[0]
    path = "/" + "/".join(str(part) for part in first.absolute_path)
    return {
        "path": path if path != "/" else "/",
        "validator": str(first.validator),
    }


def evaluate(
    challenge: dict[str, Any],
    submission: dict[str, Any],
    schema_bytes: bytes,
) -> dict[str, Any]:
    validate_challenge(challenge)
    validate_submission(submission, challenge)
    schema = _decode_pinned_schema(challenge, schema_bytes)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    answers = {row["case_id"]: row["schema_valid"] for row in submission["answers"]}

    results: list[dict[str, Any]] = []
    correct = 0
    for case in challenge["cases"]:
        errors = sorted(
            validator.iter_errors(case["manifest"]),
            key=lambda error: (
                tuple(str(part) for part in error.absolute_path),
                str(error.validator),
            ),
        )
        expected = not errors
        reported = answers[case["case_id"]]
        is_correct = reported == expected
        correct += int(is_correct)
        results.append(
            {
                "case_id": case["case_id"],
                "reported_schema_valid": reported,
                "expected_schema_valid": expected,
                "correct": is_correct,
                "first_schema_error": _error_signature(errors),
            }
        )

    total = len(results)
    measurements = submission.get("measurements", {})
    participant = submission["participant"]
    return {
        "version": REPORT_VERSION,
        "challenge_id": challenge["challenge_id"],
        "challenge_source_revision": challenge["source_revision"],
        "schema": CANONICAL_SCHEMA.as_posix(),
        "schema_git_blob_sha": challenge["schema_git_blob_sha"],
        "participant": {
            "kind": participant["kind"],
            "tool": participant.get("tool"),
            "model": participant.get("model"),
            "source_revision": participant["source_revision"],
        },
        "score": {
            "correct": correct,
            "total": total,
            "accuracy": correct / total,
            "passed": correct == total,
        },
        "case_results": results,
        "measurements": {
            "wall_seconds": measurements.get("wall_seconds"),
            "human_review_minutes": measurements.get("human_review_minutes"),
            "status": "self_reported_unverified",
        },
        "authority": {
            "hidden_benchmark_evidence": False,
            "independent_review": False,
            "integration_authority": False,
        },
    }


def evaluate_files(challenge_path: Path, submission_path: Path) -> dict[str, Any]:
    challenge = _load_object(challenge_path, "challenge")
    submission = _load_object(submission_path, "submission")
    schema_path = ROOT / CANONICAL_SCHEMA
    try:
        schema_bytes = schema_path.read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read canonical schema {schema_path}: {error}") from error
    return evaluate(challenge, submission, schema_bytes)


def serialize(report: dict[str, Any]) -> str:
    return (
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("challenge", type=Path)
    parser.add_argument("submission", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        report = evaluate_files(args.challenge, args.submission)
        text = serialize(report)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0 if report["score"]["passed"] else 1
    except (ValueError, OSError, SchemaError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
