#!/usr/bin/env python3
"""Validate and regenerate the canonical IDKMesh capability truth matrix (#944)."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import re
from pathlib import Path
from typing import Any

from idkmesh.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "docs" / "capability-matrix-v1.json"
HUMAN_MATRIX = ROOT / "docs" / "CAPABILITY_MATRIX.md"
HOMEPAGE = ROOT / "docs" / "index.html"

STATUSES = {"implemented", "experimental", "planned"}
EVIDENCE_LEVELS = {
    "0": "planned",
    "1": "implemented",
    "2": "observed internal real run",
    "3": "controlled benchmark evidence",
    "4": "external reproduction/pilot",
    "5": "production-qualified",
}
ID_RE = re.compile(r"^CAP-[0-9]{3}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
README_COMMAND_RE = re.compile(r"(?m)^\s*idkmesh\s+([a-z0-9][a-z0-9-]*)\b")
HOME_START = "<!-- CAPABILITY_MATRIX_SUMMARY_START -->"
HOME_END = "<!-- CAPABILITY_MATRIX_SUMMARY_END -->"

REQUIRED_QUESTIONS = (
    "What exact task ran?",
    "What exact source/input revision was used?",
    "Why was a worker/connector eligible?",
    "What authority did the worker have?",
    "Was local execution sandboxed?",
    "What exact candidate was produced?",
    "Was candidate normalization/provenance verified?",
    "What independent verification occurred?",
    "How independent was the verifier panel?",
    "What evidence supports/rejects the candidate?",
    "Who can record a human decision?",
    "Who can integrate/merge?",
    "Can the run be replayed/audited?",
    "Are duplicate dispatches/idempotent retries safe?",
    "Are stale inputs rejected?",
    "Can another repository adopt the workflow?",
    "Is the API localhost-only or network/multi-user qualified?",
    "Has a capability been externally reproduced?",
    "Has swarm value been benchmarked against simpler baselines?",
    "Is a production claim supported by qualification evidence?",
)

REQUIRED_ROW_FIELDS = {
    "id",
    "question",
    "status",
    "evidence_level",
    "implementation_paths",
    "specification_paths",
    "cli_commands",
    "evidence_paths",
    "known_limitation",
    "last_verified_revision",
    "public_wording",
    "qualification_artifact",
}


def cli_commands() -> set[str]:
    parser = build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def _safe_repo_path(value: str) -> bool:
    return not value.startswith("/") and ".." not in Path(value).parts


def _validate_repo_path(
    cap_id: str,
    field: str,
    value: str,
    root: Path,
    errors: list[str],
) -> None:
    if not _safe_repo_path(value):
        errors.append(f"{cap_id}: unsafe {field} path {value!r}")
    elif not (root / value).exists():
        errors.append(f"{cap_id}: missing {field} path {value!r}")


def validate_document(document: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    if document.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")
    if document.get("evidence_levels") != EVIDENCE_LEVELS:
        errors.append("evidence_levels must exactly match the #943 evidence ladder")

    verified_revision = document.get("verified_revision")
    if not isinstance(verified_revision, str) or not REVISION_RE.fullmatch(
        verified_revision
    ):
        errors.append("verified_revision must be a 40-character lowercase commit SHA")

    rows = document.get("capabilities")
    if not isinstance(rows, list):
        return errors + ["capabilities must be an array"]
    if len(rows) < len(REQUIRED_QUESTIONS):
        errors.append("capability matrix must contain at least 20 rows")

    commands = cli_commands()
    seen: set[str] = set()
    by_id: dict[str, dict[str, Any]] = {}

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {index + 1}: must be an object")
            continue

        cap_id = row.get("id")
        if not isinstance(cap_id, str) or not ID_RE.fullmatch(cap_id):
            errors.append(f"row {index + 1}: invalid capability id {cap_id!r}")
            cap_id = f"row {index + 1}"
        elif cap_id in seen:
            errors.append(f"{cap_id}: duplicate capability id")
        else:
            seen.add(cap_id)
            by_id[cap_id] = row

        missing_fields = sorted(REQUIRED_ROW_FIELDS - set(row))
        if missing_fields:
            errors.append(
                f"{cap_id}: missing required fields {', '.join(missing_fields)}"
            )

        status = row.get("status")
        level = row.get("evidence_level")
        if status not in STATUSES:
            errors.append(f"{cap_id}: invalid status {status!r}")
        if isinstance(level, bool) or not isinstance(level, int) or level not in range(6):
            errors.append(f"{cap_id}: evidence_level must be an integer 0..5")
        if status == "planned" and level != 0:
            errors.append(f"{cap_id}: planned capability must remain evidence level 0")
        if (
            status in {"implemented", "experimental"}
            and isinstance(level, int)
            and level < 1
        ):
            errors.append(f"{cap_id}: {status} capability requires evidence level >= 1")
        if level == 5 and status != "implemented":
            errors.append(f"{cap_id}: evidence level 5 must have implemented status")

        for field in (
            "question",
            "known_limitation",
            "last_verified_revision",
            "public_wording",
        ):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{cap_id}: {field} must be non-empty text")

        row_revision = row.get("last_verified_revision")
        if isinstance(row_revision, str) and row_revision and not REVISION_RE.fullmatch(
            row_revision
        ):
            errors.append(
                f"{cap_id}: last_verified_revision must be a 40-character "
                "lowercase commit SHA"
            )

        for field in (
            "implementation_paths",
            "specification_paths",
            "evidence_paths",
            "cli_commands",
        ):
            values = row.get(field)
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value for value in values
            ):
                errors.append(
                    f"{cap_id}: {field} must be an array of non-empty strings"
                )
                continue
            if field.endswith("_paths"):
                for value in values:
                    _validate_repo_path(cap_id, field, value, root, errors)

        if status == "implemented":
            if not row.get("implementation_paths"):
                errors.append(f"{cap_id}: implemented row needs an implementation path")
            if not row.get("evidence_paths"):
                errors.append(f"{cap_id}: implemented row needs a test/evidence path")

        qualification = row.get("qualification_artifact")
        if qualification is not None and (
            not isinstance(qualification, str) or not qualification.strip()
        ):
            errors.append(
                f"{cap_id}: qualification_artifact must be null or non-empty text"
            )
        if isinstance(qualification, str) and qualification.strip():
            _validate_repo_path(
                cap_id,
                "qualification_artifact",
                qualification,
                root,
                errors,
            )
        if level == 5 and not qualification:
            errors.append(
                f"{cap_id}: evidence level 5 needs a dedicated qualification artifact"
            )

        for command in row.get("cli_commands", []):
            if command not in commands:
                errors.append(
                    f"{cap_id}: unknown idkmesh CLI subcommand {command!r}"
                )

    for offset, question in enumerate(REQUIRED_QUESTIONS, start=1):
        cap_id = f"CAP-{offset:03d}"
        row = by_id.get(cap_id)
        if row is None:
            errors.append(f"missing required capability {cap_id}")
        elif row.get("question") != question:
            errors.append(
                f"{cap_id}: required engineering question drifted; "
                f"expected {question!r}"
            )

    return errors


def validate_readme_commands(root: Path = ROOT) -> list[str]:
    known = cli_commands()
    text = (root / "README.md").read_text(encoding="utf-8")
    referenced = sorted(set(README_COMMAND_RE.findall(text)) - known)
    return [
        f"README.md references unknown idkmesh subcommand {command!r}"
        for command in referenced
    ]


def validate_release_note_reference(root: Path = ROOT) -> list[str]:
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = text.split("## [Unreleased]", 1)
    if len(unreleased) != 2:
        return ["CHANGELOG.md is missing the [Unreleased] section"]
    current = unreleased[1].split("\n## [", 1)[0]
    missing = []
    if "docs/capability-matrix-v1.json" not in current:
        missing.append("canonical capability-matrix path")
    if "verified_revision" not in current:
        missing.append("verified_revision")
    if "evidence level" not in current.lower():
        missing.append("evidence-level wording")
    if missing:
        return [
            "CHANGELOG.md [Unreleased] must bind release claims to the "
            "capability matrix: missing " + ", ".join(missing)
        ]
    return []


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(document: dict[str, Any]) -> str:
    count = len(document["capabilities"])
    lines = [
        # Jekyll front matter: the published page's search snippet.
        "---",
        'title: "IDKMesh Capability Truth Matrix"',
        f'description: "The public claim boundary for IDKMesh: {count} engineering '
        "capabilities, each with status, evidence level 0-5, allowed public "
        'wording, and known limitation."',
        "---",
        "",
        "# IDKMesh Capability Truth Matrix",
        "",
        "> Generated from `docs/capability-matrix-v1.json` by "
        "`scripts/check_capability_matrix.py`. Do not edit this table by hand.",
        "",
        "**Canonical data:** [`capability-matrix-v1.json`](capability-matrix-v1.json)  ",
        "**Evidence ladder:** 0 planned · 1 implemented · "
        "2 observed internal real run · 3 controlled benchmark · "
        "4 external reproduction/pilot · 5 production-qualified  ",
        f"**Baseline revision:** `{document['verified_revision']}`",
        "",
        "This is the public claim boundary for IDKMesh. A higher evidence level is "
        "never inferred from a lower one: implemented code is not automatically "
        "benchmark evidence, external reproduction, or production qualification.",
        "",
        "| ID | Engineering question | Status | Level | Allowed public wording | "
        "Known limitation |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in document["capabilities"]:
        lines.append(
            "| "
            + " | ".join(
                _md_cell(value)
                for value in (
                    row["id"],
                    row["question"],
                    row["status"],
                    row["evidence_level"],
                    row["public_wording"],
                    row["known_limitation"],
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Machine-checkable fields",
            "",
            "Each canonical JSON row carries the stable question ID, status, evidence "
            "level, implementation paths, specification paths, supported CLI commands, "
            "deterministic test/evidence paths, known limitation, last verified source "
            "revision, allowed public wording, and an explicit qualification artifact "
            "slot. Evidence level 5 requires a dedicated, existing qualification "
            "artifact rather than merely a non-empty generic evidence list.",
            "",
            "The same validator also checks the twenty required engineering questions, "
            "repository-local paths, actual top-level `idkmesh` subcommands, primary "
            "README command examples, the Unreleased changelog's capability-matrix/"
            "evidence-level linkage, and the "
            "generated Markdown/homepage projections.",
            "",
            "Run the drift guard locally with:",
            "",
            "```bash",
            "python scripts/check_capability_matrix.py",
            "```",
            "",
            "After changing the canonical JSON, regenerate the two derived surfaces with:",
            "",
            "```bash",
            "python scripts/check_capability_matrix.py --write",
            "```",
            "",
            "## Promotion rule",
            "",
            "Promoting a row is an evidence change, not a wording change. Update the "
            "canonical JSON only when the new implementation/evidence paths are committed "
            "and the public wording remains no stronger than the evidence level. Keep a "
            "limitation when it still applies even after implementation.",
            "",
        ]
    )
    return "\n".join(lines)


def render_homepage_block(document: dict[str, Any]) -> str:
    counts = Counter(row["status"] for row in document["capabilities"])
    highest = max((row["evidence_level"] for row in document["capabilities"]), default=0)
    return "\n".join(
        [
            HOME_START,
            '      <div class="card" id="capability-truth">',
            "        <h3>Capability truth: what works today?</h3>",
            '        <p class="muted">This compact projection is generated from the '
            'repository\'s canonical <a href="capability-matrix-v1.json">capability '
            "truth JSON</a>, not maintained as a second claim list.</p>",
            '        <p id="capability-summary"><strong>'
            f"{counts['implemented']} implemented</strong> · "
            f"{counts['experimental']} experimental · "
            f"{counts['planned']} planned. Highest evidence level currently "
            f"represented: <strong>{highest}/5</strong>.</p>",
            '        <p><a href="https://mskazemi.com/idkmesh/CAPABILITY_MATRIX.html">'
            "Read the human capability matrix →</a></p>",
            "      </div>",
            HOME_END,
        ]
    )


def _homepage_block(source: str) -> str | None:
    start = source.find(HOME_START)
    end = source.find(HOME_END)
    if start < 0 or end < 0 or end < start:
        return None
    return source[start : end + len(HOME_END)]


def validate_generated_surfaces(
    document: dict[str, Any],
    root: Path = ROOT,
) -> list[str]:
    errors: list[str] = []

    markdown_path = root / "docs" / "CAPABILITY_MATRIX.md"
    if not markdown_path.exists():
        errors.append("docs/CAPABILITY_MATRIX.md is missing; run --write")
    elif markdown_path.read_text(encoding="utf-8") != render_markdown(document):
        errors.append(
            "docs/CAPABILITY_MATRIX.md drifted from canonical JSON; run --write"
        )

    homepage_path = root / "docs" / "index.html"
    source = homepage_path.read_text(encoding="utf-8")
    actual = _homepage_block(source)
    if actual is None:
        errors.append("docs/index.html capability projection markers are missing")
    elif actual != render_homepage_block(document):
        errors.append(
            "docs/index.html capability projection drifted from canonical JSON; "
            "run --write"
        )

    return errors


def write_generated_surfaces(
    document: dict[str, Any],
    root: Path = ROOT,
) -> None:
    (root / "docs" / "CAPABILITY_MATRIX.md").write_text(
        render_markdown(document),
        encoding="utf-8",
    )

    homepage_path = root / "docs" / "index.html"
    source = homepage_path.read_text(encoding="utf-8")
    actual = _homepage_block(source)
    if actual is None:
        raise ValueError("docs/index.html capability projection markers are missing")
    homepage_path.write_text(
        source.replace(actual, render_homepage_block(document), 1),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument(
        "--write",
        action="store_true",
        help="regenerate human/site projections from the canonical JSON",
    )
    args = parser.parse_args()

    document = json.loads(args.matrix.read_text(encoding="utf-8"))
    errors = (
        validate_document(document)
        + validate_readme_commands()
        + validate_release_note_reference()
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    if args.write:
        write_generated_surfaces(document)
        print("regenerated capability truth projections")
        return 0

    errors = validate_generated_surfaces(document)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"capability truth matrix OK: {len(document['capabilities'])} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
