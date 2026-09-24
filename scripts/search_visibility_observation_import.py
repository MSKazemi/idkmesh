#!/usr/bin/env python3
"""Import completed cross-engine search observations into a candidate ledger.

The input CSV must be based on the deterministic worklist emitted by
scripts/search_visibility_observation_plan.py. Every plan-controlled field is
revalidated against the canonical full observation plan before an observation is
accepted.

This tool never queries a search engine and never invents visibility evidence.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from scripts import search_visibility_observation_plan as plan
except ModuleNotFoundError:  # direct "python scripts/..." execution
    import search_visibility_observation_plan as plan

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "evidence" / "search-visibility" / "observations.json"
PLAN_COLUMNS = (
    "plan_id",
    "engine",
    "product_surface",
    "surface",
    "evidence_class",
    "cluster",
    "mapped_intent",
    "query",
    "target_url",
)
RESULT_COLUMNS = (
    "observed_at",
    "surfaced",
    "position",
    "citation_url",
    "evidence_ref",
    "notes",
)
ALL_COLUMNS = PLAN_COLUMNS + RESULT_COLUMNS


class ObservationImportError(ValueError):
    """A completed observation row violates the canonical measurement contract."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ObservationImportError(f"{path}: expected a JSON object")
    return value


def _canonical_plan() -> dict[str, dict[str, Any]]:
    full = plan.build_plan(sample="full")
    return {item["plan_id"]: item for item in full["items"]}


def render_template(*, sample: str = "heads") -> str:
    work = plan.build_plan(sample=sample)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ALL_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for item in work["items"]:
        row = {column: "" for column in ALL_COLUMNS}
        for column in PLAN_COLUMNS:
            row[column] = item[column]
        writer.writerow(row)
    return stream.getvalue()


