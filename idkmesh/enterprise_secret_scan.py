"""Deterministic raw-secret scanner for E5 (#672).

``enterprise_data_policy`` decides *who may obtain* a secret. This module is
the other half of "raw secrets never enter WorkUnits, results or audit": a pure
check that a JSON-shaped document does not already contain one.

It detects two things:

* **credential-shaped values** -- well-known token formats (GitHub, AWS, Slack,
  Google, ``sk-`` style API keys, JWTs, PEM private-key headers, ``Bearer``
  credentials, and ``scheme://user:password@host`` URLs);
* **credential-named keys with literal values** -- ``password``, ``api_key``,
  ``authorization`` and the like whose value is a literal string rather than a
  secret *reference* (``env:NAME`` and placeholders are accepted).

Properties that make the result safe to log and to record as audit evidence:

* a finding carries a rule id and a sanitized location, **never the matched
  text, a prefix of it, its length, or a hash**;
* a mapping key that is not a short plain identifier, or that itself looks like a
  secret, is replaced by ``<key:N>`` in the location, so a secret placed in a key
  cannot leak through the path;
* traversal order, and therefore the report, is deterministic;
* the scan is **fail-closed**: a node, depth or string-size limit, or a value
  that is not JSON-shaped, makes the report ``complete=False`` and therefore not
  ``clean``. "I could not look" is never reported as "nothing found";
* every pattern uses bounded quantifiers. Traversal is budgeted, while sorted
  mapping keys make the overall complexity O(N log N) in the worst case.

A clean report is evidence about the scanned text only. It is not a proof that a
document holds no secret: unknown formats, split or encoded values, and low
entropy passwords are not detected. The scanner performs no I/O, reads no
environment variable, and grants no authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

SCAN_VERSION = "0.1"
SCAN_KIND = "idkmesh-enterprise-secret-scan"

MAX_DEPTH = 32
MAX_NODES = 100_000
MAX_STRING_CHARS = 262_144

# (rule id, pattern). Every quantifier is bounded; none can backtrack
# super-linearly. Ordered, so a value reports its first matching rule only.
_VALUE_RULES: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("private_key_block", re.compile(r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY-----")),
    (
        "github_token",
        re.compile(
            r"(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9]{36,255}"
            r"|github_pat_[A-Za-z0-9_]{22,255})(?![A-Za-z0-9_])"
        ),
    ),
    (
        "aws_access_key_id",
        re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Za-z0-9])"),
    ),
    (
        "slack_token",
        re.compile(r"(?<![A-Za-z0-9])xox[abprs]-[A-Za-z0-9-]{10,200}(?![A-Za-z0-9-])"),
    ),
    (
        "google_api_key",
        re.compile(r"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{35}(?![A-Za-z0-9_-])"),
    ),
    (
        "api_key_sk",
        re.compile(r"(?<![A-Za-z0-9_-])sk-(?:ant-|proj-)?[A-Za-z0-9_-]{32,256}"),
    ),
    (
        "jwt",
        re.compile(
            r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,2048}\."
            r"eyJ[A-Za-z0-9_-]{8,2048}\.[A-Za-z0-9_-]{8,2048}"
        ),
    ),
    (
        "bearer_credential",
        # The token must hold a digit, an uppercase letter or a symbol: an
        # all-lowercase hyphenated phrase ("bearer token-based-authentication")
        # is prose, not a credential.
        re.compile(
            r"(?<![A-Za-z0-9])(?i:bearer)[ \t]{1,8}"
            r"(?=[a-z-]{0,2048}[0-9A-Z._~+/])[A-Za-z0-9._~+/-]{20,2048}"
        ),
    ),
    (
        "url_userinfo",
        re.compile(
            r"[A-Za-z][A-Za-z0-9+.-]{0,31}://[^\s/@:]{1,256}:(?P<password>[^\s/@]{1,256})@"
        ),
    ),
)
# A URL password that is obviously documentation (``user:password@host``,
# ``<password>``, ``${PASSWORD}``, ``****``) is not a credential. Measured on this
# repository's own 1,117 issues and PRs, this was the only false positive.
_PLACEHOLDER_PASSWORD = re.compile(
    r"(?i)(?:pass(?:w(?:or)?d)?|pwd|secret|token|changeme|x{3,}|\*{3,}"
    r"|<[^>]{1,64}>|\$\{[^}]{1,64}\}|\{[^}]{1,64}\}|%s)\Z"
)


def _userinfo_is_credential(match: "re.Match[str]") -> bool:
    return _PLACEHOLDER_PASSWORD.fullmatch(match.group("password")) is None


# Rules whose raw pattern match still needs a second look.
_MATCH_FILTERS = {"url_userinfo": _userinfo_is_credential}

RULE_IDS = tuple(rule for rule, _ in _VALUE_RULES) + ("sensitive_key_literal",)

# Exact (not substring) key names, so ``max_tokens`` and ``secret_ref`` are not
# credential-named keys. A superset of connector_secrets._SENSITIVE_KEYS, which
# the tests assert.
SENSITIVE_KEYS = frozenset(
    {
        "access_key",
        "access_token",
        "api_key",
        "apikey",
        "auth_token",
        "authorization",
        "bearer_token",
        "client_secret",
        "credentials",
        "passwd",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "secret_key",
        "token",
    }
)

# A value that names a secret rather than holding one.
_REFERENCE = re.compile(
    r"(?:(?:env|secret|ref|vault|gh-secret):[A-Za-z0-9_./-]{1,200}"
    r"|\$\{[A-Za-z_][A-Za-z0-9_]{0,127}\}"
    r"|<[A-Za-z0-9_ -]{1,64}>"
    r"|\*{3,64})\Z"
)
# "/" and "~" are allowed because the location is a JSON Pointer that escapes them.
_SAFE_KEY = re.compile(r"[A-Za-z0-9_.:/~-]{1,64}\Z")
_MIN_LITERAL_LENGTH = 8

@dataclass(frozen=True)
class SecretFinding:
    """One detection: a rule and a sanitized location, never the value."""

    rule: str
    location: str

    def to_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "location": self.location}


@dataclass(frozen=True)
class SecretScanReport:
    """Outcome of one scan; carries identifiers and counts only."""

    findings: tuple[SecretFinding, ...]
    complete: bool
    incomplete_reasons: tuple[str, ...]
    nodes_scanned: int

    @property
    def clean(self) -> bool:
        """True only when the whole document was scanned and nothing matched."""

        return self.complete and not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": SCAN_KIND,
            "scan_version": SCAN_VERSION,
            "clean": self.clean,
            "complete": self.complete,
            "incomplete_reasons": list(self.incomplete_reasons),
            "nodes_scanned": self.nodes_scanned,
            "findings": [finding.to_dict() for finding in self.findings],
            "authority": {
                "grants_runtime_authority": False,
                "reads_environment": False,
                "performs_io": False,
            },
        }


class SecretLeakError(ValueError):
    """A document failed the secret check; the message carries no secret text."""

    def __init__(self, report: SecretScanReport, context: str) -> None:
        self.report = report
        self.context = context
        if report.findings:
            code = "secret_detected"
            detail = ", ".join(
                f"{finding.rule} at {finding.location}"
                for finding in report.findings[:5]
            )
            more = len(report.findings) - 5
            if more > 0:
                detail += f" (+{more} more)"
        else:
            code = "scan_incomplete"
            detail = ", ".join(report.incomplete_reasons)
        super().__init__(f"{code}: {context}: {detail}")


def _value_rule(text: str) -> str | None:
    for rule, pattern in _VALUE_RULES:
        accept = _MATCH_FILTERS.get(rule)
        if accept is None:
            if pattern.search(text):
                return rule
        elif any(accept(match) for match in pattern.finditer(text)):
            return rule
    return None


def _escape(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _key_segment(key: str, index: int) -> str:
    """A log-safe path segment: the key when plain, else a positional marker."""

    if _SAFE_KEY.fullmatch(key) and _value_rule(key) is None:
        return _escape(key)
    return f"<key:{index}>"


def _is_literal_secret(value: str) -> bool:
    stripped = value.strip()
    return len(stripped) >= _MIN_LITERAL_LENGTH and not _REFERENCE.fullmatch(stripped)


def scan_for_secrets(
    document: Any,
    *,
    max_depth: int = MAX_DEPTH,
    max_nodes: int = MAX_NODES,
    max_string_chars: int = MAX_STRING_CHARS,
) -> SecretScanReport:
    """Scan a JSON-shaped document for raw secrets; never raises on content.

    Limit configuration errors raise ValueError; malformed document contents
    instead return a non-clean, incomplete report.
    """
    if any(type(value) is not int or value < 1 for value in (
        max_depth, max_nodes, max_string_chars
    )):
        raise ValueError("scan limits must be positive integers")

    findings: list[SecretFinding] = []
    reasons: set[str] = set()
    nodes = 0
    # Iterative walk: no recursion limit to hit, and the explicit stack keeps the
    # order deterministic (children are pushed in reverse so they pop in order).
    stack: list[tuple[Any, str, int, str | None]] = [(document, "", 0, None)]

    while stack:
        node, location, depth, key_name = stack.pop()
        nodes += 1
        if nodes > max_nodes:
            reasons.add("node_limit_exceeded")
            break
        shown = location or "/"

        if type(node) is str:
            if len(node) > max_string_chars:
                reasons.add("string_too_large")
                continue
            rule = _value_rule(node)
            if rule is not None:
                findings.append(SecretFinding(rule, shown))
            elif (
                key_name is not None
                and key_name.lower().replace("-", "_") in SENSITIVE_KEYS
                and _is_literal_secret(node)
            ):
                findings.append(SecretFinding("sensitive_key_literal", shown))
            continue

        if type(node) in (int, bool, type(None)):
            continue
        if type(node) is float:
            if not math.isfinite(node):
                reasons.add("unsupported_value")
            continue

        if depth >= max_depth:
            reasons.add("depth_limit_exceeded")
            continue

        if type(node) is dict:
            # Check fan-out before sorting or building a child queue: a hostile
            # container must not allocate beyond the remaining node budget.
            if len(node) > max_nodes - nodes - len(stack):
                reasons.add("node_limit_exceeded")
                continue
            if any(type(key) is not str for key in node):
                reasons.add("unsupported_value")
                continue
            ordered = sorted(node)
            children = []
            for index, key in enumerate(ordered):
                if len(key) > max_string_chars:
                    reasons.add("string_too_large")
                    continue
                segment = _key_segment(key, index)
                key_rule = _value_rule(key)
                if key_rule is not None:
                    findings.append(SecretFinding(key_rule, f"{location}/{segment}"))
                children.append((node[key], f"{location}/{segment}", depth + 1, key))
            stack.extend(reversed(children))
            continue

        if type(node) in (list, tuple):
            if len(node) > max_nodes - nodes - len(stack):
                reasons.add("node_limit_exceeded")
                continue
            stack.extend(
                (item, f"{location}/{index}", depth + 1, None)
                for index, item in reversed(list(enumerate(node)))
            )
            continue

        reasons.add("unsupported_value")

    ordered_findings = tuple(
        sorted(set(findings), key=lambda item: (item.location, item.rule))
    )
    return SecretScanReport(
        findings=ordered_findings,
        complete=not reasons,
        incomplete_reasons=tuple(sorted(reasons)),
        nodes_scanned=min(nodes, max_nodes),
    )


def assert_no_secrets(document: Any, *, context: str, **limits: int) -> SecretScanReport:
    """Return the clean report, or raise :class:`SecretLeakError`.

    ``context`` names what was scanned (for example ``"work_unit"``); it must
    not contain document content.
    """

    report = scan_for_secrets(document, **limits)
    if not report.clean:
        raise SecretLeakError(report, context)
    return report

