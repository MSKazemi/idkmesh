from __future__ import annotations

import argparse
import json
import sys

from .model import WorkUnitError, load_work_unit
from .runner import RunnerError, run_work_unit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="idkmesh-node", description="Run one bounded IDKMesh Work Unit in a local Docker sandbox.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate a Work Unit without executing it")
    validate.add_argument("work_unit")

    run = sub.add_parser("run", help="Execute one validated Work Unit")
    run.add_argument("work_unit")
    run.add_argument("--output", required=True, help="Directory for result.json, logs, and patch")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        work, raw = load_work_unit(args.work_unit)
        if args.command == "validate":
            print(json.dumps({"valid": True, "id": work.id, "revision": work.source.revision}, indent=2))
            return 0
        result = run_work_unit(work, raw, args.output)
        print(json.dumps(result["outcome"], indent=2))
        return 0 if result["outcome"]["exit_code"] == 0 and not result["outcome"]["timed_out"] else 1
    except (WorkUnitError, RunnerError, OSError) as exc:
        print(f"idkmesh-node: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
