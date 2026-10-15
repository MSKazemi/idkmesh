#!/usr/bin/env python3
"""Generate the typed web-client declarations from ``openapi.yaml`` (issue #746).

``openapi.yaml`` maps every public contract to its canonical JSON Schema in
``schemas/``. This tool turns that catalog into one TypeScript declaration
file, ``clients/typescript/idkmesh-api.d.ts``, so a browser or Node integrator
gets compile-time types without hand-writing HTTP shapes or reading server
code. The file is checked in; ``tests/test_generate_api_types.py`` regenerates
it and requires byte equality, so it cannot drift from the contracts.

Properties of the generator:

- **Declarations only.** The output is a ``.d.ts``: no JavaScript runtime, no
  fetch wrapper, no package manifest, nothing published anywhere.
- **Standard library only, no network.** ``openapi.yaml`` is read through the
  existing stdlib reader ``tools/openapi_catalog.py`` (the PR Gate installs no
  YAML package); schemas are real JSON.
- **Deterministic.** Components, definitions, paths and methods are emitted in
  sorted order; properties and enum members keep the order of the JSON source;
  no floating-point arithmetic, set iteration, or clock is involved, so the
  bytes are identical on every supported Python version.
- **Fail closed.** A schema keyword the generator does not model raises
  :class:`ApiTypeGenerationError` naming the component and JSON pointer. The
  tool never falls back to ``any`` or silently drops structure.

Type mapping (the contract the tests pin):

====================================  =======================================
JSON Schema                           TypeScript
====================================  =======================================
``string`` / ``boolean`` / ``null``   ``string`` / ``boolean`` / ``null``
``integer`` / ``number``              ``number``
``const`` / ``enum``                  literal / union of literals
``type: [..., "null"]``               union including ``null``
``array`` + ``items``                 ``T[]``
``array`` + ``prefixItems``           fixed tuple (minItems == maxItems == n)
``object`` + ``properties``           object type; ``?`` unless ``required``
``additionalProperties: false``       no index signature
``additionalProperties: <schema>``    ``{ [key: string]: T }`` (no properties)
``anyOf`` / ``oneOf``                 union
``allOf`` / ``$ref`` with siblings    intersection
``$ref`` ``#/$defs/x`` / other file   named alias / the component's alias
====================================  =======================================

Soundness policy. Keywords that restrict which instances are *valid* without
changing the structural shape (``minimum``, ``pattern``, ``uniqueItems``,
``format``, ``if``/``then``/``else``, ``not``, ``contains``,
``propertyNames``, ``unevaluatedProperties``, ...) are deliberately not
modelled. The generated type is therefore a sound over-approximation: every
document that validates against the schema is assignable to the type, but not
every assignable value validates. The JSON Schema stays the authority;
``if``/``then``/``else`` is accepted only when its branches name properties the
enclosing schema already declares (otherwise a valid document could contain a
property the type forbids), and the generator fails closed when they do not.

Usage::

    python tools/generate_api_types.py            # rewrite the checked-in file
    python tools/generate_api_types.py --check    # exit 1 if it is stale
    python tools/generate_api_types.py --stdout   # print, write nothing

Exit codes: 0 success / up to date, 1 ``--check`` found drift, 2 the document
could not be converted (the message names the offending schema).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from openapi_catalog import parse_block_mapping_lists  # noqa: E402

OPENAPI_PATH = REPO_ROOT / "openapi.yaml"
SCHEMAS_DIR = REPO_ROOT / "schemas"
OUTPUT_PATH = REPO_ROOT / "clients" / "typescript" / "idkmesh-api.d.ts"
GENERATOR_NAME = "tools/generate_api_types.py"

# Annotations that carry no structure.
ANNOTATION_KEYWORDS = frozenset(
    {"$schema", "$id", "$comment", "title", "description", "default", "examples", "example"}
)
# Value constraints that narrow validity but not the structural type.
VALIDATION_KEYWORDS = frozenset(
    {
        "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
        "minLength", "maxLength", "pattern", "format",
        "minItems", "maxItems", "uniqueItems", "minProperties",
    }
)
# Applicators that only restrict validity; see the module docstring.
REFINEMENT_KEYWORDS = frozenset(
    {"if", "then", "else", "not", "contains", "propertyNames", "unevaluatedProperties"}
)
STRUCTURAL_KEYWORDS = frozenset(
    {
        "type", "properties", "required", "additionalProperties", "items",
        "prefixItems", "enum", "const", "$ref", "$defs", "allOf", "anyOf", "oneOf",
    }
)
SUPPORTED_KEYWORDS = (
    ANNOTATION_KEYWORDS | VALIDATION_KEYWORDS | REFINEMENT_KEYWORDS | STRUCTURAL_KEYWORDS
)
# Of the structural keywords, these (alone) make a schema "carry a shape".
SHAPE_KEYWORDS = frozenset(
    {
        "type", "properties", "additionalProperties", "items", "prefixItems",
        "enum", "const", "$ref", "allOf", "anyOf", "oneOf",
    }
)
SCALAR_TYPES = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "null": "null",
}
SCHEMA_URL = re.compile(r"^(?:https?://[^/]+/schemas/)?([A-Za-z0-9._-]+\.schema\.json)(?:#(.*))?$")
FLOW_REF = re.compile(r"""^\{\s*\$ref\s*:\s*["']([^"']+)["']\s*\}$""")
IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
JSON_VALUE = "IdkmeshJsonValue"
INLINE_PARAMETER_KEYWORDS = frozenset(
    {"type", "minimum", "maximum", "minLength", "maxLength", "pattern", "example", "description"}
)


class ApiTypeGenerationError(ValueError):
    """The OpenAPI document or a referenced schema cannot be converted safely."""


# --------------------------------------------------------------------------
# Naming and literals
# --------------------------------------------------------------------------

def pascal_case(text: str) -> str:
    """``idkmesh-api-error-v0.1`` -> ``IdkmeshApiErrorV01`` (first letter only)."""
    tokens = [t for t in re.split(r"[^A-Za-z0-9]+", text) if t]
    if not tokens:
        raise ApiTypeGenerationError(f"cannot derive a TypeScript name from {text!r}")
    name = "".join(t[0].upper() + t[1:] for t in tokens)
    if name[0].isdigit():
        name = "_" + name
    return name


def ts_literal(value: Any, where: str) -> str:
    """Render a JSON scalar as a TypeScript literal type."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise ApiTypeGenerationError(
        f"{where}: const/enum member of type {type(value).__name__} is not a scalar"
    )


