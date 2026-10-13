"""Parse a GitHub "IDKMesh WorkUnit request" issue body into untrusted intake.

C13-C/C13-D of issue #608. The Issue Form ``.github/ISSUE_TEMPLATE/06-idkmesh-
workunit.yml`` renders as ``### <label>`` sections. This module turns such a
body into the frozen ``schemas/github-workunit-intake-v0.1.schema.json`` object,
or reports a *fallback* so the caller keeps using the generic issue preview.

The parse result is planning input only. It never grants authority: the
``authority_ceiling`` is always all-false, and any malformed, duplicated,
unknown, oversized or hand-edited content fails closed to ``fallback`` rather
than being guessed at. Pure function: no network, no filesystem, no clock.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import PurePosixPath
from typing import Any

SCHEMA_VERSION = "0.1"
KIND = "idkmesh-github-workunit-intake"
MAX_BODY_CHARS = 65_536

STATUS_PARSED = "parsed"
STATUS_FALLBACK = "fallback"

# Form label -> intake property id. Kept in lockstep with
# config/github-workunit-intake-v0.1.json by a regression test.
LABEL_TO_FIELD: dict[str, str] = {
    "Objective": "objective",
    "Task class": "task_class",
    "Expected outputs": "expected_outputs",
    "Requested allowed paths": "requested_allowed_paths",
    "Forbidden or sensitive paths": "requested_forbidden_paths",
    "Dependencies or blockers": "dependencies",
    "Acceptance checks": "acceptance_checks",
    "Risk hint": "risk_hint",
    "Data sensitivity hint": "data_sensitivity_hint",
    "External processing hint": "external_processing_hint",
    "Human review or decision requirement": "human_review_hint",
    "Preferred connector": "preferred_connector_hint",
    "Safety acknowledgement": "safety_acknowledgement",
}

_REQUIRED = (
    "objective",
    "task_class",
    "expected_outputs",
    "requested_allowed_paths",
    "acceptance_checks",
    "risk_hint",
    "data_sensitivity_hint",
    "external_processing_hint",
    "human_review_hint",
    "safety_acknowledgement",
)

_ENUMS: dict[str, tuple[str, ...]] = {
    "task_class": (
        "coding",
        "testing",
        "review",
        "benchmarking",
        "documentation",
        "research",
        "integration",
        "governance",
        "other",
    ),
    "risk_hint": ("low", "medium", "high", "critical", "unspecified"),
    "data_sensitivity_hint": (
        "public",
        "internal",
        "confidential",
        "restricted",
        "unspecified",
    ),
    "external_processing_hint": ("forbidden", "allowed", "unspecified"),
    "human_review_hint": ("required", "preferred", "unspecified"),
}

_LIST_LIMITS: dict[str, tuple[int, int]] = {
    # field -> (max items, max item chars), from the intake schema
    "expected_outputs": (32, 500),
    "requested_allowed_paths": (64, 512),
    "requested_forbidden_paths": (64, 512),
    "acceptance_checks": (32, 1000),
}
_MAX_OBJECTIVE_CHARS = 12_000
_MAX_DEPENDENCIES = 32
_MAX_DEPENDENCY_CHARS = 512

_HEADING_RE = re.compile(r"^###[ \t]+(.+?)[ \t]*$")
_NO_RESPONSE = "_no response_"
_BULLET_RE = re.compile(r"^(?:[-*+]|\d+[.)])[ \t]+")
_CONNECTOR_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_DEPENDENCY_RE = re.compile(
    r"^(requires|blocked[ _]by|informs)[ \t]*:[ \t]*(.+)$", re.IGNORECASE
)
_ACK_RE = re.compile(r"^-[ \t]+\[([ xX])\][ \t]+(.+)$")
_ACK_TEXT_PREFIX = "I understand this issue is an untrusted proposal"
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_AUTHORITY_CEILING = {
    "policy_authority": False,
    "secret_authority": False,
    "command_authority": False,
    "network_authority": False,
    "filesystem_authority": False,
    "connector_selection_authority": False,
    "dispatch_authority": False,
    "verification_authority": False,
    "integration_authority": False,
}


@dataclass(frozen=True)
class IntakeParseResult:
    """Outcome of parsing one issue body.

    ``status`` is ``parsed`` (``intake`` holds a schema-shaped dict) or
    ``fallback`` (``intake`` is ``None``; ``reasons`` explains why). Neither
    outcome authorizes anything.
    """

    status: str
    intake: dict[str, Any] | None
    reasons: tuple[str, ...]

    @property
    def parsed(self) -> bool:
        return self.status == STATUS_PARSED


def _fallback(*reasons: str) -> IntakeParseResult:
    return IntakeParseResult(STATUS_FALLBACK, None, tuple(reasons))


def _split_sections(body: str) -> tuple[dict[str, str], list[str]]:
    """Return ``{field_id: raw text}`` and a list of structural problems."""
    sections: dict[str, list[str]] = {}
    problems: list[str] = []
    current: str | None = None
    for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        match = _HEADING_RE.match(line)
        if match is not None:
            label = match.group(1).strip()
            field_id = LABEL_TO_FIELD.get(label)
            if field_id is None:
                problems.append(f"unknown section heading: {label[:80]!r}")
                current = None
                continue
            if field_id in sections:
                problems.append(f"duplicated section: {label}")
                current = None
                continue
            sections[field_id] = []
            current = field_id
            continue
        if current is not None:
            sections[current].append(line)
        elif line.strip():
            problems.append("content outside any known section")
    flat = {key: "\n".join(lines).strip() for key, lines in sections.items()}
    return flat, problems


def _is_blank(text: str) -> bool:
    return not text or text.strip().lower() == _NO_RESPONSE


def _lines(text: str, *, deduplicate: bool = True) -> list[str]:
    items: list[str] = []
    for raw in text.split("\n"):
        line = _BULLET_RE.sub("", raw.strip(), count=1).strip()
        if line:
            items.append(line)
    return list(dict.fromkeys(items)) if deduplicate else items


def _safe_path(value: str) -> str | None:
    if (
        value in {".", "./"}
        or value.startswith("./")
        or "://" in value
        or "\\" in value
        or value.startswith(("/", "~"))
        or re.match(r"^[A-Za-z]:", value)
        or ".." in PurePosixPath(value).parts
    ):
        return None
    return value


def _parse_dependencies(text: str, problems: list[str]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    raw_lines = _lines(text, deduplicate=False)
    if len(raw_lines) > _MAX_DEPENDENCIES:
        problems.append("dependencies: too many entries")
    for line in raw_lines:
        match = _DEPENDENCY_RE.match(line)
        if match is None:
            # Least binding relation when no keyword is given.
            relation, reference = "informs", line
        else:
            relation = match.group(1).lower().replace(" ", "_")
            reference = match.group(2).strip()
        if not reference or len(reference) > _MAX_DEPENDENCY_CHARS:
            problems.append("dependencies: empty or oversized reference")
            continue
        key = (reference, relation)
        if key not in seen:
            seen.add(key)
            result.append({"reference": reference, "relation": relation})
    return result


def parse_workunit_intake(body: object) -> IntakeParseResult:
    """Parse an Issue Form body; fail closed to ``fallback`` on any doubt."""
    if not isinstance(body, str):
        return _fallback("issue body is not text")
    if len(body) > MAX_BODY_CHARS:
        return _fallback("issue body exceeds the intake size limit")
    if _CONTROL_RE.search(body):
        return _fallback("issue body contains control characters")

    sections, problems = _split_sections(body)
    for field_id in _REQUIRED:
        if field_id not in sections or _is_blank(sections[field_id]):
            problems.append(f"missing required field: {field_id}")

    intake: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "kind": KIND}

    objective = sections.get("objective", "")
    if len(objective) > _MAX_OBJECTIVE_CHARS:
        problems.append("objective exceeds the intake size limit")
    intake["objective"] = objective

    for field_id, allowed in _ENUMS.items():
        value = sections.get(field_id, "")
        if not _is_blank(value) and value not in allowed:
            problems.append(f"{field_id}: value is not in the closed vocabulary")
        intake[field_id] = value

    for field_id, (max_items, max_chars) in _LIST_LIMITS.items():
        raw_items = [] if _is_blank(sections.get(field_id, "")) else _lines(
            sections[field_id], deduplicate=False
        )
        items = list(dict.fromkeys(raw_items))
        if len(raw_items) > max_items or any(len(i) > max_chars for i in raw_items):
            problems.append(f"{field_id}: too many or oversized entries")
        if field_id in ("requested_allowed_paths", "requested_forbidden_paths"):
            if any(_safe_path(item) is None for item in items):
                problems.append(f"{field_id}: contains an unsafe path")
        intake[field_id] = items

    dependencies_text = sections.get("dependencies", "")
    intake["dependencies"] = (
        [] if _is_blank(dependencies_text)
        else _parse_dependencies(dependencies_text, problems)
    )

    connector_text = sections.get("preferred_connector_hint", "")
    if _is_blank(connector_text):
        intake["preferred_connector_hint"] = None
    elif _CONNECTOR_RE.fullmatch(connector_text) is None:
        problems.append("preferred_connector_hint: not a plain connector id")
        intake["preferred_connector_hint"] = None
    else:
        intake["preferred_connector_hint"] = connector_text

    ack_ok = False
    for line in sections.get("safety_acknowledgement", "").split("\n"):
        match = _ACK_RE.match(line.strip())
        if match and match.group(2).startswith(_ACK_TEXT_PREFIX):
            ack_ok = match.group(1) in "xX"
    if not ack_ok:
        problems.append("safety acknowledgement is not checked")

    intake["authority_ceiling"] = dict(_AUTHORITY_CEILING)

    if problems:
        return _fallback(*dict.fromkeys(problems))
    return IntakeParseResult(STATUS_PARSED, intake, ())
