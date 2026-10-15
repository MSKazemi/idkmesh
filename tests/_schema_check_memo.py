"""Test helper: do not re-meta-validate a schema this process already accepted.

``Draft202012Validator.check_schema`` validates a schema against the whole
Draft 2020-12 metaschema, which costs tens to hundreds of milliseconds per call.
Some production code paths call it again every time they load the *same* schema
file (``experiments/local_verifier.py::load_schema`` does, once per validation),
so a test that drives such a path several times pays for the identical,
deterministic meta-check over and over -- the CPU the unit tier's budget counts.

``memoize_check_schema`` swaps the validator class a module imported for a thin
proxy whose ``check_schema`` remembers the schemas that already passed, keyed by
their canonical JSON content. Everything else is delegated untouched:

* the first sight of every distinct schema still runs the real ``check_schema``;
* a schema that fails is never remembered, so it fails again on every call;
* instance validation (``Validator(schema).iter_errors(...)``) is the real class,
  so what a test asserts about *instances* is unchanged;
* the meta-validity of every published schema is asserted for all of them by
  ``tests/test_schema_validity.py``, which does not use this helper.

This file is deliberately not named ``test_*`` so pytest does not collect it.
"""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest import mock


class _MemoizedValidatorClass:
    def __init__(self, real: Any) -> None:
        self._real = real
        self._accepted: set[str] = set()

    def check_schema(self, schema: Any, *args: Any, **kwargs: Any) -> None:
        try:
            key = json.dumps(schema, sort_keys=True)
        except (TypeError, ValueError):
            key = None  # not plain JSON: no safe identity, so always check
        if key is not None and not args and not kwargs and key in self._accepted:
            return
        self._real.check_schema(schema, *args, **kwargs)
        if key is not None and not args and not kwargs:
            self._accepted.add(key)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._real(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


def memoize_check_schema(
    test_class: type[unittest.TestCase], module: Any, name: str = "Draft202012Validator"
) -> None:
    """Patch ``module.<name>`` for the lifetime of ``test_class`` (call in setUpClass)."""

    patcher = mock.patch.object(module, name, _MemoizedValidatorClass(getattr(module, name)))
    patcher.start()
    test_class.addClassCleanup(patcher.stop)