def ts_key(name: str) -> str:
    return name if IDENTIFIER.match(name) else json.dumps(name, ensure_ascii=False)


def doc_comment(text: Any, indent: str) -> str:
    """One-line JSDoc from a description; empty when there is none."""
    if not isinstance(text, str):
        return ""
    flat = " ".join(text.split()).replace("*/", "*\\/")
    return f"{indent}/** {flat} */\n" if flat else ""


def union(members: list[str]) -> str:
    unique: list[str] = []
    for member in members:
        if member not in unique:
            unique.append(member)
    return " | ".join(unique)


def paren(expr: str) -> str:
    """Parenthesize a union so it can sit inside an array or intersection."""
    return f"({expr})" if " | " in expr and not _wrapped(expr) else expr


def _wrapped(expr: str) -> bool:
    if not (expr.startswith("(") and expr.endswith(")")):
        return False
    depth = 0
    for i, ch in enumerate(expr):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and i != len(expr) - 1:
                return False
    return True


def indent_block(text: str, prefix: str) -> str:
    return "\n".join((prefix + line) if line else line for line in text.split("\n"))


# --------------------------------------------------------------------------
# Schema translation
# --------------------------------------------------------------------------

class Component:
    """One ``components.schemas`` entry: its alias name and loaded JSON Schema."""

    def __init__(self, key: str, filename: str, schema: dict[str, Any], type_name: str) -> None:
        self.key = key
        self.filename = filename
        self.schema = schema
        self.type_name = type_name


class Registry:
    """Resolve schema files and ``$defs`` to the aliases this run will emit."""

    def __init__(self, components: dict[str, Component]) -> None:
        self.components = components
        self.by_filename = {c.filename: c for c in components.values()}

    def def_name(self, component: Component, def_key: str) -> str:
        # Injective on purpose: ``provenance_attempt`` and ``provenanceAttempt``
        # are distinct definitions in one schema, so word-splitting would collide.
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", def_key)
        return f"{component.type_name}_{cleaned[:1].upper()}{cleaned[1:]}"

    def resolve_pointer(self, component: Component, pointer: str, where: str) -> Any:
        node: Any = component.schema
        if pointer == "":
            return node
        if not pointer.startswith("/"):
            raise ApiTypeGenerationError(f"{where}: unsupported $ref fragment {pointer!r}")
        for raw in pointer[1:].split("/"):
            part = raw.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                raise ApiTypeGenerationError(f"{where}: $ref pointer {pointer!r} does not resolve")
        return node


