#!/usr/bin/env python3
"""Promote the current trusted IDKMesh GitHub Actions job into a live compute offer.

This adapter is intentionally narrow. It only emits an available
``public_project_ci`` offer while running in the canonical MSKazemi/idkmesh
repository on ``main`` from a scheduled or manually dispatched workflow after
an explicit administrator opt-in and an independently observed protected-main
gate have both passed.

It discovers/caps local resources but does not execute a Work Unit, contact an
external service, or grant repository write/merge authority.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

import local_compute_offer

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_REPOSITORY = "MSKazemi/idkmesh"
CANONICAL_REF = "refs/heads/main"
ACTIVE_EVENTS = {"schedule", "workflow_dispatch"}
ACTIVATION_ENV = "ACTIVE_COMPUTE_PULSE_ENABLED"
PROTECTION_ENV = "IDKMESH_MAIN_PROTECTED"
DEFAULT_CPU_CAP = 2.0
DEFAULT_MEMORY_MB_CAP = 4096
DEFAULT_DISK_MB_CAP = 8192


class GitHubActionsOfferError(RuntimeError):
    pass


def _require_active_context(env: Mapping[str, str]) -> None:
    if env.get("GITHUB_ACTIONS") != "true":
        raise GitHubActionsOfferError("not running inside GitHub Actions")
    if env.get("GITHUB_REPOSITORY") != CANONICAL_REPOSITORY:
        raise GitHubActionsOfferError("repository is not the canonical IDKMesh repository")
    if env.get("GITHUB_REF") != CANONICAL_REF:
        raise GitHubActionsOfferError("active compute offer is restricted to main")
    if env.get("GITHUB_EVENT_NAME") not in ACTIVE_EVENTS:
        raise GitHubActionsOfferError("active compute offer requires schedule or workflow_dispatch")
    if env.get(ACTIVATION_ENV) != "true":
        raise GitHubActionsOfferError("active compute pulse requires explicit administrator opt-in")
    if env.get(PROTECTION_ENV) != "true":
        raise GitHubActionsOfferError("active compute pulse requires verified protected main")


def _cap(value: float, cap: float) -> float:
    if cap < 0:
        raise GitHubActionsOfferError("resource caps must be non-negative")
    return min(max(value, 0.0), cap)


def build_offer_pool(
    raw: dict[str, Any],
    env: Mapping[str, str],
    *,
    cpu_cap: float = DEFAULT_CPU_CAP,
    memory_mb_cap: int = DEFAULT_MEMORY_MB_CAP,
    disk_mb_cap: int = DEFAULT_DISK_MB_CAP,
) -> dict[str, Any]:
    """Build one conservative, schema-valid live offer for the current Actions job."""
    _require_active_context(env)

    cpu = _cap(float(raw.get("cpu_cores", 0)), float(cpu_cap))
    memory = int(_cap(float(raw.get("memory_mb", 0)), float(memory_mb_cap)))
    disk = int(_cap(float(raw.get("disk_mb", 0)), float(disk_mb_cap)))
    capabilities = list(
        dict.fromkeys(
            [
                *raw.get("capabilities", []),
                "github-actions",
                "public-project-ci",
            ]
        )
    )

    pool = {
        "schema_version": "0.1",
        "offers": [
            {
                "id": "github-actions-current-job",
                "provider": "github-actions",
                "cost_class": "public_project_ci",
                "project_cost_usd": 0,
                "available": cpu > 0 and memory > 0 and disk > 0,
                "trust": "trusted",
                "capabilities": capabilities,
                "resources": {
                    "cpu_cores": cpu,
                    "memory_mb": memory,
                    "disk_mb": disk,
                    "gpu": False,
                    "accelerator_capabilities": [],
                },
                "expected_wait_seconds": 0,
                "success_probability": 0.95,
                "independence_group": "github-hosted",
                "notes": (
                    "Live offer for the already-acquired canonical GitHub-hosted CI job. "
                    "Use only after explicit administrator opt-in and protected-main verification, "
                    "for legitimate repository CI/research workloads; this offer does not "
                    "authorize arbitrary external compute or repository mutation."
                ),
            }
        ],
    }
    local_compute_offer.validate_offer_pool(pool)
    return pool


def cmd_discover(args: argparse.Namespace) -> int:
    raw = local_compute_offer.discover_raw(ROOT)
    pool = build_offer_pool(
        raw,
        os.environ,
        cpu_cap=args.cpu_cap,
        memory_mb_cap=args.memory_mb_cap,
        disk_mb_cap=args.disk_mb_cap,
    )
    payload = json.dumps(pool, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


def cmd_self_test(_: argparse.Namespace) -> int:
    raw = {
        "cpu_cores": 8.0,
        "memory_mb": 16384,
        "disk_mb": 50000,
        "capabilities": [
            "python",
            "json-schema-validation",
            "deterministic-local-execution",
            "os:linux",
        ],
    }
    env = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": CANONICAL_REPOSITORY,
        "GITHUB_REF": CANONICAL_REF,
        "GITHUB_EVENT_NAME": "schedule",
        ACTIVATION_ENV: "true",
        PROTECTION_ENV: "true",
    }
    offer = build_offer_pool(
        raw,
        env,
        cpu_cap=1.5,
        memory_mb_cap=768,
        disk_mb_cap=2048,
    )["offers"][0]
    if offer["cost_class"] != "public_project_ci" or offer["project_cost_usd"] != 0:
        raise GitHubActionsOfferError("zero-project-cost public-CI invariant failed")
    if offer["resources"]["cpu_cores"] != 1.5:
        raise GitHubActionsOfferError("CPU cap was not enforced")
    if offer["resources"]["memory_mb"] != 768 or offer["resources"]["disk_mb"] != 2048:
        raise GitHubActionsOfferError("memory/disk caps were not enforced")

    for key, value in [
        ("GITHUB_REPOSITORY", "someone/fork"),
        ("GITHUB_REF", "refs/heads/feature"),
        ("GITHUB_EVENT_NAME", "pull_request"),
        (ACTIVATION_ENV, "false"),
        (PROTECTION_ENV, "false"),
    ]:
        bad = dict(env)
        bad[key] = value
        try:
            build_offer_pool(raw, bad)
        except GitHubActionsOfferError:
            pass
        else:
            raise GitHubActionsOfferError(f"unsafe context was accepted: {key}={value}")

    for missing in (ACTIVATION_ENV, PROTECTION_ENV):
        bad = dict(env)
        del bad[missing]
        try:
            build_offer_pool(raw, bad)
        except GitHubActionsOfferError:
            pass
        else:
            raise GitHubActionsOfferError(f"missing activation evidence was accepted: {missing}")

    print(
        "OK: GitHub Actions offer is capped, zero-cost, schema-valid, main-only, "
        "protected-main-gated, and explicitly enabled"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="Emit a live GitHub Actions compute offer")
    discover.add_argument("--cpu-cap", type=float, default=DEFAULT_CPU_CAP)
    discover.add_argument("--memory-mb-cap", type=int, default=DEFAULT_MEMORY_MB_CAP)
    discover.add_argument("--disk-mb-cap", type=int, default=DEFAULT_DISK_MB_CAP)
    discover.add_argument("--output", help="Optional output JSON path; stdout if omitted")
    discover.set_defaults(func=cmd_discover)

    test = sub.add_parser("self-test", help="Run deterministic safety tests")
    test.set_defaults(func=cmd_self_test)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (GitHubActionsOfferError, local_compute_offer.DiscoveryError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
