"""Stdlib-only reader for the block-mapping subset of ``openapi.yaml``.

Deliberately not a YAML parser: this must run where only the standard
library exists (``requirements-phase0.txt`` installs jsonschema alone).
Line shapes that do not match are ignored rather than guessed at.

Two entry points share one set of line rules:

- ``parse_block_mapping`` -- the original behavior, kept byte-compatible
  for its existing consumers (the API contract-conformance and OpenAPI
  document tests): list items and block scalars are skipped wholesale,
  because nothing those modules assert lives inside one. What remains is
  the nested ``key: value`` mapping tree: paths, verbs, response codes,
  media types, schema references, and the ``components`` sections.
- ``parse_block_mapping_lists`` -- the same tree plus YAML block lists
  captured as Python lists: mapping items (``parameters``) become dicts
  whose continuation keys nest like any other key, and scalar items
  become unquoted scalars. The compatibility gate
  (``tools/schema_compat_check.py``) needs parameter names and their
  ``required`` flags to diff the request surface; every other line is
  handled exactly as in ``parse_block_mapping``, which
  ``tests/test_schema_compat_check.py`` pins against the real document.

Known limitation (shared by both): flow-style collections (``[a, b]``,
``{k: v}``) are kept as their raw scalar string, and block scalars are
kept as their ``|``/``>`` marker rather than their content.
"""

from __future__ import annotations

import re

_KEY = re.compile(r"""^(?:"([^"]*)"|'([^']*)'|([^\s:][^:]*?)):(?:\s+(.*))?$""")
_BLOCK_SCALAR = re.compile(r"^[>|][+-]?\d*$")


def _unquote(value: str) -> str:
    """Strip one layer of matching YAML quotes from a scalar value."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _split_key(stripped: str) -> tuple[str, str | None] | None:
    """Return ``(key, value-or-None)`` for a ``key: value`` line, else None."""
    match = _KEY.match(stripped)
    if match is None:
        return None
    double, single, plain, value = match.groups()
    key = (
        double if double is not None else single if single is not None else plain
    ).strip()
    return key, value


def parse_block_mapping(text: str) -> dict:
    """Parse the mapping tree, skipping list items wholesale.

    A list item (security schemes, parameters) and its continuation lines
    are skipped; the key that would hold them keeps an empty dict.
    """
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    skip_indent: int | None = None
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))
        if skip_indent is not None:
            if indent > skip_indent or stripped.startswith("- "):
                continue
            skip_indent = None
        if stripped.startswith("- "):
            # A list item (security schemes, parameters). Skip it and its
            # continuation lines; no advertised schema lives inside one.
            skip_indent = indent
            continue
        pair = _split_key(stripped)
        if pair is None:
            continue
        key, value = pair
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if value is None or value == "":
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        elif _BLOCK_SCALAR.match(value):
            skip_indent = indent
            parent[key] = value
        else:
            parent[key] = _unquote(value)
    return root


def parse_block_mapping_lists(text: str) -> dict:
    """Parse the mapping tree, capturing YAML block lists as Python lists.

    A key with an empty value that is followed by ``- `` items becomes a
    list; the same key followed by nested keys becomes a dict, exactly
    like :func:`parse_block_mapping`.
    """
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    skip_indent: int | None = None
    # An empty-value key awaiting its first child line:
    # (key_indent, parent_dict, key, placeholder_dict). If a ``- `` item
    # arrives first, the placeholder becomes a list instead.
    lazy: tuple[int, dict, str, dict] | None = None
    # The list currently being filled: (key_indent, items).
    current_list: tuple[int, list] | None = None
    # The dict of the list item currently being filled: (item_indent, dict).
    item: tuple[int, dict] | None = None

    def close_lazy_as_dict() -> None:
        nonlocal lazy
        if lazy is not None:
            key_indent, parent, key, placeholder = lazy
            parent[key] = placeholder
            stack.append((key_indent, placeholder))
            lazy = None

    for raw in text.splitlines():
        if not raw.strip():
            continue
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))
        if skip_indent is not None:
            # Unlike parse_block_mapping, a ``- `` line at or below the
            # block scalar's key indent *ends* the scalar (it is a new
            # list item or a sibling key), so only deeper lines skip.
            if indent > skip_indent:
                continue
            skip_indent = None

        if stripped.startswith("- "):
            content = stripped[2:].strip()
            if lazy is not None and indent > lazy[0]:
                # First item of this key: the placeholder becomes a list.
                key_indent, parent, key, _placeholder = lazy
                items: list = []
                parent[key] = items
                lazy = None
                current_list = (key_indent, items)
            elif current_list is not None and indent > current_list[0]:
                # Another item of the list already open.
                items = current_list[1]
            else:
                # A list under a key that cannot own one: ignore the line
                # rather than guess (the shared "ignored" rule).
                continue
            if item is not None:
                while stack and stack[-1][0] >= item[0]:
                    stack.pop()
                item = None
            pair = _split_key(content)
            if pair is not None:
                entry: dict = {}
                items.append(entry)
                item = (indent, entry)
                stack.append((indent, entry))
                key, value = pair
                if value is None or value == "":
                    nested: dict = {}
                    entry[key] = nested
                    lazy = (indent + 2, entry, key, nested)
                elif _BLOCK_SCALAR.match(value):
                    skip_indent = indent + 2
                    entry[key] = value
                else:
                    entry[key] = _unquote(value)
            else:
                items.append(_unquote(content))
            continue

        pair = _split_key(stripped)
        if pair is None:
            continue
        key, value = pair
        if lazy is not None and indent <= lazy[0]:
            close_lazy_as_dict()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if item is not None and indent <= item[0]:
            item = None
        if current_list is not None and indent <= current_list[0]:
            current_list = None
        parent = stack[-1][1]
        if value is None or value == "":
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
            lazy = (indent, parent, key, child)
        elif _BLOCK_SCALAR.match(value):
            skip_indent = indent
            parent[key] = value
        else:
            parent[key] = _unquote(value)
    return root
