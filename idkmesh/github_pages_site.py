"""Read-only static GitHub Pages projection for C14-E (#609).

This module turns already public-safe C14-D projections
(``idkmesh.github_public_evidence``) into a deterministic in-memory file map
for a static Pages site: a health/active-work/verification-debt index, one page
per run, and the canonical public JSON per run. It performs no file, network,
GitHub, verification, decision, or repository mutation and carries no dispatch,
verification, human-decision, canonical-state-write, Git push, integration, or
merge authority.

The generated pages are a publication surface only. They contain no scripts,
forms, external assets, or mutation controls, and their absence or outage must
never affect coordination.

Inputs are re-validated here (the whitelist shape via the C14-D renderer, then
every value that reaches HTML) so a hand-built mapping cannot smuggle markup,
links, or unknown vocabulary into the published site.
"""

from __future__ import annotations

import hashlib
import html
import re
from typing import Any, Iterable, Mapping

from idkmesh.github_public_evidence import (
    GitHubPublicEvidenceError,
    render_github_public_evidence_json,
)


_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REVISION_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_PR_URL_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)\Z"
)

_RUN_STATES = (
    "proposed",
    "previewed",
    "admission_blocked",
    "admitted",
    "dispatched",
    "attempt_failed",
    "candidate_observed",
    "normalized",
    "verification_requested",
    "verification_error",
    "evidence_ready",
    "awaiting_human_decision",
    "decided",
    "cancelled",
)
_TERMINAL_RUN_STATES = frozenset({"admission_blocked", "decided", "cancelled"})
_ATTEMPT_STATES = frozenset(
    {
        "created",
        "dispatched",
        "worker_error",
        "candidate_observed",
        "normalization_error",
        "normalized",
        "verification_requested",
        "verification_error",
        "verified",
        "cancelled",
    }
)
# A candidate exists (or may exist) but no accepted verification result is
# retained for it yet.
_UNVERIFIED_ATTEMPT_STATES = frozenset(
    {
        "candidate_observed",
        "normalized",
        "verification_requested",
        "verification_error",
    }
)
_DECISION_STATUSES = frozenset({"not_recorded", "pending", "recorded"})
_EVIDENCE_STATES = frozenset(
    {
        None,
        "supported",
        "rejected",
        "inconclusive",
        "worker_error",
        "result_manifest_error",
        "verification_error",
    }
)
_RECOMMENDATIONS = frozenset(
    {
        None,
        "accept_candidate",
        "reject_candidate",
        "escalate",
        "insufficient_evidence",
    }
)

MAX_RUNS = 500
MAX_SITE_BYTES = 8 * 1024 * 1024

_DISCLAIMER = (
    "Read-only publication of digest-bound public metadata. This page grants "
    "no dispatch, verification, human-decision, merge, or write authority, "
    "and publication of a digest or verifier recommendation does not accept a "
    "candidate or prove functional correctness."
)

_STYLE = (
    "body{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;"
    "padding:0 1rem;line-height:1.5}"
    "table{border-collapse:collapse;width:100%;margin:1rem 0}"
    "th,td{border:1px solid #888;padding:.25rem .5rem;text-align:left;"
    "vertical-align:top}"
    "code{word-break:break-all}"
)


class GitHubPagesSiteError(ValueError):
    """Fail-closed Pages generation error."""


def _esc(value: Any) -> str:
    """HTML-escape and neutralize Liquid delimiters for Jekyll-built Pages."""

    text = html.escape(str(value), quote=True)
    return text.replace("{", "&#123;").replace("}", "&#125;")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GitHubPagesSiteError(message)


def _slug(run_id: str) -> str:
    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:16]