class Translator:
    def __init__(self, registry: Registry) -> None:
        self.registry = registry

    # -- entry points ------------------------------------------------------

    def component_type(self, component: Component) -> str:
        expr = self.schema(component.schema, component, "", frozenset())
        if expr is None:
            raise ApiTypeGenerationError(
                f"{component.key}: schema has no structural keyword; refusing to emit an untyped alias"
            )
        return expr

    def def_type(self, component: Component, def_key: str) -> str:
        pointer = f"/$defs/{def_key}"
        node = component.schema["$defs"][def_key]
        expr = self.schema(node, component, pointer, frozenset())
        if expr is None:
            raise ApiTypeGenerationError(
                f"{component.key}{pointer}: definition has no structural keyword"
            )
        return expr

    # -- core --------------------------------------------------------------

    def schema(
        self, node: Any, comp: Component, pointer: str, known: frozenset[str], depth: int = 0
    ) -> str | None:
        """TypeScript for ``node``, or ``None`` for a pure refinement.

        ``known`` is the set of property names the enclosing object already
        declares; it bounds what ``if``/``then``/``else`` may mention.
        """
        where = f"{comp.key}{pointer or '/'}"
        if depth > 64:
            raise ApiTypeGenerationError(f"{where}: schema nesting exceeds 64 levels")
        if not isinstance(node, dict):
            raise ApiTypeGenerationError(
                f"{where}: boolean or non-object schema is not supported (would be untyped)"
            )
        unknown = sorted(set(node) - SUPPORTED_KEYWORDS)
        if unknown:
            raise ApiTypeGenerationError(
                f"{where}: unsupported JSON Schema keyword(s) {', '.join(unknown)}"
            )
        self._check_refinements(node, comp, pointer, known | self._declared(node))

        if not (set(node) & SHAPE_KEYWORDS):
            return None  # annotations / validation / refinements only

        parts: list[str] = []
        base = self._base(node, comp, pointer, known, depth, where)
        # A bare ``type`` next to a combinator is redundant (the members carry
        # their own types); dropping it keeps the output readable and is a
        # sound widening.
        combinator_keys = {"allOf", "anyOf", "oneOf"} & set(node)
        base_is_bare_type = set(node) & SHAPE_KEYWORDS == {"type"} | combinator_keys
        if base is not None and not (combinator_keys and base_is_bare_type):
            parts.append(base)

        local_known = known | self._declared(node)
        for keyword in ("anyOf", "oneOf"):
            if keyword in node:
                members = self._members(node[keyword], comp, pointer, keyword, local_known, depth, where)
                if members:
                    parts.append(union(members))
        if "allOf" in node:
            members = self._members(node["allOf"], comp, pointer, "allOf", local_known, depth, where)
            parts.extend(members)

        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return " & ".join(paren(p) for p in parts)

    def _base(
        self, node: dict[str, Any], comp: Component, pointer: str, known: frozenset[str],
        depth: int, where: str,
    ) -> str | None:
        if "const" in node:
            return ts_literal(node["const"], where)
        if "enum" in node:
            values = node["enum"]
            if not isinstance(values, list) or not values:
                raise ApiTypeGenerationError(f"{where}: enum must be a non-empty list")
            return union([ts_literal(v, where) for v in values])
        pieces: list[str] = []
        if "$ref" in node:
            pieces.append(self._ref(node["$ref"], comp, pointer, where))
            # Siblings of a $ref are additional constraints on the same value.
            siblings = {k: v for k, v in node.items() if k in {"properties", "items", "prefixItems", "additionalProperties"}}
            if siblings:
                extra = self._typed(siblings, comp, pointer, known, depth, where, None)
                if extra is not None:
                    pieces.append(extra)
            return " & ".join(paren(p) for p in pieces)
        declared = node.get("type")
        return self._typed(node, comp, pointer, known, depth, where, declared)

    def _typed(
        self, node: dict[str, Any], comp: Component, pointer: str, known: frozenset[str],
        depth: int, where: str, declared: Any,
    ) -> str | None:
        if declared is None:
            if "properties" in node or "additionalProperties" in node:
                types: list[str] = ["object"]
            elif "items" in node or "prefixItems" in node:
                types = ["array"]
            else:
                return None
        elif isinstance(declared, str):
            types = [declared]
        elif isinstance(declared, list) and declared and all(isinstance(t, str) for t in declared):
            types = list(declared)
        else:
            raise ApiTypeGenerationError(f"{where}: malformed 'type' {declared!r}")
        rendered: list[str] = []
        for t in types:
            if t in SCALAR_TYPES:
                rendered.append(SCALAR_TYPES[t])
            elif t == "array":
                rendered.append(self._array(node, comp, pointer, known, depth, where))
            elif t == "object":
                rendered.append(self._object(node, comp, pointer, known, depth, where))
            else:
                raise ApiTypeGenerationError(f"{where}: unsupported type {t!r}")
        return union(rendered)

    def _array(
        self, node: dict[str, Any], comp: Component, pointer: str, known: frozenset[str],
        depth: int, where: str,
    ) -> str:
        if "prefixItems" in node:
            prefix = node["prefixItems"]
            if not isinstance(prefix, list) or not prefix:
                raise ApiTypeGenerationError(f"{where}: prefixItems must be a non-empty list")
            if node.get("items", False) is not False:
                raise ApiTypeGenerationError(
                    f"{where}: prefixItems is supported only as a fixed tuple (no 'items' schema)"
                )
            for bound in ("minItems", "maxItems"):
                if node.get(bound) != len(prefix):
                    raise ApiTypeGenerationError(
                        f"{where}: tuple of {len(prefix)} requires {bound} == {len(prefix)} "
                        "or the type would reject valid shorter/longer arrays"
                    )
            elements = [
                self._required(p, comp, f"{pointer}/prefixItems/{i}", frozenset(), depth + 1)
                for i, p in enumerate(prefix)
            ]
            return "[" + ", ".join(elements) + "]"
        if "items" not in node and node.get("maxItems") == 0:
            return "[]"  # provably empty
        if "items" not in node:
            # No ``items`` means any JSON value per element (JSON Schema semantics).
            return f"{JSON_VALUE}[]"
        element = self._required(node["items"], comp, f"{pointer}/items", frozenset(), depth + 1)
        return f"{paren(element)}[]"

    def _object(
        self, node: dict[str, Any], comp: Component, pointer: str, known: frozenset[str],
        depth: int, where: str,
    ) -> str:
        properties = node.get("properties", {})
        if not isinstance(properties, dict):
            raise ApiTypeGenerationError(f"{where}: 'properties' must be an object")
        required_list = node.get("required", [])
        if not isinstance(required_list, list) or not all(isinstance(r, str) for r in required_list):
            raise ApiTypeGenerationError(f"{where}: 'required' must be a list of names")
        required = set(required_list)
        extras = node.get("additionalProperties", None)
        lines: list[str] = []
        for name, sub in properties.items():
            sub_pointer = f"{pointer}/properties/{name}"
            expr = self._required(sub, comp, sub_pointer, frozenset(), depth + 1)
            description = sub.get("description") if isinstance(sub, dict) else None
            lines.append(
                doc_comment(description, "  ")
                + f"  {ts_key(name)}{'' if name in required else '?'}: {expr.replace(chr(10), chr(10) + '  ')};"
            )
        for name in sorted(required - set(properties)):
            # Required by name but typed elsewhere (e.g. in an allOf member).
            if name not in known:
                lines.append(f"  {ts_key(name)}: {JSON_VALUE};")
        if extras is False:
            if not properties:
                return "Record<string, never>"
        elif extras is None or extras is True:
            if not properties:
                return f"{{ [key: string]: {JSON_VALUE} }}"
        elif isinstance(extras, dict):
            if properties:
                raise ApiTypeGenerationError(
                    f"{where}: properties together with a schema-valued additionalProperties "
                    "cannot be expressed soundly as one TypeScript object type"
                )
            value = self._required(extras, comp, f"{pointer}/additionalProperties", frozenset(), depth + 1)
            return f"{{ [key: string]: {value.replace(chr(10), chr(10) + '  ')} }}"
        else:
            raise ApiTypeGenerationError(f"{where}: malformed additionalProperties")
        body = "\n".join(lines)
        return "{\n" + body + "\n}" if body else "Record<string, never>"

    def _required(
        self, node: Any, comp: Component, pointer: str, known: frozenset[str], depth: int
    ) -> str:
        expr = self.schema(node, comp, pointer, known, depth)
        if expr is None and isinstance(node, dict) and set(node) <= ANNOTATION_KEYWORDS:
            # An annotation-only schema (``{}``) accepts any JSON value. Say so
            # with the explicit JSON union, never ``any``.
            return JSON_VALUE
        if expr is None:
            raise ApiTypeGenerationError(
                f"{comp.key}{pointer}: schema has no structural keyword; refusing to emit "
                "an untyped value (never 'any')"
            )
        return expr

    def _members(
        self, members: Any, comp: Component, pointer: str, keyword: str, known: frozenset[str],
        depth: int, where: str,
    ) -> list[str]:
        if not isinstance(members, list) or not members:
            raise ApiTypeGenerationError(f"{where}: {keyword} must be a non-empty list")
        rendered: list[str | None] = [
            self.schema(m, comp, f"{pointer}/{keyword}/{i}", known, depth + 1)
            for i, m in enumerate(members)
        ]
        concrete = [r for r in rendered if r is not None]
        if keyword != "allOf" and concrete and len(concrete) != len(rendered):
            raise ApiTypeGenerationError(
                f"{where}: {keyword} mixes structural and constraint-only members; "
                "a union would silently drop alternatives"
            )
        return concrete

    # -- references --------------------------------------------------------

    def _ref(self, ref: Any, comp: Component, pointer: str, where: str) -> str:
        if not isinstance(ref, str):
            raise ApiTypeGenerationError(f"{where}: $ref must be a string")
        if ref.startswith("#"):
            fragment = ref[1:]
            if fragment.startswith("/$defs/") and fragment.count("/") == 2:
                key = fragment[len("/$defs/"):]
                if key not in comp.schema.get("$defs", {}):
                    raise ApiTypeGenerationError(f"{where}: $ref {ref!r} names a missing definition")
                return self.registry.def_name(comp, key)
            return self._inline(comp, fragment, where)
        match = SCHEMA_URL.match(ref)
        if not match:
            raise ApiTypeGenerationError(f"{where}: unsupported $ref {ref!r}")
        filename, fragment = match.group(1), match.group(2)
        target = self.registry.by_filename.get(filename)
        if target is None:
            raise ApiTypeGenerationError(
                f"{where}: $ref {ref!r} names a schema that is not a component of openapi.yaml"
            )
        if not fragment:
            return target.type_name
        if fragment.startswith("/$defs/") and fragment.count("/") == 2:
            key = fragment[len("/$defs/"):]
            if key not in target.schema.get("$defs", {}):
                raise ApiTypeGenerationError(f"{where}: $ref {ref!r} names a missing definition")
            return self.registry.def_name(target, key)
        return self._inline(target, fragment, where)

    def _inline(self, comp: Component, fragment: str, where: str) -> str:
        """Translate the node a non-``$defs`` pointer names, in its own file."""
        node = self.registry.resolve_pointer(comp, fragment, where)
        expr = self.schema(node, comp, fragment, frozenset(), 1)
        if expr is None:
            raise ApiTypeGenerationError(f"{where}: $ref target {fragment!r} has no structural keyword")
        return paren(expr)

    # -- validity-only keywords -------------------------------------------

    @staticmethod
    def _declared(node: dict[str, Any]) -> frozenset[str]:
        """Property names ``node`` (and its allOf members) declare."""
        names: set[str] = set()
        props = node.get("properties")
        if isinstance(props, dict):
            names.update(props)
        for member in node.get("allOf", []) if isinstance(node.get("allOf"), list) else []:
            if isinstance(member, dict):
                names.update(Translator._declared(member))
        return frozenset(names)

    def _check_refinements(
        self, node: dict[str, Any], comp: Component, pointer: str, known: frozenset[str]
    ) -> None:
        """Refuse validity-only branches that mention undeclared properties."""
        for keyword in ("if", "then", "else", "not", "contains", "propertyNames"):
            branch = node.get(keyword)
            if branch is None:
                continue
            if keyword in {"contains", "propertyNames"}:
                # Constrain array members / key text only; they name no properties.
                if not isinstance(branch, dict):
                    raise ApiTypeGenerationError(f"{comp.key}{pointer}/{keyword}: malformed")
                continue
            self._refinement_names(branch, known, comp, f"{pointer}/{keyword}")

    def _refinement_names(
        self, branch: Any, known: frozenset[str], comp: Component, pointer: str
    ) -> None:
        if not isinstance(branch, dict):
            raise ApiTypeGenerationError(
                f"{comp.key}{pointer}: boolean/non-object refinement branch is not supported"
            )
        unknown_keys = sorted(set(branch) - SUPPORTED_KEYWORDS)
        if unknown_keys:
            raise ApiTypeGenerationError(
                f"{comp.key}{pointer}: unsupported JSON Schema keyword(s) {', '.join(unknown_keys)}"
            )
        mentioned: set[str] = set(branch.get("properties", {})) | set(branch.get("required", []))
        missing = sorted(mentioned - known)
        if missing:
            raise ApiTypeGenerationError(
                f"{comp.key}{pointer}: conditional branch names undeclared propert"
                f"{'y' if len(missing) == 1 else 'ies'} {', '.join(missing)}; the generated type "
                "would forbid a valid document"
            )
        for sub_keyword in ("not", "if", "then", "else"):
            if sub_keyword in branch:
                self._refinement_names(branch[sub_keyword], known, comp, f"{pointer}/{sub_keyword}")


