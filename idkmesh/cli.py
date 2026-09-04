"""``idkmesh`` command-line interface.

One subcommand for now — ``gate-audit`` — kept deliberately thin: all logic
lives in ``idkmesh.gate_audit`` so it can be tested and reused without a
process boundary.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from idkmesh import __version__
from idkmesh.gate_audit import GateAuditInputError, audit_file, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idkmesh",
        description=(
            "IDKMesh verification tooling. 'gate-audit' measures how many "
            "effective independent votes a verifier panel really has, and how "
            "often seeded known-bad probes get through it."),
    )
    parser.add_argument(
        "--version", action="version", version=f"idkmesh {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    ga = sub.add_parser(
        "gate-audit",
        help="audit a verifier panel from a verdict matrix with ground truth",
        description=(
            "Read a verdict-matrix JSON document (see "
            "docs/specifications/GATE_AUDIT_V0_1.md), compute per-verifier "
            "accuracy, pairwise error correlation, panel error, effective "
            "votes and probe breach rate, and emit a gate-audit-report-v0.1 "
            "JSON document. The audit consumes verdicts; it never runs a gate "
            "and never grants acceptance."),
    )
    ga.add_argument("input", help="path to the verdict-matrix JSON file")
    ga.add_argument(
        "--out", metavar="PATH",
        help="write the JSON report here (default: stdout)")
    ga.add_argument(
        "--markdown", metavar="PATH",
        help="also write a human-readable Markdown summary here")
    ga.add_argument(
        "--pretty", action="store_true",
        help="pretty-print the JSON report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "gate-audit":
        try:
            report = audit_file(args.input)
        except FileNotFoundError:
            print(f"error: input file not found: {args.input}", file=sys.stderr)
            return 2
        except GateAuditInputError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        rendered = json.dumps(
            report, indent=2 if args.pretty else None, sort_keys=False)
        if args.out:
            Path(args.out).write_text(rendered + "\n", encoding="utf-8")
        else:
            print(rendered)
        if args.markdown:
            Path(args.markdown).write_text(
                render_markdown(report), encoding="utf-8")
        return 0
    return 2  # pragma: no cover - argparse enforces the subcommand


if __name__ == "__main__":
    raise SystemExit(main())