def _digest(value: Any, label: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    _require(
        isinstance(value, str) and _DIGEST_RE.fullmatch(value) is not None,
        f"{label} must be a sha256 digest",
    )
    return value


def _validate_projection(
    projection: Mapping[str, Any], repository: str
) -> None:
    try:
        render_github_public_evidence_json(projection)
    except GitHubPublicEvidenceError as exc:
        raise GitHubPagesSiteError(
            f"projection is not public-safe evidence: {exc}"
        ) from exc
    _require(
        projection["repository"].casefold() == repository.casefold(),
        "projection repository does not match the Pages repository",
    )
    run = projection["run"]
    _require(
        isinstance(run["run_id"], str) and run["run_id"] != "",
        "run_id must be a non-empty string",
    )
    _require(run["state"] in _RUN_STATES, "unknown run state")
    _require(
        isinstance(run["source_revision"], str)
        and _REVISION_RE.fullmatch(run["source_revision"]) is not None,
        "source_revision must be an exact Git revision",
    )
    _digest(run["work_unit_digest"], "work_unit_digest")
    _digest(run["evidence_report_digest"], "evidence_report_digest", optional=True)
    _digest(
        run["human_decision_record_digest"],
        "human_decision_record_digest",
        optional=True,
    )
    _require(
        projection["human_decision_status"] in _DECISION_STATUSES,
        "unknown human decision status",
    )
    for attempt in projection["attempts"]:
        _require(attempt["state"] in _ATTEMPT_STATES, "unknown attempt state")
        _require(
            attempt["evidence_state"] in _EVIDENCE_STATES,
            "unknown attempt evidence state",
        )
        _require(
            attempt["verifier_recommendation"] in _RECOMMENDATIONS,
            "unknown verifier recommendation",
        )
        for key in (
            "candidate_reference_digest",
            "result_manifest_digest",
            "verification_semantic_digest",
        ):
            _digest(attempt[key], key, optional=True)
        candidate = attempt["candidate"]
        if candidate is None:
            continue
        if candidate["type"] == "github_pull_request":
            match = _PR_URL_RE.fullmatch(str(candidate["url"]))
            _require(match is not None, "candidate PR URL is not canonical")
            _require(
                match.group(1).casefold() == repository.casefold()
                and candidate["repository"].casefold() == repository.casefold()
                and match.group(2) == str(candidate["number"]),
                "candidate PR URL must name the Pages repository and number",
            )
            _require(
                _REVISION_RE.fullmatch(str(candidate["head_sha"])) is not None,
                "candidate head_sha must be an exact Git revision",
            )
        else:
            _require(
                candidate["type"] == "artifact_bundle",
                "unknown candidate type",
            )
            _digest(candidate["digest"], "candidate digest")


def _unverified_attempts(projection: Mapping[str, Any]) -> list[str]:
    return [
        attempt["attempt_id"]
        for attempt in projection["attempts"]
        if attempt["state"] in _UNVERIFIED_ATTEMPT_STATES
    ]


def _is_active(projection: Mapping[str, Any]) -> bool:
    return projection["run"]["state"] not in _TERMINAL_RUN_STATES


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex">\n'
        f"<title>{_esc(title)}</title>\n<style>{_STYLE}</style>\n</head>\n"
        f"<body>\n{body}\n"
        f'<p><small>{_esc(_DISCLAIMER)}</small></p>\n</body>\n</html>\n'
    )


def _table(headers: Iterable[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table>\n<tr>{head}</tr>\n{body}\n</table>"


def _run_link(projection: Mapping[str, Any]) -> str:
    run_id = projection["run"]["run_id"]
    return f'<a href="runs/{_slug(run_id)}.html">{_esc(run_id)}</a>'


def _render_index(
    repository: str, projections: list[Mapping[str, Any]]
) -> str:
    counts = {state: 0 for state in _RUN_STATES}
    for projection in projections:
        counts[projection["run"]["state"]] += 1
    active = [p for p in projections if _is_active(p)]
    debt = [
        (p, ids)
        for p in active
        if (ids := _unverified_attempts(p))
    ]
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
            ["Total runs", _esc(len(projections))],
            ["Active runs", _esc(len(active))],
            ["Verification debt", _esc(len(debt))],
            ["Awaiting human decision", _esc(len(pending))],
            ["Control failure present", _esc(len(control_failures))],
            ["Verification disagreement", _esc(len(disagreements))],
        ],
    )
    by_state = _table(
        ["Run state", "Runs"],
        [[_esc(s), _esc(counts[s])] for s in _RUN_STATES if counts[s]],
    ) if projections else "<p>No public runs are published.</p>"
    active_rows = [
        [
            _run_link(p),
            _esc(p["run"]["state"]),
            _esc(p["human_decision_status"]),
            _esc(len(p["attempts"])),
        ]
        for p in active
    ]
    debt_rows = [
        [_run_link(p), _esc(", ".join(ids)), _esc(p["run"]["state"])]
        for p, ids in debt
    ]
    all_rows = [
        [
            _run_link(p),
            _esc(p["run"]["state"]),
            f'<code>{_esc(p["run"]["work_unit_digest"])}</code>',
            f'<code>{_esc(p["run"]["source_revision"])}</code>',
        ]
        for p in projections
    ]
    body = (
        f"<h1>IDKMesh public run evidence: {_esc(repository)}</h1>\n"
        "<h2>Project health</h2>\n" + health + "\n" + by_state + "\n"
        "<h2>Active work</h2>\n"
        + (
            _table(
                ["Run", "State", "Human decision", "Attempts"], active_rows
            )
            if active_rows
            else "<p>No active runs.</p>"
        )
        + "\n<h2>Verification debt</h2>\n"
        "<p>Active runs with a candidate that has no retained verification "
        "result yet.</p>\n"
        + (
            _table(["Run", "Unverified attempts", "State"], debt_rows)
            if debt_rows
            else "<p>No verification debt.</p>"
        )
        + "\n<h2>All runs</h2>\n"
        + (
            _table(
                ["Run", "State", "WorkUnit digest", "Source revision"],
                all_rows,
            )
            if all_rows
            else "<p>No public runs are published.</p>"
        )
    )
    return _page(f"IDKMesh public run evidence: {repository}", body)


