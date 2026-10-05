#!/usr/bin/env python3
"""OpenAPI / JSON Schema reference resolution gate (issue #737).

`docs/specifications/API_CONVENTIONS_V0_1.md` section 19 requires that every
OpenAPI schema reference resolves and that unresolved references fail CI. This
tool is that check for the two contract surfaces in this repository:

- ``openapi.yaml`` at the repository root: every ``$ref`` must resolve. Internal
  ``#/components/<section>/<key>`` references must name a component this
  document actually defines; schema references must name a file that exists in
  ``schemas/`` whose ``$id`` agrees with the referenced name.
- every ``*.json`` document in ``schemas/``: every ``$ref`` must resolve, either
  as an internal JSON pointer inside its own document or as a cross-file schema
  reference resolved the same way as above.

Resolution is basename-based on purpose. Schema ``$id`` values in this
repository intentionally live on several hosts (``idkmesh.org``,
``idkmesh.dev``, ``github.com``, ``mskazemi.com``) while
``tests/test_schema_identity.py`` pins the invariant that matters:
``$id``'s final path segment equals the schema's own filename. A reference
resolves correctly when it names an existing file whose ``$id`` carries that
same basename. Anything else -- an unknown host outside the ``/schemas/``
namespace, an unsupported internal pointer shape, a missing ``$defs`` entry --
is reported as unresolved and fails the gate. There is no ignore list.

Like ``tests/test_workflow_tool_contracts.py``, the YAML surface is scanned as
text rather than parsed: the PR Gate installs only pytest and
``requirements-phase0.txt`` (jsonschema), so ``import yaml`` would pass on a
developer machine and fail in the very gate this file serves. Schema documents
are real JSON and are parsed with the standard library. Dependency-free by
design, matching ``tools/schema_compat_check.py``.

Exit codes: 0 every reference resolves, 1 unresolved references were found,
2 the gate could not run (missing/invalid input it cannot interpret).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENAPI_NAME = "openapi.yaml"
SCHEMAS_DIR = "schemas"

# Matches `$ref: "value"`, `$ref: 'value'`, the quoted-key form `"$ref": "value"`
# and the flow-mapping form `{$ref: "value"}`.
YAML_REF = re.compile(r"""["']?\$ref["']?\s*:\s*(?:"([^"]+)"|'([^']+)')""")
YAML_TOP_COMPONENTS = re.compile(r"^components:\s*$")
YAML_SUBSECTION = re.compile(r"^  ([A-Za-z0-9._-]+):\s*$")
YAML_COMPONENT_KEY = re.compile(r'^    (?:"([^"]+)"|([A-Za-z0-9._-]+)):(?:\s|$)')
SCHEMA_URL = re.compile(r"^https?://[^/]+?/schemas/([^#]+?\.schema\.json)(?:#(.*))?$")


class OpenApiRefCheckError(RuntimeError):
    """The gate could not run against the given tree."""


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _component_keys(text: str) -> dict[str, set[str]]:
    """Extract `components.<section>.<key>` names from the YAML text.

    Bounded scanner for the repository's own document shape: `components:` at
    column 0, its sections at indent 2, component keys at indent 4. Anything
    this cannot interpret is simply absent, so an internal reference to it
    fails closed as unresolved.
    """
    sections: dict[str, set[str]] = {}
    current: str | None = None
    in_components = False
    for line in text.splitlines():
        if YAML_TOP_COMPONENTS.match(line):
            in_components = True
            current = None
            continue
        if not in_components:
            continue
        if line and not line.startswith(" "):
            break
        subsection = YAML_SUBSECTION.match(line)
        if subsection:
            current = subsection.group(1)
            sections.setdefault(current, set())
            continue
        if current is not None:
            key = YAML_COMPONENT_KEY.match(line)
            if key:
                sections[current].add(key.group(1) or key.group(2))
    return sections


def _resolve_json_pointer(document: object, pointer: str) -> bool:
    if pointer in ("", "#"):
        return True
    if not pointer.startswith("#/"):
        return False
    target = document
    for raw in unquote(pointer[2:]).split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(target, dict) and part in target:
            target = target[part]
        elif isinstance(target, list) and part.isdigit() and int(part) < len(target):
            target = target[int(part)]
        else:
            return False
    return True


def _schema_file_for(basename: str, root: Path) -> Path:
    return root / SCHEMAS_DIR / basename


def _check_schema_target(
    ref: str, basename: str, fragment: str | None, root: Path,
    source: str, violations: list[dict[str, str]],
) -> bool:
    """Resolve one reference to a schemas/ document; record why on failure."""
    target = _schema_file_for(basename, root)
    if not target.is_file():
        violations.append({"source": source, "ref": ref,
                           "reason": f"{SCHEMAS_DIR}/{basename} does not exist"})
        return False
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        violations.append({"source": source, "ref": ref,
                           "reason": f"{SCHEMAS_DIR}/{basename} is not valid JSON: {exc}"})
        return False
    identity = document.get("$id") if isinstance(document, dict) else None
    if not isinstance(identity, str) or Path(urlparse(identity).path).name != basename:
        violations.append({
            "source": source, "ref": ref,
            "reason": (f"{SCHEMAS_DIR}/{basename} declares $id {identity!r}, "
                       "which does not agree with the referenced file name"),
        })
        return False
    pointer = None if fragment is None else (fragment if fragment.startswith("#") else "#" + fragment)
    if pointer is not None and not _resolve_json_pointer(document, pointer):
        violations.append({"source": source, "ref": ref,
                           "reason": f"pointer {pointer} does not resolve inside "
                                     f"{SCHEMAS_DIR}/{basename}"})
        return False
    return True


def _check_ref(
    ref: str, source: str, root: Path, *,
    yaml_components: dict[str, set[str]] | None,
    json_document: object | None,
    violations: list[dict[str, str]],
) -> bool:
    if ref.startswith("#"):
        if json_document is not None:
            if _resolve_json_pointer(json_document, ref):
                return True
            violations.append({"source": source, "ref": ref,
                               "reason": "internal pointer does not resolve inside its document"})
            return False
        match = re.fullmatch(r"#/components/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)", ref)
        if match and yaml_components is not None:
            section, key = match.groups()
            if key in yaml_components.get(section, ()):
                return True
            violations.append({"source": source, "ref": ref,
                               "reason": f"no component '{key}' is defined under components.{section}"})
            return False
        violations.append({"source": source, "ref": ref,
                           "reason": "unsupported internal reference shape for the YAML document"})
        return False
    match = SCHEMA_URL.match(ref)
    if match:
        return _check_schema_target(ref, match.group(1),
                                    match.group(2) if match.group(2) else None,
                                    root, source, violations)
    candidate = ref.split("#", 1)[0]
    if candidate.endswith(".schema.json"):
        basename = Path(urlparse(candidate).path).name
        fragment = ref.split("#", 1)[1] if "#" in ref else None
        return _check_schema_target(ref, basename, fragment, root, source, violations)
    violations.append({"source": source, "ref": ref,
                       "reason": ("reference is outside the schemas/ namespace "
                                  "and cannot be resolved")})
    return False


def check_references(root: Path) -> dict[str, object]:
    """Check every reference in openapi.yaml and schemas/*.json under root."""
    root = Path(root)
    openapi_path = root / OPENAPI_NAME
    if not openapi_path.is_file():
        raise OpenApiRefCheckError(f"{OPENAPI_NAME} is missing from {root}")
    schema_paths = sorted((root / SCHEMAS_DIR).glob("*.json"))
    if not schema_paths:
        raise OpenApiRefCheckError(f"no schema documents found under {root / SCHEMAS_DIR}")

    violations: list[dict[str, str]] = []
    counts = {"openapi_refs": 0, "schema_refs": 0,
              "schema_documents": len(schema_paths), "components": 0}

    text = openapi_path.read_text(encoding="utf-8")
    components = _component_keys(text)
    counts["components"] = sum(len(keys) for keys in components.values())
    for match in YAML_REF.finditer(text):
        ref = match.group(1) or match.group(2)
        counts["openapi_refs"] += 1
        _check_ref(ref, f"{OPENAPI_NAME}:{_line_of(text, match.start())}", root,
                   yaml_components=components, json_document=None,
                   violations=violations)

    for path in schema_paths:
        source = f"{SCHEMAS_DIR}/{path.name}"
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            violations.append({"source": source, "ref": "", "reason": f"not valid JSON: {exc}"})
            continue
        refs: list[str] = []

        def walk(node: object) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "$ref" and isinstance(value, str):
                        refs.append(value)
                    else:
                        walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(document)
        for ref in refs:
            counts["schema_refs"] += 1
            _check_ref(ref, source, root, yaml_components=None,
                       json_document=document, violations=violations)

    return {
        "kind": "idkmesh-openapi-ref-check",
        "ok": not violations,
        "counts": counts,
        "violations": violations,
    }


def format_report(report: dict[str, object]) -> str:
    counts = report["counts"]
    assert isinstance(counts, dict)
    summary = (
        f"openapi-ref-check: {counts['openapi_refs']} reference(s) in {OPENAPI_NAME} and "
        f"{counts['schema_refs']} reference(s) across {counts['schema_documents']} "
        f"schema document(s); {counts['components']} component key(s) tracked"
    )
    violations = report["violations"]
    assert isinstance(violations, list)
    if not violations:
        return summary + "\nopenapi-ref-check: no unresolved references"
    lines = [summary, f"openapi-ref-check: {len(violations)} unresolved reference(s):"]
    for item in violations:
        assert isinstance(item, dict)
        detail = f" ({item['reason']})" if item["reason"] else ""
        lines.append(f"  {item['source']}: {item['ref']}{detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--root", default=None,
                        help="repository root to check (default: this repository)")
    args = parser.parse_args(argv)
    try:
        report = check_references(Path(args.root) if args.root else REPO_ROOT)
    except OpenApiRefCheckError as exc:
        print(f"openapi-ref-check: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_report(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
