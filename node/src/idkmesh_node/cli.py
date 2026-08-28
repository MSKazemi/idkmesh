from __future__ import annotations

import argparse
import json
import sys

from .model import WorkUnitError, canonical_digest, load_work_unit
from .runner import RunnerError, run_work_unit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idkmesh-node",
        description="Validate or run one canonical IDKMesh Work Unit in a local Docker sandbox.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate the canonical Work Unit and local execution binding")
    validate.add_argument("work_unit")

    run = sub.add_parser("run", help="Execute one validated Work Unit")
    run.add_argument("work_unit")
    run.add_argument("--output", required=True, help="Directory for ResultManifest, logs, and patch")
    run.add_argument("--attempt", type=int, default=1, help="Positive attempt number for ResultManifest provenance")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        work = load_work_unit(args.work_unit)
        if args.command == "validate":
            print(
                json.dumps(
                    {
                        "valid": True,
                        "schema_version": work.data["schema_version"],
                        "id": work.id,
                        "version": work.version,
                        "revision": work.source.revision,
                        "work_unit_digest": canonical_digest(work.data),
                    },
                    indent=2,
                )
            )
            return 0

        if args.attempt < 1:
            raise WorkUnitError("--attempt must be at least 1")
        result = run_work_unit(work, args.output, attempt=args.attempt)
        print(
            json.dumps(
                {
                    "id": result["id"],
                    "status": result["status"],
                    "acceptance": "pending_verification",
                    "result_manifest": "result-manifest.json",
                },
                indent=2,
            )
        )
        return 0 if result["status"] == "succeeded" else 1
    except (WorkUnitError, RunnerError, OSError) as exc:
        print(f"idkmesh-node: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
