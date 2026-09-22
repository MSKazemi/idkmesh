"""``idkmesh`` command-line interface.\n\nCommands stay deliberately thin: reusable logic lives in product modules so it\ncan be tested without a process boundary. Connector inspection is read-only;\ngate-audit keeps its existing diagnostic behavior.\n"""\n\nfrom __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
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
            "IDKMesh verification and connector tooling. 'gate-audit' measures how many "
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

    connections = sub.add_parser(
        "connections",
        help="validate, list, or inspect connector configuration",
        description=(
            "Read-only connector inspection. The current probe path uses "
            "offline fake drivers only; it does not contact live providers, "
            "materialize secrets, dispatch work, or grant repository authority."
        ),
    )
    connection_sub = connections.add_subparsers(
        dest="connections_command",
        required=True,
    )

    validate = connection_sub.add_parser(
        "validate",
        help="validate a connector-profile JSON document",
    )
    validate.add_argument("profile", help="path to connector-profile JSON")
    validate.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit deterministic machine-readable JSON",
    )

    list_cmd = connection_sub.add_parser(
        "list",
        help="list normalized connector metadata from a profile",
    )
    list_cmd.add_argument("profile", help="path to connector-profile JSON")
    list_cmd.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit deterministic machine-readable JSON",
    )

    probe = connection_sub.add_parser(
        "probe",
        help="probe connector profiles through offline fake drivers",
    )
    probe.add_argument("profile", help="path to connector-profile JSON")
    probe.add_argument(
        "--checked-at",
        help="explicit observation timestamp (default: current UTC time)",
    )
    probe.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit machine-readable JSON",
    )

    doctor = sub.add_parser(
        "doctor",
        help="summarize connector readiness without dispatching work",
        description=(
            "Validate and inspect connector profiles using the offline probe "
            "contract. FAIL means configuration/driver health blocks routing; "
            "WARN means disabled/degraded; PASS means healthy in this offline view."
        ),
    )
    doctor.add_argument("profile", help="path to connector-profile JSON")
    doctor.add_argument(
        "--checked-at",
        help="explicit observation timestamp (default: current UTC time)",
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit machine-readable JSON",
    )

    route = sub.add_parser(
        "route",
        help="explain provider-neutral connector routing",
    )
    route_sub = route.add_subparsers(dest="route_command", required=True)
    explain = route_sub.add_parser(
        "explain",
        help="explain eligible/rejected connectors for a routing decision",
    )
    explain.add_argument("profile", help="path to connector-profile JSON")
    explain.add_argument("decision", help="path to routing-decision JSON")
    explain.add_argument(
        "--checked-at",
        help="explicit observation timestamp (default: current UTC time)",
    )
    explain.add_argument(
        "--cost",
        action="append",
        default=[],
        metavar="CONNECTION_ID=USD",
        help="runtime project cost for a connector; repeat as needed",
    )
    explain.add_argument(
        "--auto-select",
        action="store_true",
        help="apply deterministic auto-selection after eligibility filtering",
    )
    explain.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit machine-readable JSON",
    )

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


