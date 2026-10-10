#!/usr/bin/env python3
"""Detect a breaking change to an existing ``schemas/*.json`` file.

Policy (issue #737, "backwards-compatibility diff check for stable v1
objects"): every schema in ``schemas/`` is versioned in its own filename
(``-v0.1.schema.json``, ``-v0.2.schema.json``, ...). Once a schema file
exists, its content must never change in a way that could reject data a
prior version of the same file accepted, or accept data the prior version
rejected in a way a consumer would not expect. The sanctioned way to make a
breaking change is to add a *new*, separately versioned file -- exactly
what ``work-unit-v0.1.schema.json`` -> ``work-unit-v0.2.schema.json``
already did. A brand-new file has nothing to compare against, so it is
never a compatibility violation on its own.

This module has no CLI-framework or network dependency; it shells out to
``git show`` for old content and stdlib ``json`` for parsing, matching
``scripts/testkit.py``'s own dependency discipline for a required CI gate.

## Mechanical rule

Both the old and new document are walked recursively. Every dict node that
carries a ``"properties"`` key is a comparison point, addressed by its JSON
Pointer path from the document root (``""`` for the root, ``/properties/foo``
for a nested object under top-level property ``foo``, and so on through
``/items`` and ``/$defs/<name>``). At each node present in both documents:

- a key removed from ``properties`` is breaking (a client reading that
  field loses it);
- any change to the ``required`` array, in either direction, is breaking
  (both "a client can no longer assume this field is present" and "a
  producer must now always populate a new field" are real contract
  changes);
- any change to ``additionalProperties`` is breaking;
- for a property that is itself *not* a "properties"-bearing object (a
  leaf: ``type``, ``const``, ``enum``, ``pattern``, ``anyOf`` of scalars,
  ``$ref``, ...), a change to its subschema is breaking unless it is one
  of three recognized changes: ``enum`` gaining values (old values all
  still present; this repository already does this in place, for example
  ``search-visibility-observation-v0.1.schema.json``'s surface enum), or
  ``type`` gaining an alternative (the old type(s) all still accepted,
  for example ``"string"`` widened to ``["string", "null"]``), or the
  end-anchor hardening of ADR-0025 (a ``pattern`` ending in ``$`` gains
  the ``(?!\n)`` guard and changes nothing else). Any other change to a
  leaf subschema -- narrowing of the first two, or a change to anything
  else (``const``, ``pattern``, numeric bounds, ``anyOf``/``oneOf``,
  ``$ref`` target, ...) -- is breaking. This is deliberately conservative
  outside those three shapes: the fix for a genuine narrowing is the
  same either way, a new versioned file.

The anchor hardening is the one recognized *narrowing*. Python's ``re``
matches ``$`` before a trailing newline, so a ``^...$`` pattern accepted
``value + "\\n"`` under this repository's Python validators while the
JSON Schema specification's ECMA-262 regex semantics never did. Adding
the ``(?!\n)`` guard makes Python validation agree with the contract the
pattern already declared, and rejects exactly the strings a trailing
newline smuggled in -- nothing else (issue #963, ADR-0025). It is
recognized only in that exact mechanical form so it cannot launder any
other pattern change.

A node present in the old document but entirely absent from the new one
(the containing property itself was removed) is reported once, at its
parent's property-removal check; it is not walked as its own node.

## Known limitation (v0.1 of this tool)

``allOf``/``oneOf`` branches and schema composition via ``$ref`` targets
outside ``#/$defs`` are not resolved or walked -- a change hidden purely
inside one is not detected. Every schema in this repository as of the
2026-09 API-2 slice uses ``$ref`` only against its own ``#/$defs/...``,
so this does not currently hide anything, but a future schema using
cross-file ``$ref`` or ``allOf`` composition needs this tool extended
before it can be trusted for that file.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "schemas"


class SchemaCompatError(RuntimeError):
    """Raised when the old content at a ref cannot be loaded or parsed."""


def _git_show(ref: str, relative_path: str) -> str | None:
    """Return the file's content at ``ref``, or ``None`` if it did not exist there."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{relative_path}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # git show fails both for "file did not exist at this ref" and for
        # "ref does not resolve"; the caller has already validated the ref
        # resolves (see main()), so a nonzero exit here means a new file.
        return None
    return result.stdout


