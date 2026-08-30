#!/usr/bin/env python3
"""Aggregate open-model benchmark probe evidence into one deterministic summary.

``tools/open_model_benchmark_probe.py`` emits one ``probe-evidence.json`` per
attempt. This tool reads a tree of them and reports what was actually measured:
per-attempt outcomes, the well-formed-patch rate, the independent verifier's
acceptance rate, wall time, real token counts, and the pairwise failure
correlation between independent attempts.

It computes nothing the evidence does not contain. Where a statistic is
undefined -- most importantly the pairwise failure correlation when every
attempt fails, so the failure indicator has zero variance -- it is reported as
``null`` with an explicit reason rather than as a number.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any

SCHEMA_VERSION = "open-model-probe-summary-v0.1"

# Outcomes in which the host harness obtained a normalized, applicable,
# single-file candidate patch and handed it to the independent verifier.
WELL_FORMED_OUTCOMES = frozenset(
    {"supported", "rejected", "escalated", "insufficient_evidence", "verification_error"}
)
ACCEPTED_OUTCOMES = frozenset({"supported"})

# Rejection reasons that are failures of the unified-diff PROTOCOL, not of the
# proposed change. They are decided before any repository content is consulted.
PROTOCOL_REJECTIONS = (
    "model response did not contain a `diff --git` patch",
    "model response contained more than one file diff",
    "model patch targeted a path other than the WorkUnit allowed path",
    "model patch header is malformed but names only the allowed path",
    "model patch did not preserve exact old/new target paths",
    "model patch did not contain a textual hunk",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def binomial_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1.0 - p) ** (n - i) for i in range(0, k + 1))


def clopper_pearson_upper(successes: int, trials: int, alpha: float = 0.05) -> float | None:
    """One-sided exact upper confidence bound on a binomial success rate."""
    if trials <= 0:
        return None
    if successes >= trials:
        return 1.0
    low, high = 0.0, 1.0
    for _ in range(200):
        mid = (low + high) / 2.0
        if binomial_cdf(successes, trials, mid) > alpha:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def phi_correlation(left: list[int], right: list[int]) -> float | None:
    """Pearson correlation of two binary vectors; None when either is constant."""
    if len(left) != len(right) or len(left) < 2:
        return None
    if len(set(left)) < 2 or len(set(right)) < 2:
        return None
    n = len(left)
    mean_l = sum(left) / n
    mean_r = sum(right) / n
    cov = sum((a - mean_l) * (b - mean_r) for a, b in zip(left, right))
    var_l = sum((a - mean_l) ** 2 for a in left)
    var_r = sum((b - mean_r) ** 2 for b in right)
    denominator = math.sqrt(var_l * var_r)
    if denominator == 0.0:
        return None
    return cov / denominator


def diff_header_is_prefix_only(header: str | None) -> bool:
    """True when a rejected `diff --git` header names the same file on both sides.

    The extractor requires the exact form ``diff --git a/P b/P``. A header such
    as ``diff --git P b/P`` is rejected with "targeted a path other than the
    WorkUnit allowed path", which reads as a containment breach but is only a
    missing ``a/`` prefix. Counting these separately keeps the boundary
    statistic honest.
    """
    if not header or not header.startswith("diff --git "):
        return False
    parts = header[len("diff --git ") :].split()
    if len(parts) != 2:
        return False
    left, right = (part[2:] if part[:2] in ("a/", "b/") else part for part in parts)
    return left == right and bool(left)


def classify_failure(evidence: dict[str, Any]) -> tuple[str, str]:
    """Split a rejection into (class, detail).

    ``protocol`` failures never reach the repository: the response is not a
    single well-formed unified diff against the one allowed path. ``content``
    failures are diffs ``git apply`` parsed and then declined to apply, which is
    the only class that says anything about the proposed change. The split
    matters because a producer contract that rejects on shape alone measures
    diff-format compliance, not coding ability.
    """
    outcome = evidence["outcome"]
    if outcome in ACCEPTED_OUTCOMES:
        return "accepted", outcome
    if outcome == "producer_error":
        return "harness", "producer container did not emit a response"
    reason = evidence.get("producer_reason") or ""
    if reason in PROTOCOL_REJECTIONS:
        return "protocol", reason
    if reason.startswith("unsupported patch shape from model"):
        return "protocol", "unsupported patch shape"
    if reason == "model patch normalized to an empty candidate":
        return "protocol", reason
    if reason == "model patch did not apply cleanly to immutable source":
        stderr = evidence.get("git_apply_stderr") or ""
        if "corrupt patch" in stderr:
            return "protocol", "git apply: corrupt patch"
        if "patch fragment without header" in stderr:
            return "protocol", "git apply: patch fragment without header"
        return "content", "git apply: patch does not apply to the frozen source"
    if outcome in WELL_FORMED_OUTCOMES:
        return "verifier", outcome
    return "other", reason or outcome


def collect(results_root: Path) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for path in sorted(results_root.rglob("probe-evidence.json")):
        evidence = load_json(path)
        response_path = path.parent / "model-response.txt"
        diff_header = None
        if response_path.is_file():
            text = response_path.read_text(encoding="utf-8", errors="replace")
            start = text.find("diff --git ")
            if start >= 0:
                diff_header = text[start:].splitlines()[0]
        manifest = evidence.get("result_manifest") or {}
        resources = manifest.get("resources") or {}
        metadata = evidence.get("model_metadata") or {}
        decode = (evidence.get("producer") or {}).get("decode") or {}
        outcome = evidence["outcome"]
        failure_class, failure_detail = classify_failure(evidence)
        attempts.append(
            {
                "evidence_path": path.as_posix(),
                "task_id": evidence["task_id"],
                "attempt": evidence.get("attempt", decode.get("attempt")),
                "outcome": outcome,
                "failure_mode": evidence.get("producer_reason"),
                "failure_class": failure_class,
                "failure_detail": failure_detail,
                "hit_output_token_cap": (
                    metadata.get("output_tokens") is not None
                    and metadata.get("output_tokens") == (decode.get("max_new_tokens") or 0)
                ),
                "well_formed_patch": outcome in WELL_FORMED_OUTCOMES,
                "verifier_accepted": outcome in ACCEPTED_OUTCOMES,
                "do_sample": decode.get("do_sample"),
                "seed": decode.get("seed"),
                "temperature": decode.get("temperature"),
                "input_tokens": metadata.get("input_tokens"),
                "output_tokens": metadata.get("output_tokens"),
                "inference_seconds": metadata.get("inference_seconds"),
                "attempt_wall_seconds": resources.get("wall_seconds"),
                "raw_response_digest": evidence.get("raw_response_digest"),
                "first_diff_header": diff_header,
            }
        )
    return attempts


def correlation_block(attempts: list[dict[str, Any]], *, sampled_only: bool) -> dict[str, Any]:
    """Pairwise failure correlation between independent attempt slots."""
    rows = [a for a in attempts if (a["do_sample"] is True) or not sampled_only]
    slots = sorted({a["attempt"] for a in rows if a["attempt"] is not None})
    tasks = sorted({a["task_id"] for a in rows})
    index = {(a["task_id"], a["attempt"]): a for a in rows}

    complete = [t for t in tasks if all((t, s) in index for s in slots)]
    columns: dict[int, list[int]] = {
        s: [0 if index[(t, s)]["verifier_accepted"] else 1 for t in complete] for s in slots
    }
    pairs: list[dict[str, Any]] = []
    defined: list[float] = []
    for i, left in enumerate(slots):
        for right in slots[i + 1 :]:
            value = phi_correlation(columns[left], columns[right])
            pairs.append({"attempts": [left, right], "phi": value})
            if value is not None:
                defined.append(value)

    marginal = [v for column in columns.values() for v in column]
    return {
        "sampled_only": sampled_only,
        "attempt_slots": slots,
        "tasks_with_complete_coverage": complete,
        # 1 = this attempt failed, matching `columns` and `marginal_failure_rate`.
        # Reporting acceptance under a key named "failure" would invert every
        # future reading of this block for free.
        "failure_indicator": {
            t: [0 if index[(t, s)]["verifier_accepted"] else 1 for s in slots]
            for t in complete
        },
        "marginal_failure_rate": (sum(marginal) / len(marginal)) if marginal else None,
        "pairs": pairs,
        "mean_pairwise_phi": statistics.fmean(defined) if defined else None,
        "undefined_reason": (
            None
            if defined
            else "every attempt failed, so the per-attempt failure indicator has zero "
            "variance and pairwise correlation is undefined, not zero"
        ),
    }


def response_distinctness(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Distinct raw responses, counted per task *and* across tasks.

    Counting only within a task hides the interesting failure: two attempts on
    two different WorkUnits, built from two different prompts, emitting the
    byte-identical response. That is not a duplicate run, it is the producer
    ignoring the task, and a per-task view reports it as full diversity.
    """
    digests = [a["raw_response_digest"] for a in attempts if a["raw_response_digest"]]
    by_digest: dict[str, set[str]] = {}
    for a in attempts:
        digest = a["raw_response_digest"]
        if digest:
            by_digest.setdefault(digest, set()).add(a["task_id"])
    shared = sorted(
        (
            {"raw_response_digest": digest, "task_ids": sorted(tasks)}
            for digest, tasks in by_digest.items()
            if len(tasks) > 1
        ),
        key=lambda item: (-len(item["task_ids"]), item["raw_response_digest"]),
    )
    per_task: dict[str, dict[str, int]] = {}
    for task in sorted({a["task_id"] for a in attempts}):
        rows = [a for a in attempts if a["task_id"] == task and a["raw_response_digest"]]
        per_task[task] = {
            "attempts": len(rows),
            "distinct_responses": len({a["raw_response_digest"] for a in rows}),
        }
    return {
        "attempts_with_a_digest": len(digests),
        "distinct_responses": len(set(digests)),
        "per_task": per_task,
        "responses_shared_across_tasks": shared,
        "note": "A response shared across tasks was produced from different "
        "prompts. It means the requested change stopped influencing the output, "
        "and it is invisible in the per-task counts.",
    }


