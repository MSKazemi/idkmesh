#!/usr/bin/env python3
"""Deterministic repository-structure observatory for IDKMesh.

Repository Homeostasis Engine (RHE) v0 observes repository structure and
proposes bounded restructures. It never moves, deletes, or rewrites repository
files itself.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

VERSION = "0.1"
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
VIRTUAL_REPO_LINK_RE = re.compile(
    r"^(?:\.\./)+(?:issues|pull|discussions|actions|releases|compare|commit)(?:/|$)"
)


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    path: str
    detail: str
    suggested_action: str


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def iter_files(root: Path, excluded_dirs: set[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in excluded_dirs for part in rel.parts):
            continue
        yield path


def is_virtual_repo_link(raw: str) -> bool:
    """Return True for GitHub repository routes that are not filesystem paths."""
    target = raw.strip().split("#", 1)[0].split("?", 1)[0]
    return bool(VIRTUAL_REPO_LINK_RE.match(target))


def normalize_link_target(source: Path, raw: str, root: Path) -> Path | None:
    target = raw.strip().split("#", 1)[0].split("?", 1)[0]
    if (
        not target
        or target.startswith(("http://", "https://", "mailto:", "tel:", "data:"))
        or is_virtual_repo_link(raw)
    ):
        return None
    target = target.replace("%20", " ")
    if target.startswith("/"):
        candidate = root / target.lstrip("/")
    else:
        candidate = source.parent / target
    return candidate.resolve()


def git_count(root: Path, args: list[str]) -> int | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def git_changed_files(root: Path, base: str) -> int | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", f"{base}..HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return len({line for line in result.stdout.splitlines() if line.strip()})


def bucket_destination(path: str, config: dict) -> str | None:
    upper = PurePosixPath(path).name.upper()
    for rule in config.get("destination_rules", []):
        if any(token.upper() in upper for token in rule.get("filename_contains", [])):
            return rule.get("destination")
    return None


def analyze(root: Path, config: dict) -> dict:
    excluded = set(config.get("excluded_directories", []))
    files = list(iter_files(root, excluded))
    markdown = [p for p in files if p.suffix.lower() in {".md", ".markdown"}]
    root_markdown = [p for p in markdown if len(p.relative_to(root).parts) == 1]

    allowed_root = set(config.get("allowed_root_files", []))
    root_excess = sorted(
        p.relative_to(root).as_posix()
        for p in root_markdown
        if p.name not in allowed_root
    )

    max_doc_bytes = int(config.get("thresholds", {}).get("max_document_bytes", 20000))
    oversized = sorted(
        (p.relative_to(root).as_posix(), p.stat().st_size)
        for p in markdown
        if p.stat().st_size > max_doc_bytes
    )

    dir_counts: Counter[str] = Counter()
    for path in files:
        rel = path.relative_to(root)
        dir_counts[rel.parent.as_posix()] += 1
    max_dir_files = int(config.get("thresholds", {}).get("max_files_per_directory", 30))
    crowded_dirs = sorted((d, n) for d, n in dir_counts.items() if n > max_dir_files)

    markdown_rel = {p.relative_to(root).as_posix(): p for p in markdown}
    inbound: Counter[str] = Counter()
    broken_links: list[tuple[str, str]] = []

    for source in markdown:
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for raw in LINK_RE.findall(text):
            candidate = normalize_link_target(source, raw, root)
            if candidate is None:
                continue
            try:
                candidate.relative_to(root)
            except ValueError:
                broken_links.append((source.relative_to(root).as_posix(), raw))
                continue

            resolved = candidate
            if candidate.is_dir():
                if (candidate / "README.md").exists():
                    resolved = candidate / "README.md"
                elif (candidate / "index.md").exists():
                    resolved = candidate / "index.md"

            if not resolved.exists():
                broken_links.append((source.relative_to(root).as_posix(), raw))
                continue

            rel = resolved.relative_to(root).as_posix()
            if rel in markdown_rel:
                inbound[rel] += 1

    orphan_exempt_prefixes = tuple(config.get("orphan_exempt_prefixes", []))
    orphan_exempt_paths = set(config.get("orphan_exempt_paths", []))
    entrypoints = set(config.get("entrypoint_documents", []))
    orphans: list[str] = []
    for rel in sorted(markdown_rel):
        if (
            rel in entrypoints
            or rel in orphan_exempt_paths
            or rel.startswith(orphan_exempt_prefixes)
        ):
            continue
        if inbound[rel] == 0:
            orphans.append(rel)

    proposals = []
    for path in root_excess:
        destination = bucket_destination(path, config)
        if destination:
            proposals.append(
                {
                    "rule": "MoveRootDocument",
                    "path": path,
                    "destination": destination,
                    "risk": "low-medium",
                    "reason": (
                        "Non-entrypoint Markdown at repository root increases navigation pressure."
                    ),
                }
            )
    for path, size in oversized:
        proposals.append(
            {
                "rule": "ReviewOversizedDocument",
                "path": path,
                "destination": None,
                "risk": "medium",
                "reason": (
                    f"Document size {size} exceeds configured threshold {max_doc_bytes}; "
                    "split only if coherent subgraphs exist."
                ),
            }
        )
    for directory, count in crowded_dirs:
        proposals.append(
            {
                "rule": "ReviewCrowdedDirectory",
                "path": directory,
                "destination": None,
                "risk": "medium",
                "reason": f"Directory contains {count} files, above threshold {max_dir_files}.",
            }
        )

    thresholds = config.get("thresholds", {})
    root_limit = max(1, int(thresholds.get("root_markdown_soft_limit", 12)))
    root_pressure = min(1.0, len(root_excess) / root_limit)
    broken_pressure = min(
        1.0,
        len(broken_links) / max(1, int(thresholds.get("broken_link_pressure_at", 5))),
    )
    orphan_ratio = len(orphans) / max(1, len(markdown))
    oversized_pressure = min(
        1.0,
        len(oversized) / max(1, int(thresholds.get("oversized_pressure_at", 5))),
    )
    directory_pressure = min(
        1.0,
        len(crowded_dirs) / max(1, int(thresholds.get("crowded_directory_pressure_at", 4))),
    )

    pressure = round(
        100.0
        * (
            0.35 * root_pressure
            + 0.25 * broken_pressure
            + 0.20 * min(1.0, orphan_ratio * 4.0)
            + 0.10 * oversized_pressure
            + 0.10 * directory_pressure
        ),
        2,
    )

    epoch_cfg = config.get("evolution_epoch", {})
    base_ref = epoch_cfg.get("baseline_ref")
    commits_since = (
        git_count(root, ["rev-list", "--count", f"{base_ref}..HEAD"])
        if base_ref
        else None
    )
    changed_files_since = git_changed_files(root, base_ref) if base_ref else None

    epoch_due = False
    reasons = []
    if commits_since is not None and commits_since >= int(epoch_cfg.get("commit_interval", 25)):
        epoch_due = True
        reasons.append(f"{commits_since} commits since structural baseline")
    if changed_files_since is not None and changed_files_since >= int(
        epoch_cfg.get("changed_file_interval", 15)
    ):
        epoch_due = True
        reasons.append(f"{changed_files_since} unique files changed since structural baseline")
    pressure_high = float(epoch_cfg.get("pressure_high", 60))
    if pressure >= pressure_high:
        epoch_due = True
        reasons.append(f"structural pressure {pressure} >= {pressure_high}")

    restructure_due = epoch_due and bool(proposals or broken_links or orphans)

    findings: list[Finding] = []
    for path in root_excess:
        findings.append(
            Finding(
                "root_document_pressure",
                "warning",
                path,
                "Root-level Markdown is outside the configured entrypoint/health-file allowlist.",
                (
                    "Consider MoveRootDocument to "
                    f"{bucket_destination(path, config) or 'a semantically appropriate docs/ module'} "
                    "via reviewed PR."
                ),
            )
        )
    for source, raw in broken_links:
        findings.append(
            Finding(
                "broken_internal_link",
                "error",
                source,
                f"Internal link target does not resolve: {raw}",
                "Repair or explicitly supersede the reference before structural auto-promotion.",
            )
        )
    for path in orphans:
        findings.append(
            Finding(
                "orphan_document",
                "warning",
                path,
                "Document has no inbound Markdown link from the scanned graph.",
                "Link from a canonical index/parent or mark/archive it intentionally.",
            )
        )
    for path, size in oversized:
        findings.append(
            Finding(
                "oversized_document",
                "info",
                path,
                f"Document is {size} bytes (> {max_doc_bytes}).",
                "Review for coherent split points; size alone is not sufficient reason to split.",
            )
        )

    return {
        "engine": "IDKMesh Repository Homeostasis Engine",
        "version": VERSION,
        "metrics": {
            "files": len(files),
            "markdown_files": len(markdown),
            "root_markdown_files": len(root_markdown),
            "root_excess_documents": len(root_excess),
            "broken_internal_links": len(broken_links),
            "orphan_documents": len(orphans),
            "orphan_ratio": round(orphan_ratio, 4),
            "oversized_documents": len(oversized),
            "crowded_directories": len(crowded_dirs),
            "structural_pressure": pressure,
            "commits_since_structural_baseline": commits_since,
            "changed_files_since_structural_baseline": changed_files_since,
        },
        "epoch": {
            "due": epoch_due,
            "restructure_due": restructure_due,
            "reasons": reasons,
            "baseline_ref": base_ref,
        },
        "findings": [asdict(finding) for finding in findings],
        "proposals": proposals,
        "safety": {
            "automatic_moves": False,
            "automatic_deletions": False,
            "automatic_semantic_merges": False,
            "requires_review_for_structure_changes": True,
        },
    }


def render_markdown(report: dict) -> str:
    metrics = report["metrics"]
    epoch = report["epoch"]
    lines = [
        "# Repository Homeostasis Report",
        "",
        f"Generated by RHE v{report['version']}.",
        "",
        "## Structural state",
        "",
        f"- Structural pressure: **{metrics['structural_pressure']} / 100**",
        f"- Files: {metrics['files']} ({metrics['markdown_files']} Markdown)",
        f"- Root Markdown files: {metrics['root_markdown_files']}",
        f"- Root documents outside allowlist: {metrics['root_excess_documents']}",
        f"- Broken internal links: {metrics['broken_internal_links']}",
        f"- Orphan documents: {metrics['orphan_documents']} ({metrics['orphan_ratio']:.1%})",
        f"- Oversized documents: {metrics['oversized_documents']}",
        f"- Crowded directories: {metrics['crowded_directories']}",
        "",
        "## Evolution epoch",
        "",
        f"- Epoch due: **{'yes' if epoch['due'] else 'no'}**",
        (
            "- Restructure proposal justified: "
            f"**{'yes' if epoch['restructure_due'] else 'no'}**"
        ),
    ]
    if epoch["reasons"]:
        lines.append("- Trigger reasons:")
        lines.extend(f"  - {reason}" for reason in epoch["reasons"])

    lines.extend(["", "## Candidate structural rewrites", ""])
    if report["proposals"]:
        for proposal in report["proposals"][:50]:
            destination = (
                f" -> `{proposal['destination']}`" if proposal.get("destination") else ""
            )
            lines.append(
                f"- **{proposal['rule']}** `{proposal['path']}`{destination} "
                f"({proposal['risk']}): {proposal['reason']}"
            )
    else:
        lines.append("No structural rewrite candidates crossed deterministic proposal rules.")

    lines.extend(
        [
            "",
            "## Safety boundary",
            "",
            (
                "RHE v0 is **proposal-only**. It does not move/delete files or merge "
                "structural changes. Structural proposals must be executed in a branch/PR, "
                "with links/tests/invariants rechecked and independent human review before merge."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", default=".idkmesh/repository-homeostasis.json")
    parser.add_argument("--json-output", default="artifacts/repository-homeostasis.json")
    parser.add_argument("--md-output", default="artifacts/repository-homeostasis.md")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    config = load_config((root / args.config).resolve())
    report = analyze(root, config)

    json_output = (root / args.json_output).resolve()
    md_output = (root / args.md_output).resolve()
    json_output.parent.mkdir(parents=True, exist_ok=True)
    md_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    md_output.write_text(render_markdown(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "structural_pressure": report["metrics"]["structural_pressure"],
                "epoch_due": report["epoch"]["due"],
                "restructure_due": report["epoch"]["restructure_due"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
