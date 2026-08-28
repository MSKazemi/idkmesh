"""Protocol-neutral identity evidence binding for IDKMesh worker results.

Identity evidence is deliberately optional and namespaced. It may describe an
A2A Agent Card, an MCP workload identity, a direct local worker, or another
adapter without changing ResultManifest v0.1 core fields.

Authentication/identity evidence never grants authorization, verification, or
integration authority.
"""

from __future__ import annotations

import copy
import re
from typing import Any

IDENTITY_BINDING_EXTENSION = "org.idkmesh.identity-binding"
IDENTITY_BINDING_SCHEMA_VERSION = "0.1"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class IdentityBindingError(ValueError):
    """Raised when identity evidence is malformed or would be overwritten."""


def build_identity_binding(
    *,
    protocol: str,
    subject: str,
    verified: bool,
    evidence_digest: str | None = None,
    evidence_locator: str | None = None,
    verification_method: str | None = None,
) -> dict[str, Any]:
    """Build a small vendor-neutral identity evidence object.

    `verified=True` means only that the adapter/verifier checked the referenced
    identity evidence using the declared method. It does not mean the worker is
    authorized, correct, independent, or approved for integration.
    """

    if not isinstance(protocol, str) or not protocol.strip():
        raise IdentityBindingError("protocol is required")
    if not isinstance(subject, str) or not subject.strip():
        raise IdentityBindingError("subject is required")
    if not isinstance(verified, bool):
        raise IdentityBindingError("verified must be boolean")
    if evidence_digest is not None and not _SHA256_RE.fullmatch(evidence_digest):
        raise IdentityBindingError("evidence_digest must be sha256:<64 lowercase hex>")
    if evidence_locator is not None and not isinstance(evidence_locator, str):
        raise IdentityBindingError("evidence_locator must be a string")
    if verification_method is not None and not isinstance(verification_method, str):
        raise IdentityBindingError("verification_method must be a string")

    binding: dict[str, Any] = {
        "schema_version": IDENTITY_BINDING_SCHEMA_VERSION,
        "protocol": protocol.strip(),
        "subject": subject.strip(),
        "verified": verified,
    }
    if evidence_digest is not None:
        binding["evidence_digest"] = evidence_digest
    if evidence_locator is not None:
        binding["evidence_locator"] = evidence_locator
    if verification_method is not None:
        binding["verification_method"] = verification_method
    return binding


def attach_identity_binding(
    result_manifest: dict[str, Any], binding: dict[str, Any]
) -> dict[str, Any]:
    """Return a copy of a ResultManifest with identity evidence attached.

    Existing identity evidence is never silently replaced. This keeps provenance
    append-only at this semantic boundary and makes conflicting adapter claims
    explicit.
    """

    if not isinstance(result_manifest, dict):
        raise IdentityBindingError("ResultManifest must be an object")
    if not isinstance(binding, dict):
        raise IdentityBindingError("identity binding must be an object")
    if binding.get("schema_version") != IDENTITY_BINDING_SCHEMA_VERSION:
        raise IdentityBindingError("unsupported identity binding schema_version")

    # Rebuild through the constructor so callers cannot attach malformed data by
    # manually assembling an object.
    normalized = build_identity_binding(
        protocol=binding.get("protocol"),
        subject=binding.get("subject"),
        verified=binding.get("verified"),
        evidence_digest=binding.get("evidence_digest"),
        evidence_locator=binding.get("evidence_locator"),
        verification_method=binding.get("verification_method"),
    )

    updated = copy.deepcopy(result_manifest)
    extensions = updated.setdefault("extensions", {})
    if not isinstance(extensions, dict):
        raise IdentityBindingError("ResultManifest extensions must be an object")
    if IDENTITY_BINDING_EXTENSION in extensions:
        raise IdentityBindingError("identity binding already exists")
    extensions[IDENTITY_BINDING_EXTENSION] = normalized
    return updated


def get_identity_binding(result_manifest: dict[str, Any]) -> dict[str, Any] | None:
    """Return attached identity evidence without interpreting it as authority."""

    if not isinstance(result_manifest, dict):
        raise IdentityBindingError("ResultManifest must be an object")
    extensions = result_manifest.get("extensions", {})
    if not isinstance(extensions, dict):
        raise IdentityBindingError("ResultManifest extensions must be an object")
    value = extensions.get(IDENTITY_BINDING_EXTENSION)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise IdentityBindingError("identity binding extension must be an object")
    return value
