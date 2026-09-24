"""IDKMesh command-line interface.

Command handlers stay deliberately thin. Product logic lives in reusable
modules so it can be tested and embedded without a process boundary.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import stat
import sys
from pathlib import Path

from idkmesh import __version__
from idkmesh.gate_audit import (
    GateAuditInputError,
    audit_file,
    render_json,
    render_markdown,
)
from idkmesh.steward_report import (
    StewardReportInputError,
    load_report as load_steward_report,
    render_summary as render_steward_summary,
)
from idkmesh.steward_history import (
    StewardHistoryInputError,
    load_history as load_steward_history,
    render_history_json,
    render_history_text,
)
from idkmesh.marginal_evidence import (
    MarginalEvidenceInputError,
    analyze_file as analyze_marginal_file,
    render_json as render_marginal_json,
)
from idkmesh.marginal_evidence_benchmark import (
    MarginalEvidenceBenchmarkInputError,
    benchmark_file as benchmark_marginal_file,
    referenced_paths as marginal_benchmark_referenced_paths,
    render_json as render_marginal_benchmark_json,
)
from idkmesh.local_ui_security import MAX_BODY_BYTES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idkmesh",
        description=(
            "IDKMesh local evidence tools. Inspect swarm runs with "
            "'control-tower', steward runs with 'steward-report' and "
            "'steward-history', and verifier panels with 'gate-audit'."),
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
            "verifier panel accuracy, pairwise error correlation, panel error, effective "
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

    gm = sub.add_parser(
        "gate-marginal",
        help="measure what one additional verifier adds to an existing panel",
        description=(
            "Analyze add-one verifier contribution against the same "
            "ground-truthed verdict matrix and gate rule. This command is "
            "diagnostic only: it does not rank/select a verifier, dispatch "
            "work, approve an EvaluatorPlan, accept a candidate, or merge."),
    )
    gm.add_argument("input", help="path to the verdict-matrix JSON file")
    gm.add_argument(
        "--current", action="append", required=True, metavar="VERIFIER_ID",
        help=(
            "verifier already in the current panel; repeat for each panel "
            "member"))
    gm.add_argument(
        "--candidate", action="append", metavar="VERIFIER_ID",
        help=(
            "candidate verifier to analyze; repeat as needed. If omitted, "
            "analyze every verifier not already in --current"))
    gm.add_argument(
        "--out", metavar="PATH",
        help="write the JSON report here (default: stdout)")
    gm.add_argument(
        "--pretty", action="store_true",
        help="pretty-print the JSON report")
    gm.add_argument(
        "--bootstrap", action="store_true",
        help=(
            "add paired candidate-row bootstrap intervals for panel-error and "
            "effective-vote deltas"))
    gm.add_argument(
        "--bootstrap-replicates", type=int, default=2000, metavar="N",
        help="bootstrap resample count; requires --bootstrap (default: 2000)")
    gm.add_argument(
        "--bootstrap-seed", type=int, default=0, metavar="N",
        help="bootstrap seed; requires --bootstrap (default: 0)")
    gm.add_argument(
        "--bootstrap-confidence-level", type=float, default=0.95,
        metavar="X",
        help=(
            "confidence level in (0, 1); requires --bootstrap "
            "(default: 0.95)"))

    gmb = sub.add_parser(
        "gate-marginal-benchmark",
        help="compare marginal verifier selection with simple held-out baselines",
        description=(
            "Use a versioned benchmark config to select candidate verifiers "
            "from design rows only, then evaluate the frozen selections on "
            "disjoint holdout rows. Diagnostic only: no live routing, "
            "EvaluatorPlan, acceptance, or merge authority."),
    )
    gmb.add_argument(
        "input",
        help="path to marginal-evidence-benchmark-config-v0.1 JSON",
    )
    gmb.add_argument(
        "--out",
        metavar="PATH",
        help="write the benchmark JSON report here (default: stdout)",
    )
    gmb.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print the JSON report",
    )
    connections = sub.add_parser(
        "connections",
        help="validate, list, import, store, or inspect connector configuration",
        description=(
            "Read-only connector inspection and local profile metadata persistence. "
            "The probe path uses offline fake drivers only; store commands persist "
            "safe normalized metadata only and never contact live providers, "
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

    import_cmd = connection_sub.add_parser(
        "import",
        help="import and validate connector profile into a local store",
        description=(
            "Validate a connector-profile document and persist safe normalized "
            "metadata into a local SQLite store. Secret material and credentials "
            "are never persisted."
        ),
    )
    import_cmd.add_argument("profile", help="path to connector-profile JSON")
    import_cmd.add_argument(
        "--store",
        required=True,
        metavar="PATH",
        help="path to local SQLite metadata store",
    )
    import_cmd.add_argument(
        "--updated-at",
        help="explicit update timestamp (default: current UTC time)",
    )
    import_cmd.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit deterministic machine-readable JSON",
    )

    stored_cmd = connection_sub.add_parser(
        "stored",
        help="list normalized connector metadata from a local store",
        description=(
            "Read normalized connector configuration metadata from a local SQLite store."
        ),
    )
    stored_cmd.add_argument(
        "--store",
        required=True,
        metavar="PATH",
        help="path to local SQLite metadata store",
    )
    stored_cmd.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit deterministic machine-readable JSON",
    )

    probe = connection_sub.add_parser(
        "probe",
        help="probe connector profiles through offline fake drivers",
        description=(
            "Read-only probe using offline fake drivers only. This command "
            "does not contact live providers, materialize secrets, or dispatch work."
        ),
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
            "contract without dispatching work. FAIL means configuration/driver health blocks routing; "
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
        description=(
            "Explain eligible/rejected connectors without external work or "
            "repository mutation. Selection is applied only with --auto-select."
        ),
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

    tower = sub.add_parser(
        "control-tower",
        help="open the local read-only Human Control Tower",
        description=(
            "Serve the IDKMesh Human Control Tower on 127.0.0.1. It renders "
            "existing Run Evidence Report v0.1 documents, recomputes their "
            "human-facing summary, and never runs workers, selects candidates, "
            "pushes Git, or merges."),
    )
    tower.add_argument(
        "report", nargs="?",
        help="optional Run Evidence Report v0.1 JSON file to preload")
    tower.add_argument(
        "--port", type=int, default=8770, metavar="PORT",
        help="loopback TCP port (default: 8770)")
    tower.add_argument(
        "--no-browser", action="store_true",
        help="serve the Control Tower without opening the default browser")

    sr = sub.add_parser(
        "steward-report",
        help="validate and summarize an Auto Draft PR Steward report",
        description=(
            "Read a local auto-draft-pr-steward-report-v0.1 JSON artifact, "
            "strictly validate its evidence and authority contract, and print "
            "a concise offline summary. No GitHub token or network access is "
            "used."),
    )
    sr.add_argument("input", help="path to steward-report.json")
    sr.add_argument(
        "--details", action="store_true",
        help="also list planned, created, and skipped branch records")

    sui = sub.add_parser(
        "steward-report-ui",
        help="open a local read-only dashboard for a steward report",
        description=(
            "Validate a local Auto Draft PR Steward report and serve a "
            "self-contained read-only dashboard on 127.0.0.1. The UI makes "
            "no live GitHub requests and exposes no mutation endpoint."),
    )
    sui.add_argument("input", help="path to steward-report.json")
    sui.add_argument(
        "--port", type=int, default=8766, metavar="PORT",
        help="loopback TCP port (default: 8766)")
    sui.add_argument(
        "--no-browser", action="store_true",
        help="serve the dashboard without opening the default browser")

    sh = sub.add_parser(
        "steward-history",
        help="aggregate multiple steward reports offline",
        description=(
            "Validate local Auto Draft PR Steward reports and aggregate them "
            "into one deterministic cross-run history. Inputs may be report "
            "files or directories; directory discovery reads only files named "
            "steward-report.json. No GitHub token or network access is used."),
    )
    sh.add_argument(
        "inputs", nargs="+", metavar="PATH",
        help="report file or directory containing steward-report.json files")
    sh.add_argument(
        "--details", action="store_true",
        help="include one human-readable line per run")
    sh.add_argument(
        "--json", action="store_true",
        help="emit the versioned machine-readable history JSON")
    sh.add_argument(
        "--pretty", action="store_true",
        help="pretty-print --json output")

    shi = sub.add_parser(
        "steward-history-ui",
        help="open a local read-only dashboard for steward history",
        description=(
            "Validate and aggregate local Auto Draft PR Steward reports, then "
            "serve a self-contained history dashboard on 127.0.0.1. The UI "
            "makes no live GitHub requests and exposes no mutation endpoint."),
    )
    shi.add_argument(
        "inputs", nargs="+", metavar="PATH",
        help="report file or directory containing steward-report.json files")
    shi.add_argument(
        "--port", type=int, default=8767, metavar="PORT",
        help="loopback TCP port (default: 8767)")
    shi.add_argument(
        "--no-browser", action="store_true",
        help="serve the dashboard without opening the default browser")
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
    for flag, path in (
        ("--out", getattr(args, "out", None)),
        ("--markdown", getattr(args, "markdown", None)),
    ):
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
        import sqlite3
        from idkmesh.connector_store import LocalStoreError

        # The store branches below catch OSError alongside LocalStoreError and
        # sqlite3.Error, so an OS-level store failure (an unwritable or
        # non-directory parent path) must classify as a store error too.
        # Profile loading raises ConnectorProfileError, never OSError, so this
        # cannot mislabel a profile failure.
        default_code = (
            "connector_store_error"
            if isinstance(exc, (LocalStoreError, sqlite3.Error, OSError))
            else "connector_profile_error"
        )
        payload = {
            "valid": False,
            "error": {
                "code": getattr(exc, "code", default_code),
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
    if args.connections_command == "stored":
        import sqlite3
        from idkmesh.connector_store import LocalMetadataStore, LocalStoreError

        store_path = Path(args.store)
        if not store_path.exists():
            return _connections_error(
                LocalStoreError(f"store database file not found: {args.store}"),
                json_output=args.json_output,
            )
        if store_path.is_dir():
            return _connections_error(
                LocalStoreError(f"store path is a directory: {args.store}"),
                json_output=args.json_output,
            )

        try:
            store = LocalMetadataStore(store_path)
            summaries = store.list_connections()
        except (LocalStoreError, sqlite3.Error, OSError) as exc:
            return _connections_error(exc, json_output=args.json_output)

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
            # `connections` is the shared C1-F control-metadata table and
            # `record_connection` takes free-form metadata, so a persisted row
            # need not carry this command's summary shape - and stored data
            # outlives the code that wrote it. Render what a row has instead of
            # raising an unhandled KeyError out of the CLI; JSON mode already
            # returns stored rows verbatim.
            print("id\tkind\tdriver\tenabled\ttiers\tmax_risk")
            for item in summaries:
                raw_tiers = item.get("capability_tiers")
                tiers = (
                    ",".join(str(tier) for tier in raw_tiers)
                    if isinstance(raw_tiers, (list, tuple))
                    else ""
                )
                enabled = {True: "yes", False: "no"}.get(item.get("enabled"), "?")
                print(
                    f"{item.get('id', '')}\t{item.get('kind', '')}\t"
                    f"{item.get('driver', '')}\t"
                    f"{enabled}\t{tiers}\t{item.get('max_risk', '')}"
                )
        return 0

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

    if args.connections_command == "import":
        import sqlite3
        from idkmesh.connector_store import LocalMetadataStore, LocalStoreError

        updated_at = _observation_time(getattr(args, "updated_at", None))
        store_path = Path(args.store)
        if store_path.is_dir():
            return _connections_error(
                LocalStoreError(f"store path is a directory: {args.store}"),
                json_output=args.json_output,
            )

        try:
            store = LocalMetadataStore(store_path)
            for item in summaries:
                store.record_connection(
                    item["id"],
                    metadata=item,
                    updated_at=updated_at,
                )
        except (LocalStoreError, sqlite3.Error, OSError) as exc:
            return _connections_error(exc, json_output=args.json_output)

        if args.json_output:
            print(
                json.dumps(
                    {
                        "imported": len(summaries),
                        "connections": summaries,
                        "store": str(store_path),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            print(f"imported: {len(summaries)} connector profile(s) into {store_path}")
            for item in summaries:
                print(f"- {item['id']} ({item['kind']}/{item['driver']})")
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
    try:
        report = explain_route(
            decision,
            inspect_connectors(configs, checked_at=checked_at),
            connector_costs=costs,
            auto_select=args.auto_select,
        )
    except ConnectorInspectionError as exc:
        return _connections_error(exc, json_output=args.json_output)

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
    if args.command == "control-tower":
        if not (0 <= args.port <= 65535):
            return _fail("--port must be between 0 and 65535")
        initial_text = None
        if args.report:
            path = Path(args.report)
            try:
                if not stat.S_ISREG(path.stat().st_mode):
                    return _fail(
                        f"run evidence path is not a regular JSON file: {args.report}")
                with path.open("rb") as handle:
                    payload = handle.read(MAX_BODY_BYTES + 1)
                if len(payload) > MAX_BODY_BYTES:
                    return _fail("run evidence report exceeds the 2 MiB local-UI limit")
                initial_text = payload.decode("utf-8-sig")
            except FileNotFoundError:
                return _fail(f"run evidence report not found: {args.report}")
            except IsADirectoryError:
                return _fail(
                    f"run evidence path is a directory, not a JSON report: "
                    f"{args.report}")
            except UnicodeDecodeError as exc:
                return _fail(
                    f"{args.report}: not UTF-8 text ({exc.reason} at byte "
                    f"{exc.start}); save the report as UTF-8")
            except OSError as exc:
                return _fail(
                    f"cannot read run evidence report {args.report}: "
                    f"{_reason(exc)}")
        from idkmesh.control_tower_ui import serve_control_tower
        try:
            serve_control_tower(
                initial_text,
                port=args.port,
                open_browser=not args.no_browser,
            )
        except ValueError as exc:
            return _fail(str(exc))
        except OSError as exc:
            return _fail(
                f"cannot start Control Tower on 127.0.0.1:{args.port}: "
                f"{_reason(exc)}")
        return 0

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

    if args.command in {"steward-report", "steward-report-ui"}:
        if args.command == "steward-report-ui" and not (0 <= args.port <= 65535):
            return _fail("--port must be between 0 and 65535")
        try:
            report = load_steward_report(args.input)
        except FileNotFoundError:
            return _fail(f"input file not found: {args.input}")
        except IsADirectoryError:
            return _fail(
                f"input path is a directory, not a steward report: {args.input}")
        except OSError as exc:
            return _fail(
                f"cannot read steward report {args.input}: {_reason(exc)}")
        except StewardReportInputError as exc:
            return _fail(str(exc))

        if args.command == "steward-report":
            print(render_steward_summary(report, details=args.details), end="")
            return 0

        from idkmesh.steward_report_ui import serve_steward_report_ui
        try:
            serve_steward_report_ui(
                report,
                port=args.port,
                open_browser=not args.no_browser,
            )
        except OSError as exc:
            return _fail(
                f"cannot start local steward dashboard on 127.0.0.1:{args.port}: "
                f"{_reason(exc)}")
        return 0

    if args.command in {"steward-history", "steward-history-ui"}:
        if args.command == "steward-history-ui":
            if not (0 <= args.port <= 65535):
                return _fail("--port must be between 0 and 65535")
        else:
            if args.pretty and not args.json:
                return _fail("--pretty requires --json")
            if args.details and args.json:
                return _fail("--details cannot be combined with --json")

        try:
            history = load_steward_history(args.inputs)
        except StewardHistoryInputError as exc:
            return _fail(str(exc))
        except OSError as exc:
            return _fail(f"cannot read steward history input: {_reason(exc)}")

        if args.command == "steward-history":
            if args.json:
                print(render_history_json(history, pretty=args.pretty))
            else:
                print(render_history_text(history, details=args.details), end="")
            return 0

        from idkmesh.steward_history_ui import serve_steward_history_ui
        try:
            serve_steward_history_ui(
                history,
                port=args.port,
                open_browser=not args.no_browser,
            )
        except OSError as exc:
            return _fail(
                f"cannot start local steward history dashboard on "
                f"127.0.0.1:{args.port}: {_reason(exc)}")
        return 0

    if args.command == "gate-marginal-benchmark":
        try:
            protected_paths = marginal_benchmark_referenced_paths(args.input)
        except FileNotFoundError:
            return _fail(f"input file not found: {args.input}")
        except IsADirectoryError:
            return _fail(
                f"input path is a directory, not a benchmark config file: "
                f"{args.input}")
        except OSError as exc:
            return _fail(
                f"cannot read benchmark input {args.input}: {_reason(exc)}")
        except MarginalEvidenceBenchmarkInputError as exc:
            return _fail(str(exc))

        if args.out:
            out_key = os.path.realpath(args.out)
            labels = ("benchmark config", "design matrix", "holdout matrix")
            for protected, label in zip(protected_paths, labels):
                if out_key == os.path.realpath(protected):
                    return _fail(
                        f"--out {args.out} is the {label}; writing the report "
                        "there would overwrite benchmark evidence"
                    )

        try:
            report = benchmark_marginal_file(args.input)
        except FileNotFoundError as exc:
            return _fail(f"benchmark referenced file not found: {exc.filename}")
        except IsADirectoryError as exc:
            return _fail(
                f"benchmark referenced path is a directory: {exc.filename}")
        except OSError as exc:
            return _fail(
                f"cannot read benchmark evidence: {_reason(exc)}")
        except MarginalEvidenceBenchmarkInputError as exc:
            return _fail(str(exc))

        rendered = render_marginal_benchmark_json(report, pretty=args.pretty)
        if args.out:
            failure = _write(
                args.out,
                rendered + "\n",
                "marginal-evidence benchmark JSON report",
            )
            if failure is not None:
                return failure
        else:
            print(rendered)
        return 0

    if args.command == "gate-marginal":
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
        elif (
            args.bootstrap_replicates != 2000
            or args.bootstrap_seed != 0
            or args.bootstrap_confidence_level != 0.95
        ):
            return _fail(
                "--bootstrap-replicates/--bootstrap-seed/"
                "--bootstrap-confidence-level require --bootstrap")

        try:
            report = analyze_marginal_file(
                args.input,
                current_verifier_ids=args.current,
                candidate_verifier_ids=args.candidate,
                bootstrap=bootstrap,
            )
        except FileNotFoundError:
            return _fail(f"input file not found: {args.input}")
        except IsADirectoryError:
            return _fail(
                f"input path is a directory, not a verdict-matrix file: "
                f"{args.input}")
        except OSError as exc:
            return _fail(
                f"cannot read input file {args.input}: {_reason(exc)}")
        except MarginalEvidenceInputError as exc:
            return _fail(str(exc))

        rendered = render_marginal_json(report, pretty=args.pretty)
        if args.out:
            failure = _write(
                args.out, rendered + "\n", "marginal-evidence JSON report")
            if failure is not None:
                return failure
        else:
            print(rendered)
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
