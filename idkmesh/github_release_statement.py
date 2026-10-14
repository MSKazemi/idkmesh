"""Unsigned in-toto Statement for a release record, C14-G (#609).

This module turns a validated C14-F release metadata record into an
`in-toto Statement v1 <https://in-toto.io/Statement/v1>`_ whose *subjects* are
the release's distributable artifacts (name plus SHA-256) and whose *predicate*
embeds the whole release record, so the artifact digests and the public-safe
run-evidence digests travel in one document. The statement is a payload that a
CI job running with a GitHub workflow identity could pass to an attestation
step; this module only builds and checks that payload.

It is deliberately **not** an attestation:

* nothing is signed, no key or token is read, and no file, network, or GitHub
  call is made; ``predicate.signature.status`` is always ``unsigned``;
* signing and registering an attestation needs the CI workflow identity and
  the repository plan's attestation support, neither of which exists offline;
* subjects are the caller-supplied digests from the release record and are
  *not* checked against any build or file (``subjects_verified_against_build``
  is fixed ``false``);
* it makes no SLSA build-provenance claim and no functional-correctness claim;
* it carries no timestamps and grants no dispatch, verification,
  human-decision, push, merge, tag, release, or attestation authority.

The statement is re-validated before rendering, and the embedded release
record is re-validated through the C14-F validator, so a hand-built or mutated
statement cannot be rendered.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from idkmesh.github_release_provenance import (
    GitHubReleaseProvenanceError,
    validate_github_release_provenance,
)


STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = (
    "https://github.com/MSKazemi/idkmesh/blob/main/docs/specifications/"
    "GITHUB_RELEASE_STATEMENT_V0_1.md"
)
MAX_STATEMENT_JSON_BYTES = 2 * 1024 * 1024

_PREDICATE_SCHEMA_VERSION = "0.1"
_STATEMENT_KEYS = frozenset({"_type", "subject", "predicateType", "predicate"})
_SUBJECT_KEYS = frozenset({"name", "digest"})
_PREDICATE_KEYS = frozenset({"schema_version", "signature", "claims", "record"})
_SIGNATURE = {
    "status": "unsigned",
    "signing_requires": "CI workflow identity",
}
_CLAIMS = {
    "signed": False,
    "attestation_registered": False,
    "slsa_build_provenance": False,
    "subjects_verified_against_build": False,
    "functional_correctness": False,
}


class GitHubReleaseStatementError(ValueError):
    """Fail-closed release-statement error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GitHubReleaseStatementError(message)


def _exact(value: Any, keys: frozenset[str], path: str) -> Mapping[str, Any]:
    _require(
        isinstance(value, Mapping) and set(value) == keys,
        f"release statement {path} does not match the v0.1 shape",
    )
    return value


def _fixed(value: Any, expected: Mapping[str, Any], path: str) -> None:
    _exact(value, frozenset(expected), path)
    _require(
        all(
            type(value[key]) is type(expected[key]) and value[key] == expected[key]
            for key in expected
        ),
        f"release statement {path} must be the fixed v0.1 value",
    )


def _subjects(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": artifact["name"],
            # in-toto digests are bare lowercase hex keyed by algorithm.
            "digest": {"sha256": artifact["digest"].removeprefix("sha256:")},
        }
        for artifact in record["artifacts"]
    ]


def build_github_release_statement(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return the unsigned in-toto Statement for a release record.

    ``record`` must be a valid C14-F record with at least one artifact: a
    statement without subjects attests nothing, so it is refused.
    """

    try:
        validate_github_release_provenance(record)
    except GitHubReleaseProvenanceError as exc:
        raise GitHubReleaseStatementError(str(exc)) from exc
    _require(
        len(record["artifacts"]) > 0,
        "a release statement needs at least one artifact subject",
    )
    statement: dict[str, Any] = {
        "_type": STATEMENT_TYPE,
        "subject": _subjects(record),
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "schema_version": _PREDICATE_SCHEMA_VERSION,
            "signature": dict(_SIGNATURE),
            "claims": dict(_CLAIMS),
            "record": json.loads(json.dumps(record)),
        },
    }
    validate_github_release_statement(statement)
    return statement


def validate_github_release_statement(statement: Mapping[str, Any]) -> None:
    """Fail closed unless ``statement`` is exactly a v0.1 release statement."""

    _require(isinstance(statement, Mapping), "release statement must be a mapping")
    _require(
        statement.get("_type") == STATEMENT_TYPE
        and statement.get("predicateType") == PREDICATE_TYPE,
        "not a GitHub release statement v0.1",
    )
    _exact(statement, _STATEMENT_KEYS, "root")
    predicate = _exact(statement["predicate"], _PREDICATE_KEYS, "predicate")
    _require(
        predicate["schema_version"] == _PREDICATE_SCHEMA_VERSION,
        "unsupported release statement predicate version",
    )
    _fixed(predicate["signature"], _SIGNATURE, "predicate.signature")
    _fixed(predicate["claims"], _CLAIMS, "predicate.claims")
    try:
        validate_github_release_provenance(predicate["record"])
    except GitHubReleaseProvenanceError as exc:
        raise GitHubReleaseStatementError(str(exc)) from exc
    record = predicate["record"]
    _require(len(record["artifacts"]) > 0, "release statement has no subjects")
    subjects = statement["subject"]
    _require(isinstance(subjects, list), "release statement subject must be a list")
    for index, subject in enumerate(subjects):
        _exact(subject, _SUBJECT_KEYS, f"subject[{index}]")
        _exact(subject["digest"], frozenset({"sha256"}), f"subject[{index}].digest")
    # Subjects must be exactly the record's artifacts; this also pins names,
    # digests, ordering, and uniqueness to the already-validated record.
    _require(
        subjects == _subjects(record),
        "release statement subjects do not match the embedded release record",
    )


def render_github_release_statement_json(statement: Mapping[str, Any]) -> str:
    """Render the validated statement as deterministic, bounded JSON."""

    validate_github_release_statement(statement)
    rendered = (
        json.dumps(
            statement,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    _require(
        len(rendered.encode("utf-8")) <= MAX_STATEMENT_JSON_BYTES,
        f"release statement exceeds {MAX_STATEMENT_JSON_BYTES} UTF-8 bytes",
    )
    return rendered
