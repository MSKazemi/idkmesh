"""Offline Markdown evidence bundle for the Pages-disabled fallback (C14-H, #609).

GitHub Pages is an optional publication surface (C14-E). When it is disabled,
unavailable, or stale, the same public-safe evidence must still be readable
without any server. This module renders the *same* C14-D public-safe
projections that ``idkmesh.github_pages_site`` renders as HTML into a
self-contained, offline bundle of escaped Markdown and JSON files plus a
deterministic digest manifest. A separate, reviewed workflow could upload that
directory as an Actions artifact; this module changes no workflow and uploads
nothing.

The bundle is a *view*. It is never canonical evidence (an Actions artifact
expires and is not durable), it grants no dispatch, verification,
human-decision, write, push, integration, or merge authority, and it performs
no network, GitHub, or repository mutation. Digests prove only that the files
were not altered after rendering; they are not signatures and do not prove
functional correctness.

Layout (all paths are fixed, relative, POSIX)::

    README.md               health / active work / verification debt / all runs
    runs/<slug>.md          per-run provenance page
    data/runs/<slug>.json   canonical C14-D public projection (same bytes as Pages)
    outage/<slug>.json      offline locator from build_github_pages_outage_fallback
    MANIFEST.json           sha256 + size of every other file

Untrusted text (run, attempt and connector identifiers) is escaped for
Markdown, inline HTML, GitHub autolinks and mentions, and Liquid delimiters
before it reaches a ``.md`` file. Every input is re-validated by the shared
Pages validator, and :func:`verify_github_pages_fallback_bundle` re-renders the
bundle from its embedded projections so a hand-edited file fails even when its
manifest entry was recomputed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from idkmesh.github_pages_site import (
    MAX_RUNS,
    MAX_SITE_BYTES,
    GitHubPagesSiteError,
    _DISCLAIMER,
    _PR_URL_RE,
    _REPOSITORY_RE,
    _RUN_STATES,
    _is_active,
    _slug,
    _unverified_attempts,
    build_github_pages_outage_fallback,
    validate_public_projection,
)
from idkmesh.github_pages_writer import (
    GitHubPagesWriteError,
    _make_stage,
    _validate_file_map,
)
from idkmesh.github_public_evidence import render_github_public_evidence_json


SCHEMA_VERSION = "0.1"
MANIFEST_KIND = "idkmesh-pages-fallback-manifest"
MANIFEST_PATH = "MANIFEST.json"
README_PATH = "README.md"

# README + manifest, plus a Markdown page, a public JSON file and an outage
# locator per run.
MAX_BUNDLE_FILES = 2 + 3 * MAX_RUNS

_PATH_RES = (
    re.compile(r"README\.md\Z"),
    re.compile(r"MANIFEST\.json\Z"),
    re.compile(r"runs/[0-9a-f]{16}\.md\Z"),
    re.compile(r"data/runs/[0-9a-f]{16}\.json\Z"),
    re.compile(r"outage/[0-9a-f]{16}\.json\Z"),
)
_SHA256_HEX_RE = re.compile(r"[0-9a-f]{64}\Z")

_NOTICE = (
    "Offline fallback bundle of digest-bound public metadata, generated "
    "because GitHub Pages is optional and may be disabled or unavailable. "
    "It is a view, not canonical evidence: the canonical record is the linked "
    "GitHub Issue/PR and durable ledger. Availability of canonical evidence "
    "is unverified here. Digests detect alteration after rendering only; "
    "they are not signatures. This bundle grants no dispatch, verification, "
    "human-decision, merge, or write authority."
)

# Characters made inert by numeric entities in Markdown text: HTML and entity
# starts, backslash and code/emphasis/link/table/heading/image syntax, Liquid
# and template delimiters, mentions, autolink schemes (":" and "." break
# "http:" and "www."), and "$" (math).
_MD_ESCAPED = frozenset("&<>\"'\\`*_[]()#|!~{}@$:.")
_FORBIDDEN_CONTROL_RE = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f‎‏  "
    "‪-‮⁦-⁩﻿]"
)

_CLAIMS = {
    "canonical_evidence": False,
    "github_mutation_performed": False,
    "human_decision_authority": False,
    "integration_authority": False,
    "network_access": False,
    "pages_required_for_coordination": False,
    "signed": False,
    "verification_authority": False,
}


class GitHubPagesFallbackError(ValueError):
    """Fail-closed fallback-bundle render, verify, read or write error."""


@dataclass(frozen=True)
class FallbackBundleReport:
    """Verified bundle summary; ``files`` is ``(path, size_bytes, sha256)``."""

    repository: str
    run_count: int
    files: tuple[tuple[str, int, str], ...]

    @property
    def total_bytes(self) -> int:
        return sum(size for _, size, _ in self.files)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GitHubPagesFallbackError(message)


def escape_markdown(value: Any) -> str:
    """Return ``value`` as inert, single-line Markdown text.

    Whitespace controls collapse to one space; other control and bidi
    formatting characters are refused (fail closed) rather than stripped.
    """

    text = str(value)
    _require(
        _FORBIDDEN_CONTROL_RE.search(text) is None,
        "text contains a forbidden control or bidirectional character",
    )
    text = " ".join(text.split())
    return "".join(
        f"&#{ord(ch)};" if ch in _MD_ESCAPED else ch for ch in text
    )


def _e(value: Any) -> str:
    return escape_markdown(value)


def _table(headers: Iterable[str], rows: list[list[str]]) -> str:
    """Rows hold already-escaped cells."""

    header = "| " + " | ".join(_e(h) for h in headers) + " |"
    rule = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, rule, *body]) + "\n"


def _opt(value: Any) -> str:
    return "none" if value is None else _e(value)


def _run_link(projection: Mapping[str, Any]) -> str:
    run_id = projection["run"]["run_id"]
    return f"[{_e(run_id)}](runs/{_slug(run_id)}.md)"


def _candidate_cell(candidate: Mapping[str, Any] | None) -> str:
    if candidate is None:
        return "none"
    if candidate["type"] == "github_pull_request":
        url = str(candidate["url"])
        # Re-assert the canonical shape: only characters that are inert inside
        # a Markdown link destination can reach this point.
        _require(
            _PR_URL_RE.fullmatch(url) is not None,
            "candidate PR URL is not canonical",
        )
        return (
            f"[PR #{_e(candidate['number'])}]({url}) at "
            f"{_e(candidate['head_sha'])}"
        )
    return f"artifact bundle {_e(candidate['digest'])}"


def _render_readme(
    repository: str, projections: list[Mapping[str, Any]]
) -> str:
    counts = {state: 0 for state in _RUN_STATES}
    for projection in projections:
        counts[projection["run"]["state"]] += 1
    active = [p for p in projections if _is_active(p)]
    debt = [(p, ids) for p in active if (ids := _unverified_attempts(p))]
    pending = [
        p for p in projections if p["human_decision_status"] == "pending"
    ]
    control_failures = [
        p
        for p in projections
        if p["evidence_summary"] is not None
        and p["evidence_summary"]["control_failure_present"]
    ]
    disagreements = [
        p
        for p in projections
        if p["evidence_summary"] is not None
        and p["evidence_summary"]["verification_disagreement"]
    ]
    health = _table(
        ["Measure", "Runs"],
        [
            ["Total runs", _e(len(projections))],
            ["Active runs", _e(len(active))],
            ["Verification debt", _e(len(debt))],
            ["Awaiting human decision", _e(len(pending))],
            ["Control failure present", _e(len(control_failures))],
            ["Verification disagreement", _e(len(disagreements))],
        ],
    )
    by_state = (
        _table(
            ["Run state", "Runs"],
            [[_e(s), _e(counts[s])] for s in _RUN_STATES if counts[s]],
        )
        if projections
        else "No public runs are published.\n"
    )
    active_table = (
        _table(
            ["Run", "State", "Human decision", "Attempts"],
            [
                [
                    _run_link(p),
                    _e(p["run"]["state"]),
                    _e(p["human_decision_status"]),
                    _e(len(p["attempts"])),
                ]
                for p in active
            ],
        )
        if active
        else "No active runs.\n"
    )
    debt_table = (
        _table(
            ["Run", "Unverified attempts", "State"],
            [
                [_run_link(p), _e(", ".join(ids)), _e(p["run"]["state"])]
                for p, ids in debt
            ],
        )
        if debt
        else "No verification debt.\n"
    )
    all_table = (
        _table(
            ["Run", "State", "WorkUnit digest", "Source revision"],
            [
                [
                    _run_link(p),
                    _e(p["run"]["state"]),
                    _e(p["run"]["work_unit_digest"]),
                    _e(p["run"]["source_revision"]),
                ]
                for p in projections
            ],
        )
        if projections
        else "No public runs are published.\n"
    )
    return (
        f"# IDKMesh public run evidence (offline fallback): {_e(repository)}\n\n"
        f"> {_NOTICE}\n\n"
        f"{_DISCLAIMER}\n\n"
        "## Project health\n\n" + health + "\n" + by_state + "\n"
        "## Active work\n\n" + active_table + "\n"
        "## Verification debt\n\n"
        "Active runs with a candidate that has no retained verification "
        "result yet.\n\n" + debt_table + "\n"
        "## All runs\n\n" + all_table + "\n"
        "Integrity: see `MANIFEST.json` for the SHA-256 digest of every "
        "other file.\n"
    )


def _render_run(repository: str, projection: Mapping[str, Any]) -> str:
    run = projection["run"]
    slug = _slug(run["run_id"])
    summary = projection["evidence_summary"]
    facts = _table(
        ["Field", "Value"],
        [
            ["Run", _e(run["run_id"])],
            ["State", _e(run["state"])],
            [
                "WorkUnit",
                f"{_e(run['work_unit_id'])} version "
                f"{_e(run['work_unit_version'])}",
            ],
            ["WorkUnit digest", _opt(run["work_unit_digest"])],
            ["Source revision", _opt(run["source_revision"])],
            ["Evidence report digest", _opt(run["evidence_report_digest"])],
            [
                "Human decision",
                f"{_e(projection['human_decision_status'])} "
                f"({_opt(run['human_decision_record_digest'])})",
            ],
        ],
    )
    attempt_rows = [
        [
            _e(a["order"]),
            _e(a["attempt_id"]),
            _e(a["connector_id"]),
            _e(a["state"]),
            _candidate_cell(a["candidate"]),
            _opt(a["result_manifest_digest"]),
            _opt(a["verification_semantic_digest"]),
            _e(a["evidence_state"] or "none"),
            _e(a["verifier_recommendation"] or "none"),
        ]
        for a in sorted(projection["attempts"], key=lambda a: a["order"])
    ]
    attempts = (
        _table(
            [
                "Order",
                "Attempt",
                "Connector",
                "State",
                "Candidate",
                "Result manifest",
                "Verification digest",
                "Evidence state",
                "Verifier recommendation",
            ],
            attempt_rows,
        )
        if attempt_rows
        else "No attempts recorded.\n"
    )
    summary_md = (
        "No retained evidence report.\n"
        if summary is None
        else _table(
            ["Measure", "Value"],
            [[_e(k), _e(v)] for k, v in sorted(summary.items())],
        )
    )
    return (
        f"# Run {_e(run['run_id'])}\n\n"
        f"[All runs for {_e(repository)}](../{README_PATH}) | "
        f"[public JSON projection](../data/runs/{slug}.json) | "
        f"[offline locator](../outage/{slug}.json)\n\n"
        "## Provenance\n\n" + facts + "\n## Attempts\n\n" + attempts
        + "\n## Evidence summary\n\n" + summary_md + "\n"
        f"{_DISCLAIMER}\n"
    )


def _json_text(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_manifest(repository: str, files: Mapping[str, str]) -> str:
    entries = [
        {
            "path": path,
            "size_bytes": len(text.encode("utf-8")),
            "sha256": _sha256(text),
        }
        for path, text in sorted(files.items())
    ]
    return _json_text(
        {
            "schema_version": SCHEMA_VERSION,
            "kind": MANIFEST_KIND,
            "repository": repository,
            "run_count": sum(1 for p in files if p.startswith("runs/")),
            "claims": dict(_CLAIMS),
            "files": entries,
        }
    )


def render_github_pages_fallback_bundle(
    projections: Iterable[Mapping[str, Any]],
    *,
    repository: str,
) -> dict[str, str]:
    """Return a deterministic ``path -> text`` offline bundle.

    ``projections`` must be C14-D public-safe projections for ``repository``;
    each is value-validated by the same validator the Pages renderer uses.
    Nothing is written and no input is mutated.
    """

    _require(
        isinstance(repository, str)
        and _REPOSITORY_RE.fullmatch(repository) is not None,
        "repository must be owner/name",
    )
    items = list(projections)
    _require(len(items) <= MAX_RUNS, f"at most {MAX_RUNS} runs may be bundled")
    seen: set[str] = set()
    slugs: set[str] = set()
    for projection in items:
        try:
            validate_public_projection(projection, repository)
        except GitHubPagesSiteError as exc:
            raise GitHubPagesFallbackError(str(exc)) from exc
        run_id = projection["run"]["run_id"]
        _require(run_id not in seen, "duplicate run_id in fallback input")
        seen.add(run_id)
        slug = _slug(run_id)
        _require(slug not in slugs, "run slug collision in fallback input")
        slugs.add(slug)

    items.sort(key=lambda p: p["run"]["run_id"])
    files: dict[str, str] = {README_PATH: _render_readme(repository, items)}
    for projection in items:
        slug = _slug(projection["run"]["run_id"])
        files[f"runs/{slug}.md"] = _render_run(repository, projection)
        files[f"data/runs/{slug}.json"] = render_github_public_evidence_json(
            projection
        )
        files[f"outage/{slug}.json"] = _json_text(
            build_github_pages_outage_fallback(
                projection, repository=repository
            )
        )
    files[MANIFEST_PATH] = _build_manifest(repository, files)
    total = sum(len(text.encode("utf-8")) for text in files.values())
    _require(
        total <= MAX_SITE_BYTES,
        f"generated bundle exceeds {MAX_SITE_BYTES} UTF-8 bytes",
    )
    return dict(sorted(files.items()))


def _strict_json(text: str, label: str) -> Any:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            _require(key not in result, f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise GitHubPagesFallbackError(
            f"{label}: non-standard JSON constant {value}"
        )

    try:
        return json.loads(
            text,
            object_pairs_hook=no_duplicates,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise GitHubPagesFallbackError(f"{label}: invalid JSON: {exc.msg}") from exc
    except RecursionError as exc:
        raise GitHubPagesFallbackError(f"{label}: JSON nesting too deep") from exc


def _check_manifest(manifest: Any, encoded: Mapping[str, bytes]) -> str:
    _require(isinstance(manifest, dict), "manifest must be a JSON object")
    expected_keys = {
        "schema_version",
        "kind",
        "repository",
        "run_count",
        "claims",
        "files",
    }
    _require(set(manifest) == expected_keys, "manifest has unexpected fields")
    _require(
        manifest["schema_version"] == SCHEMA_VERSION
        and manifest["kind"] == MANIFEST_KIND,
        "not a fallback manifest v0.1",
    )
    repository = manifest["repository"]
    _require(
        isinstance(repository, str)
        and _REPOSITORY_RE.fullmatch(repository) is not None,
        "manifest repository must be owner/name",
    )
    _require(manifest["claims"] == _CLAIMS, "manifest claims were altered")
    entries = manifest["files"]
    _require(isinstance(entries, list), "manifest files must be a list")
    listed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        _require(
            isinstance(entry, dict)
            and set(entry) == {"path", "size_bytes", "sha256"},
            "manifest file entry has unexpected fields",
        )
        path = entry["path"]
        _require(isinstance(path, str), "manifest path must be a string")
        _require(path not in listed, f"manifest lists {path!r} twice")
        _require(path != MANIFEST_PATH, "manifest must not list itself")
        size = entry["size_bytes"]
        _require(
            isinstance(size, int) and not isinstance(size, bool),
            "manifest size_bytes must be an integer",
        )
        _require(
            isinstance(entry["sha256"], str)
            and _SHA256_HEX_RE.fullmatch(entry["sha256"]) is not None,
            "manifest sha256 must be 64 lowercase hex characters",
        )
        listed[path] = entry
    _require(
        [e["path"] for e in entries] == sorted(listed),
        "manifest files are not sorted by path",
    )
    actual = set(encoded) - {MANIFEST_PATH}
    missing = sorted(set(listed) - actual)
    extra = sorted(actual - set(listed))
    _require(not missing, f"bundle is missing listed file(s): {missing}")
    _require(not extra, f"bundle has unlisted file(s): {extra}")
    for path, entry in listed.items():
        data = encoded[path]
        _require(
            entry["size_bytes"] == len(data),
            f"size mismatch for {path!r}",
        )
        _require(
            entry["sha256"] == hashlib.sha256(data).hexdigest(),
            f"digest mismatch for {path!r}",
        )
    return repository


def verify_github_pages_fallback_bundle(
    files: Mapping[str, str],
) -> FallbackBundleReport:
    """Verify a bundle file map; raise :class:`GitHubPagesFallbackError`.

    Checks, in order: path safety and size bounds, the exact layout, the
    manifest schema, claims, file set, sizes and SHA-256 digests, then that
    re-rendering the embedded public projections reproduces every file
    byte-for-byte (so escaping and content cannot have been edited).
    """

    try:
        encoded = _validate_file_map(files, max_files=MAX_BUNDLE_FILES)
    except GitHubPagesWriteError as exc:
        raise GitHubPagesFallbackError(str(exc)) from exc
    for path in encoded:
        _require(
            any(rx.fullmatch(path) for rx in _PATH_RES),
            f"unexpected file in fallback bundle: {path!r}",
        )
    _require(MANIFEST_PATH in encoded, "bundle has no MANIFEST.json")
    _require(README_PATH in encoded, "bundle has no README.md")
    try:
        manifest_text = encoded[MANIFEST_PATH].decode("utf-8")
    except UnicodeDecodeError as exc:  # pragma: no cover - map holds str
        raise GitHubPagesFallbackError("manifest is not UTF-8") from exc
    manifest = _strict_json(manifest_text, MANIFEST_PATH)
    repository = _check_manifest(manifest, encoded)

    projections: list[Mapping[str, Any]] = []
    for path in sorted(p for p in encoded if p.startswith("data/runs/")):
        projection = _strict_json(files[path], path)
        _require(isinstance(projection, dict), f"{path}: not a JSON object")
        projections.append(projection)
    _require(
        manifest["run_count"] == len(projections),
        "manifest run_count does not match the bundle",
    )
    expected = render_github_pages_fallback_bundle(
        projections, repository=repository
    )
    _require(
        set(expected) == set(files),
        "bundle file set differs from a fresh render of its projections",
    )
    for path, text in expected.items():
        _require(
            files[path] == text,
            f"{path!r} differs from a fresh render of its projections",
        )
    return FallbackBundleReport(
        repository=repository,
        run_count=len(projections),
        files=tuple(
            (path, len(data), hashlib.sha256(data).hexdigest())
            for path, data in encoded.items()
        ),
    )


def read_github_pages_fallback_dir(path: str | os.PathLike[str]) -> dict[str, str]:
    """Read a bundle directory into a file map without following symlinks.

    Refuses symlinks, special files, unrecognised layout depth, oversized
    trees and non-UTF-8 content. It does not verify digests; pass the result
    to :func:`verify_github_pages_fallback_bundle`.
    """

    root = Path(os.fspath(path))
    try:
        info = os.lstat(root)
    except OSError as exc:
        raise GitHubPagesFallbackError(
            f"cannot read bundle directory {root}: {exc.strerror or type(exc).__name__}"
        ) from exc
    _require(
        stat.S_ISDIR(info.st_mode),
        f"bundle path is not a real directory (symlinks are refused): {root}",
    )
    result: dict[str, str] = {}
    total = 0
    stack: list[tuple[Path, str]] = [(root, "")]
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    while stack:
        current, prefix = stack.pop()
        try:
            with os.scandir(current) as scan:
                entries = sorted(scan, key=lambda e: e.name)
        except OSError as exc:
            raise GitHubPagesFallbackError(
                f"cannot list {current}: {exc.strerror or type(exc).__name__}"
            ) from exc
        for entry in entries:
            rel = f"{prefix}{entry.name}"
            _require(not entry.is_symlink(), f"symlink in bundle: {rel!r}")
            if entry.is_dir(follow_symlinks=False):
                _require(
                    rel in {"runs", "data", "data/runs", "outage"},
                    f"unexpected directory in bundle: {rel!r}",
                )
                stack.append((Path(entry.path), rel + "/"))
                continue
            _require(
                entry.is_file(follow_symlinks=False),
                f"non-regular file in bundle: {rel!r}",
            )
            _require(
                len(result) < MAX_BUNDLE_FILES,
                f"at most {MAX_BUNDLE_FILES} files may be read",
            )
            try:
                fd = os.open(entry.path, os.O_RDONLY | nofollow)
                with os.fdopen(fd, "rb") as handle:
                    data = handle.read(MAX_SITE_BYTES + 1)
            except OSError as exc:
                raise GitHubPagesFallbackError(
                    f"cannot read {rel!r}: {exc.strerror or type(exc).__name__}"
                ) from exc
            total += len(data)
            _require(
                total <= MAX_SITE_BYTES,
                f"bundle exceeds {MAX_SITE_BYTES} bytes",
            )
            try:
                result[rel] = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise GitHubPagesFallbackError(
                    f"{rel!r} is not UTF-8"
                ) from exc
    return result


def verify_github_pages_fallback_dir(
    path: str | os.PathLike[str],
) -> FallbackBundleReport:
    """Read and verify an on-disk bundle (read-only)."""

    return verify_github_pages_fallback_bundle(
        read_github_pages_fallback_dir(path)
    )


def write_github_pages_fallback_bundle(
    files: Mapping[str, str],
    out_dir: str | os.PathLike[str],
) -> FallbackBundleReport:
    """Verify ``files`` and write them to a new local directory.

    The bundle is verified first (fail closed). ``out_dir`` must not exist or
    must be an empty real directory; nothing existing is replaced or followed.
    Files are staged in a fresh sibling directory and moved into place only
    after every file is written. No network or GitHub access, no upload.
    """

    report = verify_github_pages_fallback_bundle(files)
    encoded = _validate_file_map(files, max_files=MAX_BUNDLE_FILES)
    target = Path(os.fspath(out_dir))
    name = target.name
    _require(
        name not in {"", ".", ".."},
        "out directory needs a final path component (not '.', '..' or '/')",
    )
    parent = target.parent
    _require(parent.is_dir(), f"parent directory does not exist: {parent}")
    _require(not os.path.islink(target), f"out directory is a symlink: {target}")
    existed = os.path.lexists(target)
    if existed:
        _require(
            target.is_dir(), f"out path exists and is not a directory: {target}"
        )
        _require(
            not any(target.iterdir()),
            f"out directory is not empty (it is never replaced): {target}",
        )

    try:
        stage = _make_stage(parent, name, "tmp")
    except GitHubPagesWriteError as exc:
        raise GitHubPagesFallbackError(str(exc)) from exc
    try:
        for path, data in encoded.items():
            destination = stage.joinpath(*path.split("/"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            with open(destination, "xb") as handle:
                handle.write(data)
        if existed:
            os.rmdir(target)
        os.rename(stage, target)
    except OSError as exc:
        shutil.rmtree(stage, ignore_errors=True)
        if existed and not os.path.lexists(target):
            try:
                os.mkdir(target)
            except OSError:
                pass
        raise GitHubPagesFallbackError(
            f"cannot write fallback bundle to {target}: "
            f"{exc.strerror or type(exc).__name__}"
        ) from exc
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return report