# --------------------------------------------------------------------------
# openapi.yaml loading
# --------------------------------------------------------------------------

def load_openapi(path: Path = OPENAPI_PATH) -> dict[str, Any]:
    """Read ``openapi.yaml`` with the repository's stdlib block-mapping reader."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ApiTypeGenerationError(f"cannot read {path}: {exc}") from exc
    return parse_block_mapping_lists(text)


def load_components(
    openapi: dict[str, Any], schemas_dir: Path = SCHEMAS_DIR
) -> dict[str, Component]:
    section = openapi.get("components", {}).get("schemas")
    if not isinstance(section, dict) or not section:
        raise ApiTypeGenerationError("openapi.yaml has no components.schemas")
    components: dict[str, Component] = {}
    names: dict[str, str] = {}
    for key in sorted(section):
        raw = section[key]
        match = FLOW_REF.match(raw) if isinstance(raw, str) else None
        if not match:
            raise ApiTypeGenerationError(
                f"components.schemas.{key}: expected a single {{$ref: ...}} entry, got {raw!r}"
            )
        url = SCHEMA_URL.match(match.group(1))
        if not url or url.group(2):
            raise ApiTypeGenerationError(
                f"components.schemas.{key}: $ref {match.group(1)!r} is not a whole schema file"
            )
        filename = url.group(1)
        schema_path = schemas_dir / filename
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ApiTypeGenerationError(f"components.schemas.{key}: cannot load {filename}: {exc}") from exc
        if not isinstance(schema, dict):
            raise ApiTypeGenerationError(f"components.schemas.{key}: {filename} is not a JSON object")
        type_name = pascal_case(key)
        if type_name in names:
            raise ApiTypeGenerationError(
                f"components.schemas.{key} and .{names[type_name]} both map to TypeScript name {type_name}"
            )
        names[type_name] = key
        components[key] = Component(key, filename, schema, type_name)
    return components


# --------------------------------------------------------------------------
# Operations (paths)
# --------------------------------------------------------------------------

def _truthy(value: Any) -> bool:
    return str(value).strip().lower() == "true"


class OperationWriter:
    def __init__(self, openapi: dict[str, Any], components: dict[str, Component]) -> None:
        self.openapi = openapi
        self.components = components
        self.parameters = openapi.get("components", {}).get("parameters", {})
        self.responses = openapi.get("components", {}).get("responses", {})

    def schema_ref(self, schema: Any, where: str) -> str:
        """Type for an operation-level schema (a component ``$ref`` or a scalar)."""
        if not isinstance(schema, dict):
            raise ApiTypeGenerationError(f"{where}: schema must be a mapping")
        ref = schema.get("$ref")
        if ref is not None:
            prefix = "#/components/schemas/"
            if not isinstance(ref, str) or not ref.startswith(prefix):
                raise ApiTypeGenerationError(f"{where}: unsupported $ref {ref!r}")
            key = ref[len(prefix):]
            if key not in self.components:
                raise ApiTypeGenerationError(f"{where}: $ref names unknown component {key!r}")
            return self.components[key].type_name
        extra = sorted(set(schema) - INLINE_PARAMETER_KEYWORDS)
        if extra:
            raise ApiTypeGenerationError(f"{where}: unsupported inline schema keyword(s) {', '.join(extra)}")
        declared = schema.get("type")
        if declared in SCALAR_TYPES:
            return SCALAR_TYPES[declared]
        if declared == "object":
            return f"{{ [key: string]: {JSON_VALUE} }}"
        raise ApiTypeGenerationError(f"{where}: unsupported inline schema type {declared!r}")

    def parameter(self, item: Any, where: str) -> tuple[str, str, bool, str]:
        if not isinstance(item, dict):
            raise ApiTypeGenerationError(f"{where}: parameter must be a mapping")
        if "$ref" in item:
            prefix = "#/components/parameters/"
            ref = item["$ref"]
            if not isinstance(ref, str) or not ref.startswith(prefix) or ref[len(prefix):] not in self.parameters:
                raise ApiTypeGenerationError(f"{where}: unresolved parameter {ref!r}")
            item = self.parameters[ref[len(prefix):]]
        try:
            name, location = item["name"], item["in"]
        except (KeyError, TypeError) as exc:
            raise ApiTypeGenerationError(f"{where}: parameter lacks name/in") from exc
        if location not in {"path", "query"}:
            raise ApiTypeGenerationError(f"{where}: parameter location {location!r} is not supported")
        required = _truthy(item.get("required", "false")) or location == "path"
        return location, name, required, self.schema_ref(item.get("schema"), f"{where}.{name}")

    def content(self, content: Any, where: str, indent: str) -> str:
        if not isinstance(content, dict) or not content:
            raise ApiTypeGenerationError(f"{where}: empty content")
        lines = []
        for media in sorted(content):
            lines.append(
                f"{indent}  {json.dumps(media)}: "
                f"{self.schema_ref(content[media].get('schema') if isinstance(content[media], dict) else None, f'{where}.{media}')};"
            )
        return "{\n" + "\n".join(lines) + f"\n{indent}}}"

    def response(self, entry: Any, where: str, indent: str) -> str:
        if isinstance(entry, dict) and "$ref" in entry:
            prefix = "#/components/responses/"
            ref = entry["$ref"]
            if not isinstance(ref, str) or not ref.startswith(prefix) or ref[len(prefix):] not in self.responses:
                raise ApiTypeGenerationError(f"{where}: unresolved response {ref!r}")
            entry = self.responses[ref[len(prefix):]]
        if not isinstance(entry, dict):
            raise ApiTypeGenerationError(f"{where}: response must be a mapping")
        if "content" not in entry:
            return "Record<string, never>"
        return self.content(entry["content"], where, indent)

    def operation(self, method: str, path: str, op: Any) -> str:
        where = f"{method.upper()} {path}"
        if not isinstance(op, dict):
            raise ApiTypeGenerationError(f"{where}: operation must be a mapping")
        out: list[str] = []
        summary = op.get("summary")
        if isinstance(summary, str):
            out.append(doc_comment(summary, "  ").rstrip("\n"))
        out.append(f"  {json.dumps(where)}: {{")
        params = [self.parameter(p, where) for p in op.get("parameters", [])] if isinstance(op.get("parameters", []), list) else None
        if params is None:
            raise ApiTypeGenerationError(f"{where}: parameters must be a list")
        for location, label in (("path", "pathParameters"), ("query", "queryParameters")):
            chosen = sorted((p for p in params if p[0] == location), key=lambda p: p[1])
            if chosen:
                body = " ".join(f"{ts_key(n)}{'' if req else '?'}: {t};" for _, n, req, t in chosen)
                out.append(f"    {label}: {{ {body} }};")
        if "requestBody" in op:
            body = op["requestBody"]
            if not isinstance(body, dict) or "content" not in body:
                raise ApiTypeGenerationError(f"{where}: requestBody needs content")
            out.append(f"    requestBody: {self.content(body['content'], where + ' requestBody', '    ')};")
        responses = op.get("responses")
        if not isinstance(responses, dict) or not responses:
            raise ApiTypeGenerationError(f"{where}: operation has no responses")
        out.append("    responses: {")
        for status in sorted(responses):
            out.append(
                f"      {json.dumps(status)}: "
                f"{self.response(responses[status], f'{where} {status}', '      ')};"
            )
        out.append("    };")
        out.append("  };")
        return "\n".join(out)

    def render(self) -> str:
        paths = self.openapi.get("paths")
        if not isinstance(paths, dict) or not paths:
            raise ApiTypeGenerationError("openapi.yaml has no paths")
        operations: list[str] = []
        for path in sorted(paths):
            item = paths[path]
            if not isinstance(item, dict):
                raise ApiTypeGenerationError(f"{path}: path item must be a mapping")
            for method in sorted(item):
                if method not in {"get", "post", "put", "patch", "delete"}:
                    raise ApiTypeGenerationError(f"{path}: unsupported path-item key {method!r}")
                operations.append(self.operation(method, path, item[method]))
        return (
            "/** Every served operation, keyed `METHOD /path`. */\n"
            "export interface IdkmeshApiOperations {\n" + "\n".join(operations) + "\n}\n\n"
            "export type IdkmeshApiOperationName = keyof IdkmeshApiOperations;\n"
        )


# --------------------------------------------------------------------------
# Top-level generation
# --------------------------------------------------------------------------

def header(openapi: dict[str, Any]) -> str:
    info = openapi.get("info", {})
    return (
        "// GENERATED FILE - DO NOT EDIT.\n"
        f"// Generator: {GENERATOR_NAME} (issue #746). Regenerate with:\n"
        f"//   python {GENERATOR_NAME}\n"
        "// Source: openapi.yaml and the JSON Schemas in schemas/ it catalogs.\n"
        f"// OpenAPI: {info.get('title', 'unknown')} (version {info.get('version', 'unknown')}).\n"
        "//\n"
        "// Declarations only: no runtime code, no network access, nothing to publish.\n"
        "// Mapping: integer and number -> number; const/enum -> literal unions; nullable\n"
        "// types -> `| null`; allOf -> `&`; anyOf/oneOf -> `|`. Value constraints (pattern,\n"
        "// minimum, uniqueItems, if/then/else, ...) are NOT encoded: every document that\n"
        "// validates against a schema is assignable to its type, but assignable values\n"
        "// are not guaranteed valid. The JSON Schema in schemas/ remains the authority.\n"
    )


def security_header_type(openapi: dict[str, Any]) -> str:
    schemes = openapi.get("components", {}).get("securitySchemes", {})
    lines = []
    for name in sorted(schemes):
        scheme = schemes[name]
        if not isinstance(scheme, dict) or scheme.get("type") != "apiKey" or scheme.get("in") != "header":
            raise ApiTypeGenerationError(f"securitySchemes.{name}: only header apiKey schemes are supported")
        lines.append(
            f"/** Header carrying the `{name}` credential. */\n"
            f"export type {pascal_case(name)}HeaderName = {json.dumps(scheme.get('name'))};\n"
        )
    return "\n".join(lines)


def generate(
    openapi_path: Path = OPENAPI_PATH,
    schemas_dir: Path = SCHEMAS_DIR,
    openapi: dict[str, Any] | None = None,
    components: dict[str, Component] | None = None,
) -> str:
    """Return the full text of the declaration file."""
    if openapi is None:
        openapi = load_openapi(openapi_path)
    if components is None:
        components = load_components(openapi, schemas_dir)
    registry = Registry(components)
    translator = Translator(registry)
    declared: set[str] = {JSON_VALUE}

    def declare(name: str, where: str) -> None:
        if name in declared:
            raise ApiTypeGenerationError(f"{where}: duplicate TypeScript declaration {name}")
        declared.add(name)

    blocks: list[str] = []
    for key in sorted(components):
        comp = components[key]
        declare(comp.type_name, key)
        doc = doc_comment(comp.schema.get("description"), "")
        blocks.append(f"{doc}export type {comp.type_name} = {translator.component_type(comp)};\n")
        defs = comp.schema.get("$defs", {})
        if not isinstance(defs, dict):
            raise ApiTypeGenerationError(f"{key}: $defs must be an object")
        for def_key in sorted(defs):
            def_name = registry.def_name(comp, def_key)
            declare(def_name, f"{key}/$defs/{def_key}")
            doc = doc_comment(defs[def_key].get("description") if isinstance(defs[def_key], dict) else None, "")
            blocks.append(f"{doc}export type {def_name} = {translator.def_type(comp, def_key)};\n")
    json_value = (
        "/** Any JSON value: the explicit type for schemas that constrain nothing. */\n"
        f"export type {JSON_VALUE} =\n"
        "  | string\n  | number\n  | boolean\n  | null\n"
        f"  | {JSON_VALUE}[]\n"
        f"  | {{ [key: string]: {JSON_VALUE} }};\n"
    )
    parts = [header(openapi), json_value, security_header_type(openapi), "\n".join(blocks), OperationWriter(openapi, components).render()]
    return "\n".join(p for p in parts if p)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="declaration file to write or check")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="exit 1 when the file on disk is stale; write nothing")
    mode.add_argument("--stdout", action="store_true", help="print the declarations; write nothing")
    args = parser.parse_args(argv)
    try:
        text = generate()
    except ApiTypeGenerationError as exc:
        print(f"generate_api_types: {exc}", file=sys.stderr)
        return 2
    if args.stdout:
        sys.stdout.write(text)
        return 0
    if args.check:
        try:
            current = args.output.read_text(encoding="utf-8")
        except OSError:
            current = None
        if current != text:
            print(f"generate_api_types: {args.output} is stale; run python {GENERATOR_NAME}", file=sys.stderr)
            return 1
        print(f"{args.output} is up to date")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