def _walk_object_nodes(doc: Any, path: str = "") -> dict[str, dict]:
    """Return {json_pointer_path: node} for every properties-bearing dict."""
    nodes: dict[str, dict] = {}
    if not isinstance(doc, dict):
        return nodes
    if isinstance(doc.get("properties"), dict):
        nodes[path] = doc
        for key, child in doc["properties"].items():
            nodes.update(_walk_object_nodes(child, f"{path}/properties/{key}"))
    if isinstance(doc.get("items"), dict):
        nodes.update(_walk_object_nodes(doc["items"], f"{path}/items"))
    if isinstance(doc.get("$defs"), dict):
        for key, child in doc["$defs"].items():
            nodes.update(_walk_object_nodes(child, f"{path}/$defs/{key}"))
    return nodes


def _type_set(value: Any) -> set[str] | None:
    """Normalize a JSON Schema ``type`` value to a set, or None if absent."""
    if isinstance(value, str):
        return {value}
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return set(value)
    return None


# ADR-0025 end-anchor hardening (issue #963). ``json.load`` decodes the
# JSON escape ``\\n`` in a pattern string to a literal newline, so the
# guard suffix is written here as a literal newline too; ``(?!`` + newline
# + ``)`` is the same regex assertion as the ``(?!\n)`` escape, and stays
# valid ECMA-262 for non-Python validators.
ANCHOR_SUFFIX = "(?!\n)"


def _pattern_hardened(old: Any, new: Any) -> bool:
    """True for one ADR-0025 pattern change: ``P$`` -> ``P$`` + suffix."""
    return (
        isinstance(old, str)
        and isinstance(new, str)
        and old.endswith("$")
        and not old_pattern_escaped(old)
        and new == old + ANCHOR_SUFFIX
    )


def old_pattern_escaped(pattern: str) -> bool:
    """True if the trailing ``$`` is an escaped literal, not an anchor."""
    return pattern.endswith("\\$")


def _hardening_only_change(old: Any, new: Any) -> bool:
    """True if every difference is the ADR-0025 end-anchor hardening.

    Walks both subschemas in parallel at any depth (``items`` entries,
    ``anyOf`` branches, nested objects). Every ``pattern`` value must be
    identical or a recognized hardening -- an old value ending in an
    unescaped ``$`` followed by exactly ``ANCHOR_SUFFIX`` -- and every
    other node must be structurally identical. Anything else falls
    through to the widening checks and is reported as breaking.
    """
    if isinstance(old, dict) and isinstance(new, dict):
        if set(old) != set(new):
            return False
        for key in old:
            if key == "pattern":
                if old[key] != new[key] and not _pattern_hardened(old[key], new[key]):
                    return False
            elif not _hardening_only_change(old[key], new[key]):
                return False
        return True
    if isinstance(old, list) and isinstance(new, list):
        return len(old) == len(new) and all(
            _hardening_only_change(o, n) for o, n in zip(old, new)
        )
    return old == new


def _leaf_compatible(old: dict, new: dict) -> bool:
    """True if a leaf (non-object) subschema change is a recognized one.

    Three shapes are recognized as compatible: an ``enum`` that only
    gains values, a ``type`` that only gains alternatives (each with
    every other key in the subschema unchanged), and the ADR-0025
    end-anchor hardening of a ``pattern``. Anything else -- including a
    narrowing of the first two, or any change this function does not
    specifically recognize -- is reported as breaking by the caller.
    """
    if _hardening_only_change(old, new):
        return True
    old_other = {k: v for k, v in old.items() if k not in ("enum", "type")}
    new_other = {k: v for k, v in new.items() if k not in ("enum", "type")}
    if old_other != new_other:
        return False

    old_enum, new_enum = old.get("enum"), new.get("enum")
    if old_enum is not None or new_enum is not None:
        if not (isinstance(old_enum, list) and isinstance(new_enum, list)):
            return False
        if not set(old_enum) <= set(new_enum):
            return False

    old_types, new_types = _type_set(old.get("type")), _type_set(new.get("type"))
    if old.get("type") is not None or new.get("type") is not None:
        if old_types is None or new_types is None:
            return False
        if not old_types <= new_types:
            return False

    return True


