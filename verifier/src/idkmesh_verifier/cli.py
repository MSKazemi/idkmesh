from __future__ import annotations

import argparse
import json
import sys

from .model import VerifierError, load_json_object, parse_context
from .runner import VerificationRuntimeError, run_verification


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="idkmesh-verify",
        description="Independently verify one worker ResultManifest candidate against a trusted verifier plan.",
    )
    root.add_argument("--work-unit", required=True)
    root.add_argument("--result-manifest", required=True)
    root.add_argument("--plan", required=True, help="Trusted verifier-side plan; do not provide this file to the worker.")
    root.add_argument("--artifact-root", required=True, help="Root directory containing candidate artifacts referenced by ResultManifest locators.")
    root.add_argument("--output", required=True, help="New directory for VerificationResult and evidence files.")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        work_unit = load_json_object(args.work_unit)
        worker_result = load_json_object(args.result_manifest)
        plan = load_json_object(args.plan)
        context = parse_context(work_unit, worker_result, plan)
        result = run_verification(
            context,
            artifact_root=args.artifact_root,
            output_dir=args.output,
        )
        print(
            json.dumps(
                {
                    "verification_result": f"{args.output}/verification-result.json",
                    "status": result["status"],
                    "recommendation": result["decision_support"]["recommendation"],
                    "final_authority": "human_or_governance_policy",
                },
                indent=2,
            )
        )
        return 0 if result["status"] == "passed" else 1
    except (VerifierError, VerificationRuntimeError, OSError) as exc:
        print(f"idkmesh-verify: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