def _parse_observed_at(raw: str) -> tuple[str, str]:
    value = raw.strip()
    if not value:
        raise ObservationImportError("observed_at is required")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ObservationImportError(f"invalid observed_at timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ObservationImportError("observed_at must include a timezone")
    utc = parsed.astimezone(dt.timezone.utc)
    canonical = utc.isoformat().replace("+00:00", "Z")
    id_stamp = utc.strftime("%Y%m%dT%H%M%SZ")
    return canonical, id_stamp


def _parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ObservationImportError("surfaced must be exactly true or false")


def _parse_position(raw: str) -> int | None:
    value = raw.strip()
    if not value:
        return None
    try:
        position = int(value)
    except ValueError as exc:
        raise ObservationImportError(f"position must be a positive integer: {value!r}") from exc
    if position < 1:
        raise ObservationImportError("position must be a positive integer")
    return position


def _validate_optional_url(label: str, value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ObservationImportError(
            f"{label} must be an absolute http(s) URL when provided"
        )
    return value


def _observation_id(item: dict[str, Any], stamp: str) -> str:
    suffix = item["plan_id"].split("/", 1)[1]
    return f"manual/{suffix}/{stamp}"


def _validate_plan_fields(
    row: dict[str, str],
    canonical: dict[str, dict[str, Any]],
    *,
    row_number: int,
) -> dict[str, Any]:
    plan_id = row.get("plan_id", "").strip()
    if not plan_id:
        raise ObservationImportError(f"row {row_number}: plan_id is required")
    item = canonical.get(plan_id)
    if item is None:
        raise ObservationImportError(f"row {row_number}: unknown plan_id {plan_id!r}")
    for column in PLAN_COLUMNS:
        actual = row.get(column, "").strip()
        expected = str(item[column])
        if actual != expected:
            raise ObservationImportError(
                f"row {row_number}: {column} does not match canonical plan "
                f"({actual!r} != {expected!r})"
            )
    return item


def _row_to_observation(
    row: dict[str, str],
    canonical: dict[str, dict[str, Any]],
    *,
    row_number: int,
) -> dict[str, Any]:
    item = _validate_plan_fields(row, canonical, row_number=row_number)
    observed_at, stamp = _parse_observed_at(row.get("observed_at", ""))
    surfaced = _parse_bool(row.get("surfaced", ""))
    position = _parse_position(row.get("position", ""))
    citation_url = _validate_optional_url(
        "citation_url",
        row.get("citation_url", "").strip() or None,
    )
    evidence_ref = row.get("evidence_ref", "").strip() or None
    notes = row.get("notes", "").strip()
    if not notes:
        raise ObservationImportError(f"row {row_number}: notes are required")

    if not surfaced and (position is not None or citation_url):
        raise ObservationImportError(
            f"row {row_number}: a non-surfaced observation cannot claim "
            "position or citation_url"
        )

    observation: dict[str, Any] = {
        "id": _observation_id(item, stamp),
        "observed_at": observed_at,
        "engine": item["engine"],
        "surface": item["surface"],
        "evidence_class": item["evidence_class"],
        "mapped_intent": item["mapped_intent"],
        "query": item["query"],
        "target_url": item["target_url"],
        "surfaced": surfaced,
        "notes": notes,
    }
    if position is not None:
        observation["position"] = position
    if citation_url:
        observation["citation_url"] = citation_url
    if evidence_ref:
        observation["evidence_ref"] = evidence_ref
    return observation


def import_rows(
    input_csv: Path,
    *,
    ledger_path: Path = DEFAULT_LEDGER,
) -> dict[str, Any]:
    ledger = _load_json(ledger_path)
    if ledger.get("schema_version") != "0.1":
        raise ObservationImportError("unsupported search-visibility ledger version")
    observations = ledger.get("observations")
    if not isinstance(observations, list):
        raise ObservationImportError("ledger observations must be an array")

    canonical = _canonical_plan()
    existing_ids = {
        item.get("id")
        for item in observations
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    text = input_csv.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ObservationImportError("input CSV has no header")
    missing = [column for column in ALL_COLUMNS if column not in reader.fieldnames]
    if missing:
        raise ObservationImportError(
            "input CSV is missing required column(s): " + ", ".join(missing)
        )
    unexpected = [
        column
        for column in reader.fieldnames
        if column not in ALL_COLUMNS
    ]
    if unexpected:
        raise ObservationImportError(
            "input CSV has unexpected column(s): " + ", ".join(unexpected)
        )

    imported: list[dict[str, Any]] = []
    seen_new: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        observation = _row_to_observation(row, canonical, row_number=row_number)
        observation_id = observation["id"]
        if observation_id in existing_ids or observation_id in seen_new:
            raise ObservationImportError(
                f"row {row_number}: duplicate observation id {observation_id!r}"
            )
        seen_new.add(observation_id)
        imported.append(observation)

    if not imported:
        raise ObservationImportError("input CSV contains no completed observations")

    combined = [*observations, *imported]
    combined.sort(
        key=lambda item: (
            str(item.get("observed_at", "")),
            str(item.get("engine", "")),
            str(item.get("id", "")),
        )
    )
    return {
        "schema_version": "0.1",
        "observations": combined,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", choices=("heads", "full"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.template:
        if args.input or args.output:
            parser.error("--template cannot be combined with --input or --output")
        print(render_template(sample=args.template), end="")
        return 0

    if args.input is None or args.output is None:
        parser.error("--input and --output are required unless --template is used")

    try:
        candidate = import_rows(args.input, ledger_path=args.ledger)
    except (OSError, csv.Error, json.JSONDecodeError, ObservationImportError) as exc:
        parser.error(str(exc))

    if args.output.resolve() == args.ledger.resolve():
        parser.error(
            "refusing to overwrite the canonical ledger; write a candidate file "
            "and review the diff before replacing observations.json"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "total_observations": len(candidate["observations"]),
                "imported_observations": (
                    len(candidate["observations"])
                    - len(_load_json(args.ledger)["observations"])
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