def diff_schema(old: dict, new: dict) -> list[str]:
    """Return a list of breaking-change descriptions; empty means compatible."""
    violations: list[str] = []
    old_nodes = _walk_object_nodes(old)
    new_nodes = _walk_object_nodes(new)

    for path, old_node in old_nodes.items():
        new_node = new_nodes.get(path)
        if new_node is None:
            # The whole object at this path disappeared. If it is the root,
            # or its parent property removal was not already caught (the
            # parent node itself vanished too), record it directly so a
            # deleted nested object is never silently unreported.
            violations.append(f"{path or '(root)'}: object removed entirely")
            continue

        old_props = set(old_node.get("properties", {}))
        new_props = set(new_node.get("properties", {}))
        for removed in sorted(old_props - new_props):
            violations.append(f"{path}/properties/{removed}: property removed")

        old_required = set(old_node.get("required", []) or [])
        new_required = set(new_node.get("required", []) or [])
        if old_required != new_required:
            gained = sorted(new_required - old_required)
            lost = sorted(old_required - new_required)
            detail = []
            if gained:
                detail.append(f"gained required {gained}")
            if lost:
                detail.append(f"lost required {lost}")
            violations.append(f"{path or '(root)'}: required changed ({'; '.join(detail)})")

        if old_node.get("additionalProperties") != new_node.get("additionalProperties"):
            violations.append(
                f"{path or '(root)'}: additionalProperties changed "
                f"({old_node.get('additionalProperties')!r} -> "
                f"{new_node.get('additionalProperties')!r})"
            )

        for key in sorted(old_props & new_props):
            old_child = old_node["properties"][key]
            new_child = new_node["properties"][key]
            child_path = f"{path}/properties/{key}"
            if child_path in old_nodes:
                # A nested object: its own structure is checked as its own
                # node above (or will be, once the outer loop reaches it).
                continue
            if old_child != new_child and not _leaf_compatible(old_child, new_child):
                violations.append(f"{child_path}: schema changed")

    return violations


def check_file(relative_path: str, base_ref: str) -> list[str]:
    """Return violations for one schema file, or [] if new/unchanged/compatible."""
    old_text = _git_show(base_ref, relative_path)
    if old_text is None:
        return []
    new_text = (ROOT / relative_path).read_text(encoding="utf-8")
    try:
        old_doc = json.loads(old_text)
    except json.JSONDecodeError as exc:
        raise SchemaCompatError(
            f"{relative_path}: old content at {base_ref} is not valid JSON: {exc}"
        ) from exc
    try:
        new_doc = json.loads(new_text)
    except json.JSONDecodeError as exc:
        raise SchemaCompatError(f"{relative_path}: current content is not valid JSON: {exc}") from exc
    if old_doc == new_doc:
        return []
    return diff_schema(old_doc, new_doc)


def _ref_resolves(ref: str) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def check_tree(base_ref: str, schemas_dir: Path = SCHEMAS_DIR) -> dict[str, list[str]]:
    """Return {relative_path: violations} for every schema with a violation.

    Raises SchemaCompatError if ``base_ref`` does not resolve, rather than
    silently treating every schema as new (which is what an unresolvable ref
    would otherwise look like to ``_git_show``).
    """
    if not _ref_resolves(base_ref):
        raise SchemaCompatError(f"--base {base_ref!r} does not resolve to a commit")
    report: dict[str, list[str]] = {}
    for path in sorted(schemas_dir.glob("*.json")):
        relative_path = str(path.relative_to(ROOT))
        violations = check_file(relative_path, base_ref)
        if violations:
            report[relative_path] = violations
    return report


def _resolve_base_ref(explicit: str | None) -> str:
    if explicit is not None:
        return explicit
    result = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SchemaCompatError(
            "no --base given and `git merge-base HEAD origin/main` failed "
            f"({result.stderr.strip()}); pass --base explicitly"
        )
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base",
        default=None,
        help="git ref to compare against (default: merge-base of HEAD and origin/main)",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        base_ref = _resolve_base_ref(args.base)
        report = check_tree(base_ref)
    except SchemaCompatError as exc:
        print(f"schema-compat-check: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"base": base_ref, "violations": report}, indent=2, sort_keys=True))
    elif report:
        print(f"schema-compat-check: breaking change(s) against {base_ref}:")
        for relative_path, violations in report.items():
            print(f"  {relative_path}:")
            for violation in violations:
                print(f"    - {violation}")
        print(
            "\nA schema file's content must never change incompatibly once it "
            "exists. Add a new, separately versioned file instead (see "
            "docs/decisions/ADR-0020-schema-backward-compatibility-gate.md)."
        )
    else:
        print(f"schema-compat-check: no breaking changes against {base_ref}")

    return 1 if report else 0


if __name__ == "__main__":
    raise SystemExit(main())