def _observation_time(value: str | None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _connection_summary(config) -> dict[str, object]:
    return {
        "id": config.id,
        "kind": config.kind,
        "driver": config.driver,
        "enabled": config.enabled,
        "auth_ref_configured": config.secret_ref is not None,
        "capability_tiers": sorted(config.capability_tiers),
        "task_classes": sorted(config.task_classes),
        "tools": sorted(config.tools),
        "candidate_types": sorted(config.candidate_types),
        "max_risk": config.max_risk,
        "external_processing": config.external_processing,
        "project_spend_usd_max": config.project_spend_usd_max,
        "max_concurrency": config.max_concurrency,
    }


def _connections_error(exc, *, json_output: bool) -> int:
    if json_output:
        payload = {
            "valid": False,
            "error": {
                "code": getattr(exc, "code", "connector_profile_error"),
                "path": getattr(exc, "path", "$"),
                "message": str(exc),
            },
        }
        print(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
        return 2
    return _fail(str(exc))


def _run_connections(args: argparse.Namespace) -> int:
    from idkmesh.connector_profiles import (
        ConnectorProfileError,
        load_connector_profile_document,
    )

    try:
        configs = load_connector_profile_document(args.profile)
    except ConnectorProfileError as exc:
        return _connections_error(exc, json_output=args.json_output)

    summaries = [_connection_summary(config) for config in configs]

    if args.connections_command == "validate":
        if args.json_output:
            print(
                json.dumps(
                    {
                        "valid": True,
                        "count": len(summaries),
                        "connections": summaries,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            print(f"valid: {len(summaries)} connector profile(s)")
            for item in summaries:
                print(f"- {item['id']} ({item['kind']}/{item['driver']})")
        return 0

    if args.connections_command == "list":
        if args.json_output:
            print(
                json.dumps(
                    {
                        "count": len(summaries),
                        "connections": summaries,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            print("id\tkind\tdriver\tenabled\ttiers\tmax_risk")
            for item in summaries:
                tiers = ",".join(item["capability_tiers"])
                enabled = "yes" if item["enabled"] else "no"
                print(
                    f"{item['id']}\t{item['kind']}\t{item['driver']}\t"
                    f"{enabled}\t{tiers}\t{item['max_risk']}"
                )
        return 0

    if args.connections_command == "probe":
        from idkmesh.connector_inspection import inspect_connectors

        checked_at = _observation_time(args.checked_at)
        inspected = inspect_connectors(configs, checked_at=checked_at)
        payload = {
            "checked_at": checked_at,
            "connections": [item.to_dict() for item in inspected],
        }
        if args.json_output:
            print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        else:
            print("id\tstatus\tdriver\treason")
            for item in inspected:
                if item.error_code is not None:
                    status = "error"
                    reason = item.error_code
                else:
                    status = item.probe.status
                    reason = (
                        item.probe.failure.code
                        if item.probe and item.probe.failure
                        else "-"
                    )
                print(
                    f"{item.config.id}\t{status}\t"
                    f"{item.config.kind}/{item.config.driver}\t{reason}"
                )
        return 0

    return 2


def _run_doctor(args: argparse.Namespace) -> int:
    from idkmesh.connector_inspection import doctor_report, inspect_connectors
    from idkmesh.connector_profiles import (
        ConnectorProfileError,
        load_connector_profile_document,
    )

    try:
        configs = load_connector_profile_document(args.profile)
    except ConnectorProfileError as exc:
        return _connections_error(exc, json_output=args.json_output)

    checked_at = _observation_time(args.checked_at)
    report = doctor_report(
        inspect_connectors(configs, checked_at=checked_at)
    )
    payload = {"checked_at": checked_at, **report}
    if args.json_output:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print(f"doctor: {report['status']}")
        for item in report["connections"]:
            print(
                f"- {item['connection_id']}: "
                f"{item['state']} ({item['reason']})"
            )
    return 1 if report["status"] == "FAIL" else 0


def _run_route(args: argparse.Namespace) -> int:
    from idkmesh.connector_inspection import (
        ConnectorInspectionError,
        explain_route,
        inspect_connectors,
        load_routing_decision_document,
        parse_connector_costs,
    )
    from idkmesh.connector_profiles import (
        ConnectorProfileError,
        load_connector_profile_document,
    )

    try:
        configs = load_connector_profile_document(args.profile)
        decision = load_routing_decision_document(args.decision)
        costs = parse_connector_costs(args.cost)
    except (ConnectorProfileError, ConnectorInspectionError) as exc:
        return _connections_error(exc, json_output=args.json_output)

    checked_at = _observation_time(args.checked_at)
    report = explain_route(
        decision,
        inspect_connectors(configs, checked_at=checked_at),
        connector_costs=costs,
        auto_select=args.auto_select,
    )
    payload = {"checked_at": checked_at, **report}
    if args.json_output:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print("eligible:")
        if report["eligible"]:
            for item in report["eligible"]:
                print(
                    f"- {item['connection_id']}: "
                    f"{item['supported_tier']}"
                )
        else:
            print("- none")
        print("ineligible:")
        if report["ineligible"]:
            for item in report["ineligible"]:
                print(
                    f"- {item['connection_id']}: "
                    + ",".join(item["reasons"])
                )
        else:
            print("- none")
        print(
            "selected: "
            + (report["selected_connection_id"] or "none")
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "connections":
        return _run_connections(args)
    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "route":
        return _run_route(args)
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

    try:
        report = audit_file(args.input)
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