def summarize(results_root: Path) -> dict[str, Any]:
    attempts = collect(results_root)
    total = len(attempts)
    well_formed = sum(1 for a in attempts if a["well_formed_patch"])
    accepted = sum(1 for a in attempts if a["verifier_accepted"])

    outcome_counts: dict[str, int] = {}
    failure_modes: dict[str, int] = {}
    failure_classes: dict[str, int] = {}
    failure_details: dict[str, int] = {}
    for a in attempts:
        outcome_counts[a["outcome"]] = outcome_counts.get(a["outcome"], 0) + 1
        if a["failure_mode"]:
            failure_modes[a["failure_mode"]] = failure_modes.get(a["failure_mode"], 0) + 1
        failure_classes[a["failure_class"]] = failure_classes.get(a["failure_class"], 0) + 1
        failure_details[a["failure_detail"]] = failure_details.get(a["failure_detail"], 0) + 1
    capped = sum(1 for a in attempts if a["hit_output_token_cap"])
    path_rejections = [
        a
        for a in attempts
        if a["failure_mode"] == "model patch targeted a path other than the WorkUnit allowed path"
    ]
    prefix_only = sum(1 for a in path_rejections if diff_header_is_prefix_only(a["first_diff_header"]))

    inference = [a["inference_seconds"] for a in attempts if a["inference_seconds"] is not None]
    inputs = [a["input_tokens"] for a in attempts if a["input_tokens"] is not None]
    outputs = [a["output_tokens"] for a in attempts if a["output_tokens"] is not None]

    tasks = sorted({a["task_id"] for a in attempts})
    per_task = {
        t: {
            "attempts": sum(1 for a in attempts if a["task_id"] == t),
            "well_formed_patch": sum(1 for a in attempts if a["task_id"] == t and a["well_formed_patch"]),
            "verifier_accepted": sum(1 for a in attempts if a["task_id"] == t and a["verifier_accepted"]),
        }
        for t in tasks
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "results_root": results_root.as_posix(),
        "totals": {
            "tasks": len(tasks),
            "attempts": total,
            "well_formed_patch": well_formed,
            "verifier_accepted": accepted,
            "well_formed_patch_rate": (well_formed / total) if total else None,
            "verifier_acceptance_rate": (accepted / total) if total else None,
            "verifier_acceptance_upper_95": clopper_pearson_upper(accepted, total),
        },
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "failure_modes": dict(sorted(failure_modes.items(), key=lambda kv: (-kv[1], kv[0]))),
        "failure_classes": dict(sorted(failure_classes.items(), key=lambda kv: (-kv[1], kv[0]))),
        "failure_details": dict(sorted(failure_details.items(), key=lambda kv: (-kv[1], kv[0]))),
        "allowed_path_rejections": {
            "total": len(path_rejections),
            "header_prefix_formatting_only": prefix_only,
            "note": "Rejections reported as an out-of-scope path whose diff header "
            "in fact names the allowed path on both sides and differs only in the "
            "a/ or b/ prefix. These are diff-format failures, not containment "
            "breaches. The probe now reports them separately as \"model patch "
            "header is malformed but names only the allowed path\"; this count "
            "stays so evidence recorded before that fix can still be read "
            "correctly, and it should be 0 for any run made after it.",
        },
        "output_token_cap": {
            "attempts_at_cap": capped,
            "rate": (capped / total) if total else None,
            "note": "An attempt at the cap never emitted a stop token; it was still "
            "generating when generation was cut off.",
        },
        "cost": {
            "total_model_input_tokens": sum(inputs),
            "total_model_output_tokens": sum(outputs),
            "total_inference_seconds": sum(inference),
            "mean_inference_seconds": statistics.fmean(inference) if inference else None,
            "max_inference_seconds": max(inference) if inference else None,
            "paid_api_spend_usd": 0.0,
        },
        "per_task": per_task,
        "response_distinctness": response_distinctness(attempts),
        "pairwise_failure_correlation": correlation_block(attempts, sampled_only=True),
        "attempts": attempts,
    }


