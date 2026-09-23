#!/usr/bin/env python3
"""Freeze one AVE-core verifier-allocation shadow recommendation.

The CLI reads canonical JSON inputs and writes one adaptive-policy shadow plan.
It does not modify the EvaluatorPlan or execute any verifier.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

try:
    from tools.ave_shadow_adapter import (
        AVEShadowAdapterError,
        build_ave_shadow_plan,
    )
except ModuleNotFoundError:  # direct: python tools/ave_shadow_adapter_cli.py
    from ave_shadow_adapter import (
        AVEShadowAdapterError,
        build_ave_shadow_plan,
    )


class AVEShadowCLIError(RuntimeError):
    pass


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AVEShadowCLIError(f"{path}: expected a JSON object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="MSKazemi/idkmesh")
    parser.add_argument("--work-unit", required=True)
    parser.add_argument("--evaluator-plan", required=True)
    parser.add_argument("--verifier-pool", required=True)
    parser.add_argument("--maturity", choices=("N2", "N3"), default="N2")
    parser.add_argument("--input-ref", action="append", default=[])
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    output = Path(args.output)
    if output.exists():
        print(
            f"ERROR: refusing to overwrite frozen shadow plan: {output}",
            file=sys.stderr,
        )
        return 2

    try:
        plan = build_ave_shadow_plan(
            repository=args.repository,
            work_unit=load_json(args.work_unit),
            evaluator_plan=load_json(args.evaluator_plan),
            verifier_pool=load_json(args.verifier_pool),
            maturity=args.maturity,
            input_refs=args.input_ref,
            evidence_refs=args.evidence_ref,
        )
    except (
        OSError,
        KeyError,
        json.JSONDecodeError,
        AVEShadowAdapterError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    except FileExistsError:
        print(
            f"ERROR: refusing to overwrite frozen shadow plan: {output}",
            file=sys.stderr,
        )
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
