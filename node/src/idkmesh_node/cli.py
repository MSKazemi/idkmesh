from __future__ import annotations

import argparse
import json
import sys

from .model import WorkUnitError, canonical_digest, load_work_unit
from .runner import RunnerError, run_work_unit



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idkmesh-node",
        description="Validate or run one canonical IDKMesh Work Unit in a bounded local Docker sandbox.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate the canonical Work Unit and node execution binding")
    validate.add_argument("work_unit")

    run = sub.add_parser("run", help="Execute one validated Work Unit")
    run.add_argument("work_unit")
    run.add_argument("--output", required=True, help="Empty directory for ResultManifest, logs, and patch")
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
                        "work_unit_id": work.id,
                        "work_unit_version": work.version,
                        "source_revision": work.source.revision,
                        "work_unit_digest": canonical_digest(work.document),
                    },
                    indent=2,
                )
            )
            return 0

        result = run_work_unit(work, args.output)
        print(
            json.dumps(
                {
                    "result_manifest": "result-manifest.json",
                    "status": result["status"],
                    "candidate_artifact": "changes.patch",
                    "independent_verification_required": True,
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