def self_test() -> int:
    assert phi_correlation([1, 1, 1, 1], [1, 1, 1, 1]) is None
    assert phi_correlation([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert phi_correlation([1, 0, 1, 0], [0, 1, 0, 1]) == -1.0
    upper = clopper_pearson_upper(0, 60)
    exact = 1.0 - 0.05 ** (1.0 / 60)
    assert abs(upper - exact) < 1e-9, (upper, exact)
    assert clopper_pearson_upper(0, 0) is None
    assert abs(clopper_pearson_upper(1, 10) - 0.3942) < 1e-3
    # The reported failure indicator must be the failure indicator, not its
    # complement: a run where nothing was accepted is all ones, never all zeros.
    block = correlation_block(
        [
            {
                "task_id": "t", "attempt": 1, "do_sample": True,
                "verifier_accepted": False,
            },
            {
                "task_id": "t", "attempt": 2, "do_sample": True,
                "verifier_accepted": False,
            },
        ],
        sampled_only=True,
    )
    assert block["failure_indicator"] == {"t": [1, 1]}, block["failure_indicator"]
    assert block["marginal_failure_rate"] == 1.0
    assert block["mean_pairwise_phi"] is None
    # Full per-task diversity must not be allowed to hide a cross-task collision.
    distinct = response_distinctness(
        [
            {"task_id": "a", "raw_response_digest": "sha256:1"},
            {"task_id": "a", "raw_response_digest": "sha256:2"},
            {"task_id": "b", "raw_response_digest": "sha256:1"},
            {"task_id": "b", "raw_response_digest": "sha256:3"},
        ]
    )
    assert distinct["per_task"] == {
        "a": {"attempts": 2, "distinct_responses": 2},
        "b": {"attempts": 2, "distinct_responses": 2},
    }, distinct["per_task"]
    assert distinct["distinct_responses"] == 3, distinct["distinct_responses"]
    assert distinct["responses_shared_across_tasks"] == [
        {"raw_response_digest": "sha256:1", "task_ids": ["a", "b"]}
    ], distinct["responses_shared_across_tasks"]
    assert classify_failure(
        {"outcome": "producer_output_rejected",
         "producer_reason": "model response did not contain a `diff --git` patch"}
    ) == ("protocol", "model response did not contain a `diff --git` patch")
    assert classify_failure(
        {"outcome": "producer_output_rejected",
         "producer_reason": "model patch did not apply cleanly to immutable source",
         "git_apply_stderr": "error: corrupt patch at line 42\n"}
    ) == ("protocol", "git apply: corrupt patch")
    assert classify_failure(
        {"outcome": "producer_output_rejected",
         "producer_reason": "model patch did not apply cleanly to immutable source",
         "git_apply_stderr": "error: patch does not apply\n"}
    )[0] == "content"
    assert classify_failure({"outcome": "supported"})[0] == "accepted"
    assert diff_header_is_prefix_only("diff --git tools/x.py b/tools/x.py")
    assert diff_header_is_prefix_only("diff --git a/tools/x.py b/tools/x.py")
    assert not diff_header_is_prefix_only("diff --git a/tools/x.py b/SECURITY.md")
    assert not diff_header_is_prefix_only(None)
    assert classify_failure(
        {
            "outcome": "producer_output_rejected",
            "producer_reason": "model patch header is malformed but names only the allowed path",
        }
    ) == (
        "protocol",
        "model patch header is malformed but names only the allowed path",
    )
    print("OK: correlation degeneracy and exact binomial bound behave as documented")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--results-root")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.results_root:
        parser.error("--results-root is required unless --self-test is used")

    summary = summarize(Path(args.results_root))
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
