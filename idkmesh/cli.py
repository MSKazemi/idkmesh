"""``idkmesh`` command-line interface.

One subcommand for now — ``gate-audit`` — kept deliberately thin: all logic
lives in ``idkmesh.gate_audit`` so it can be tested and reused without a
process boundary.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from idkmesh import __version__
from idkmesh.gate_audit import (
    GateAuditInputError,
    audit_file,
    render_json,
    render_markdown,
)


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
    ga.add_argument(
        "--bootstrap", action="store_true",
        help=(
            "add a deterministic candidate-level bootstrap confidence "
            "interval for panel error, mean verifier accuracy, mean "
            "pairwise correlation and effective votes (issue #520); emits "
            "gate-audit-report-v0.2 instead of v0.1"))
    ga.add_argument(
        "--bootstrap-replicates", type=int, default=2000, metavar="N",
        help="bootstrap resample count; requires --bootstrap (default: 2000)")
    ga.add_argument(
        "--bootstrap-seed", type=int, default=0, metavar="N",
        help=(
            "seed for the bootstrap's deterministic PRNG; requires "
            "--bootstrap (default: 0)"))
    ga.add_argument(
        "--bootstrap-confidence-level", type=float, default=0.95,
        metavar="X",
        help=(
            "confidence level in (0, 1) for the bootstrap interval; "
            "requires --bootstrap (default: 0.95)"))

    gui = sub.add_parser(
        "gate-audit-ui",
        help="open the local browser interface for gate-audit",
        description=(
            "Serve a local browser interface for the gate-audit diagnostic. "
            "The server binds only to 127.0.0.1 and uses the same audit engine "
            "as the CLI; verdict data is not uploaded to a hosted service."),
    )
    gui.add_argument(
        "input", nargs="?",
        help="optional verdict-matrix JSON file to preload in the editor")
    gui.add_argument(
        "--port", type=int, default=8765, metavar="PORT",
        help="loopback TCP port (default: 8765)")
    gui.add_argument(
        "--no-browser", action="store_true",
        help="serve the UI without opening the default browser")
    return parser


def _fail(message: str) -> int:
    """Report a user-fixable problem on stderr and return the exit code for it.

    Every failure route ends here. A traceback is a defect report about the
    tool; it is not a usable message about the caller's file, and it does not
    honour the documented exit codes.
    """
    print(f"error: {message}", file=sys.stderr)
    return 2


def _reason(exc: OSError) -> str:
    return exc.strerror or type(exc).__name__


def _check_output_paths(args: argparse.Namespace) -> int | None:
    """Refuse output paths that would destroy a file the run needs.

    Checked before the audit runs, so a mistyped flag costs nothing. Both
    cases used to succeed with exit 0: ``--out`` and ``--markdown`` on one path
    left only the Markdown, discarding the JSON evidence the report's digest
    exists to bind; ``--out`` on the input path overwrote the verdict matrix
    itself, which is unrecoverable if it was not committed.
    """
    claimed: dict[str, str] = {}
    for flag, path in (("--out", args.out), ("--markdown", args.markdown)):
        if path is None:
            continue
        key = os.path.realpath(path)
        if key == os.path.realpath(args.input):
            return _fail(
                f"{flag} {path} is the input file; writing the report there "
                "would overwrite the verdict matrix it was computed from")
        if key in claimed:
            return _fail(
                f"{flag} and {claimed[key]} both point at {path}; one report "
                "would overwrite the other")
        claimed[key] = flag
    return None


def _write(path: str, text: str, what: str) -> int | None:
    try:
        Path(path).write_text(text, encoding="utf-8")
    except OSError as exc:
        return _fail(f"cannot write the {what} to {path}: {_reason(exc)}")
    return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "gate-audit-ui":
        if not (0 <= args.port <= 65535):
            return _fail("--port must be between 0 and 65535")
        initial_text = None
        if args.input:
            path = Path(args.input)
            try:
                initial_text = path.read_text(encoding="utf-8-sig")
            except FileNotFoundError:
                return _fail(f"input file not found: {args.input}")
            except IsADirectoryError:
                return _fail(
                    f"input path is a directory, not a verdict-matrix file: "
                    f"{args.input}")
            except UnicodeDecodeError as exc:
                return _fail(
                    f"{args.input}: not UTF-8 text ({exc.reason} at byte "
                    f"{exc.start}); save the verdict matrix as UTF-8")
            except OSError as exc:
                return _fail(
                    f"cannot read input file {args.input}: {_reason(exc)}")
        from idkmesh.gate_audit_ui import serve_gate_audit_ui
        try:
            serve_gate_audit_ui(
                initial_text, port=args.port,
                open_browser=not args.no_browser)
        except OSError as exc:
            return _fail(
                f"cannot start local UI on 127.0.0.1:{args.port}: "
                f"{_reason(exc)}")
        return 0

    if args.command != "gate-audit":  # pragma: no cover - argparse enforces it
        return 2

    if not args.input:
        return _fail("no input path given; pass the verdict-matrix JSON file")

    conflict = _check_output_paths(args)
    if conflict is not None:
        return conflict

    bootstrap: dict[str, object] | None = None
    if args.bootstrap:
        bootstrap = {
            "replicates": args.bootstrap_replicates,
            "seed": args.bootstrap_seed,
            "confidence_level": args.bootstrap_confidence_level,
        }
    elif (args.bootstrap_replicates != 2000 or args.bootstrap_seed != 0
            or args.bootstrap_confidence_level != 0.95):
        return _fail(
            "--bootstrap-replicates/--bootstrap-seed/"
            "--bootstrap-confidence-level require --bootstrap")

    try:
        report = audit_file(args.input, bootstrap=bootstrap)
    except FileNotFoundError:
        return _fail(f"input file not found: {args.input}")
    except IsADirectoryError:
        return _fail(
            f"input path is a directory, not a verdict-matrix file: "
            f"{args.input}")
    except OSError as exc:
        # Unreadable, a broken symlink, a special file: a real condition the
        # caller can act on, and previously a traceback with exit 1.
        return _fail(f"cannot read input file {args.input}: {_reason(exc)}")
    except GateAuditInputError as exc:
        return _fail(str(exc))

    rendered = render_json(report, pretty=args.pretty)
    if args.out:
        failure = _write(args.out, rendered + "\n", "JSON report")
        if failure is not None:
            return failure
    else:
        print(rendered)
    if args.markdown:
        failure = _write(
            args.markdown, render_markdown(report), "Markdown summary")
        if failure is not None:
            return failure
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