def _candidate_cell(candidate: Mapping[str, Any] | None) -> str:
    if candidate is None:
        return "none"
    if candidate["type"] == "github_pull_request":
        return (
            f'<a href="{_esc(candidate["url"])}" rel="noopener">'
            f'PR #{_esc(candidate["number"])}</a> at '
            f'<code>{_esc(candidate["head_sha"])}</code>'
        )
    return f'artifact bundle <code>{_esc(candidate["digest"])}</code>'


def _opt(value: Any) -> str:
    return "none" if value is None else f"<code>{_esc(value)}</code>"


def _render_run(repository: str, projection: Mapping[str, Any]) -> str:
    run = projection["run"]
    summary = projection["evidence_summary"]
    facts = _table(
        ["Field", "Value"],
        [
            ["Run", f'<code>{_esc(run["run_id"])}</code>'],
            ["State", _esc(run["state"])],
            [
                "WorkUnit",
                f'<code>{_esc(run["work_unit_id"])}</code> version '
                f'{_esc(run["work_unit_version"])}',
            ],
            ["WorkUnit digest", _opt(run["work_unit_digest"])],
            ["Source revision", _opt(run["source_revision"])],
            ["Evidence report digest", _opt(run["evidence_report_digest"])],
            [
                "Human decision",
                f'{_esc(projection["human_decision_status"])} '
                f'({_opt(run["human_decision_record_digest"])})',
            ],
        ],
    )
    attempt_rows = [
        [
            _esc(a["order"]),
            f'<code>{_esc(a["attempt_id"])}</code>',
            _esc(a["connector_id"]),
            _esc(a["state"]),
            _candidate_cell(a["candidate"]),
            _opt(a["result_manifest_digest"]),
            _opt(a["verification_semantic_digest"]),
            _esc(a["evidence_state"] or "none"),
            _esc(a["verifier_recommendation"] or "none"),
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
        else "<p>No attempts recorded.</p>"
    )
    if summary is None:
        summary_html = "<p>No retained evidence report.</p>"
    else:
        summary_html = _table(
            ["Measure", "Value"],
            [[_esc(k), _esc(v)] for k, v in sorted(summary.items())],
        )
    body = (
        f"<h1>Run {_esc(run['run_id'])}</h1>\n"
        f'<p><a href="../index.html">All runs for {_esc(repository)}</a> '
        f'| <a href="../data/runs/{_slug(run["run_id"])}.json">'
        "public JSON projection</a></p>\n"
        "<h2>Provenance</h2>\n" + facts + "\n<h2>Attempts</h2>\n" + attempts
        + "\n<h2>Evidence summary</h2>\n" + summary_html
    )
    return _page(f"Run {run['run_id']}", body)


def render_github_pages_site(
    projections: Iterable[Mapping[str, Any]],
    *,
    repository: str,
) -> dict[str, str]:
    """Return a deterministic ``path -> text`` file map for a static site.

    ``projections`` must be C14-D public-safe projections for ``repository``.
    The result contains ``index.html``, ``runs/<slug>.html``,
    ``data/runs/<slug>.json`` and an empty ``.nojekyll`` marker. Nothing is
    written; the caller decides whether and where to publish.
    """

    _require(
        isinstance(repository, str)
        and _REPOSITORY_RE.fullmatch(repository) is not None,
        "repository must be owner/name",
    )
    items = list(projections)
    _require(len(items) <= MAX_RUNS, f"at most {MAX_RUNS} runs may be published")
    seen: set[str] = set()
    slugs: set[str] = set()
    for projection in items:
        _require(
            isinstance(projection, Mapping),
            "each projection must be a mapping",
        )
        _validate_projection(projection, repository)
        run_id = projection["run"]["run_id"]
        _require(run_id not in seen, "duplicate run_id in Pages input")
        seen.add(run_id)
        slug = _slug(run_id)
        _require(slug not in slugs, "run slug collision in Pages input")
        slugs.add(slug)

    items.sort(key=lambda p: p["run"]["run_id"])
    files: dict[str, str] = {".nojekyll": "", "index.html": _render_index(repository, items)}
    for projection in items:
        slug = _slug(projection["run"]["run_id"])
        files[f"runs/{slug}.html"] = _render_run(repository, projection)
        files[f"data/runs/{slug}.json"] = render_github_public_evidence_json(
            projection
        )
    total = sum(len(text.encode("utf-8")) for text in files.values())
    _require(
        total <= MAX_SITE_BYTES,
        f"generated site exceeds {MAX_SITE_BYTES} UTF-8 bytes",
    )
    return dict(sorted(files.items()))
