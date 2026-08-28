#!/usr/bin/env python3
"""Discover conservative local capacity and emit a zero-project-cost compute offer.

This utility performs discovery only. It does not execute a Work Unit, open a
network connection, register a node, or expose remote-control functionality.
The output conforms to compute-offer-pool-v0.1 and can be consumed by
free_compute_router.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
OFFER_SCHEMA = ROOT / "schemas" / "compute-offer-pool-v0.1.schema.json"

DEFAULT_CPU_CAP = 1.0
DEFAULT_MEMORY_MB_CAP = 1024
DEFAULT_DISK_MB_CAP = 4096


class DiscoveryError(RuntimeError):
    pass


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_offer_pool(pool: dict[str, Any]) -> None:
    schema = read_json(OFFER_SCHEMA)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(pool), key=lambda error: list(error.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise DiscoveryError(f"generated offer failed schema validation: {details}")


def detected_memory_mb() -> int:
    """Best-effort stdlib-only physical-memory detection; return 0 if unknown."""
    if hasattr(os, "sysconf"):
        try:
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            pages = int(os.sysconf("SC_PHYS_PAGES"))
            if page_size > 0 and pages > 0:
                return (page_size * pages) // (1024 * 1024)
        except (OSError, ValueError, TypeError):
            pass
    return 0


def discover_raw(path: Path) -> dict[str, Any]:
    cpu = float(os.cpu_count() or 1)
    memory_mb = detected_memory_mb()
    try:
        disk_mb = int(shutil.disk_usage(path).free // (1024 * 1024))
    except OSError:
        disk_mb = 0

    capabilities = [
        "deterministic-local-execution",
        "python",
        f"os:{platform.system().lower() or 'unknown'}",
        f"arch:{platform.machine().lower() or 'unknown'}",
    ]
    if importlib.util.find_spec("jsonschema") is not None:
        capabilities.append("json-schema-validation")

    return {
        "cpu_cores": max(cpu, 0.0),
        "memory_mb": max(memory_mb, 0),
        "disk_mb": max(disk_mb, 0),
        "capabilities": capabilities,
    }


def bounded(value: float, cap: float) -> float:
    if cap < 0:
        raise DiscoveryError("resource caps must be non-negative")
    return min(value, cap)


def build_offer_pool(
    raw: dict[str, Any],
    *,
    cpu_cap: float,
    memory_mb_cap: int,
    disk_mb_cap: int,
    donated: bool,
    available: bool,
    gpu: bool,
    accelerator_capabilities: list[str],
    independence_group: str,
) -> dict[str, Any]:
    if not independence_group:
        raise DiscoveryError("independence group must be non-empty")

    cpu = bounded(float(raw["cpu_cores"]), float(cpu_cap))
    memory_mb = int(bounded(float(raw["memory_mb"]), float(memory_mb_cap)))
    disk_mb = int(bounded(float(raw["disk_mb"]), float(disk_mb_cap)))

    # Unknown memory/disk must never be promoted to the requested cap.
    if int(raw["memory_mb"]) == 0:
        memory_mb = 0
    if int(raw["disk_mb"]) == 0:
        disk_mb = 0

    capabilities = list(dict.fromkeys(raw["capabilities"]))
    accelerators = list(dict.fromkeys(accelerator_capabilities)) if gpu else []
    capabilities.extend(cap for cap in accelerators if cap not in capabilities)

    pool = {
        "schema_version": "0.1",
        "offers": [
            {
                "id": "local-discovered",
                "provider": "local",
                "cost_class": "donated" if donated else "local_owned",
                "project_cost_usd": 0,
                "available": available,
                "trust": "untrusted",
                "capabilities": capabilities,
                "resources": {
                    "cpu_cores": cpu,
                    "memory_mb": memory_mb,
                    "disk_mb": disk_mb,
                    "gpu": gpu,
                    "accelerator_capabilities": accelerators,
                },
                "expected_wait_seconds": 0,
                "success_probability": 0.5,
                "independence_group": independence_group,
                "notes": (
                    "Discovery-only local offer. Reported capacity is capped below detected host "
                    "capacity and does not itself authorize execution. GPU capacity is included only "
                    "after an explicit command-line declaration."
                ),
            }
        ],
    }
    validate_offer_pool(pool)
    return pool


def command_discover(args: argparse.Namespace) -> int:
    raw = discover_raw(ROOT)
    pool = build_offer_pool(
        raw,
        cpu_cap=args.cpu_cap,
        memory_mb_cap=args.memory_mb_cap,
        disk_mb_cap=args.disk_mb_cap,
        donated=args.donated,
        available=not args.unavailable,
        gpu=args.gpu,
        accelerator_capabilities=args.accelerator,
        independence_group=args.independence_group,
    )
    payload = json.dumps(pool, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


def command_self_test(_: argparse.Namespace) -> int:
    raw = {
        "cpu_cores": 8.0,
        "memory_mb": 16384,
        "disk_mb": 50000,
        "capabilities": ["python", "json-schema-validation", "deterministic-local-execution"],
    }
    pool = build_offer_pool(
        raw,
        cpu_cap=1.5,
        memory_mb_cap=768,
        disk_mb_cap=2048,
        donated=False,
        available=True,
        gpu=False,
        accelerator_capabilities=[],
        independence_group="fixture-local",
    )
    offer = pool["offers"][0]
    resources = offer["resources"]
    if resources["cpu_cores"] != 1.5:
        raise DiscoveryError("CPU cap was not enforced")
    if resources["memory_mb"] != 768:
        raise DiscoveryError("memory cap was not enforced")
    if resources["disk_mb"] != 2048:
        raise DiscoveryError("disk cap was not enforced")
    if offer["project_cost_usd"] != 0 or offer["cost_class"] != "local_owned":
        raise DiscoveryError("local offer violated zero-project-spend invariant")

    small_raw = dict(raw)
    small_raw.update({"cpu_cores": 0.25, "memory_mb": 32, "disk_mb": 128})
    small_pool = build_offer_pool(
        small_raw,
        cpu_cap=4,
        memory_mb_cap=4096,
        disk_mb_cap=10000,
        donated=True,
        available=True,
        gpu=False,
        accelerator_capabilities=[],
        independence_group="fixture-small",
    )
    small = small_pool["offers"][0]
    if small["resources"]["cpu_cores"] != 0.25 or small["resources"]["memory_mb"] != 32:
        raise DiscoveryError("discovery incorrectly inflated small host capacity to configured caps")
    if small["cost_class"] != "donated":
        raise DiscoveryError("explicit donated mode was not preserved")

    print("OK: local discovery is schema-valid, zero-cost, capped, and never inflates detected capacity")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="Emit one capped local compute offer")
    discover.add_argument("--cpu-cap", type=float, default=DEFAULT_CPU_CAP)
    discover.add_argument("--memory-mb-cap", type=int, default=DEFAULT_MEMORY_MB_CAP)
    discover.add_argument("--disk-mb-cap", type=int, default=DEFAULT_DISK_MB_CAP)
    discover.add_argument(
        "--donated",
        action="store_true",
        help="Explicitly classify the zero-project-cost capacity as donated instead of local_owned.",
    )
    discover.add_argument("--unavailable", action="store_true")
    discover.add_argument(
        "--gpu",
        action="store_true",
        help="Explicitly declare that capped GPU capacity may be advertised; no GPU is auto-enabled.",
    )
    discover.add_argument(
        "--accelerator",
        action="append",
        default=[],
        help="Accelerator capability such as cuda; meaningful only with --gpu. Repeatable.",
    )
    discover.add_argument(
        "--independence-group",
        default="local-machine",
        help="Privacy-preserving logical independence label; hostnames are not collected by default.",
    )
    discover.add_argument("--output", help="Optional output JSON path; stdout if omitted.")
    discover.set_defaults(func=command_discover)

    self_test = sub.add_parser("self-test", help="Run deterministic cap and policy tests")
    self_test.set_defaults(func=command_self_test)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (DiscoveryError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
