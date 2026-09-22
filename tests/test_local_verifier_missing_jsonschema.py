"""Regression test: local_verifier gives an actionable error without jsonschema.

``experiments/local_verifier.py`` performs real JSON Schema validation and
therefore needs the optional ``jsonschema`` dependency (the ``verify`` extra
in ``pyproject.toml``; see
``docs/decisions/ADR-0012-optional-verification-dependency.md``). The
installable ``idkmesh`` CLI package stays dependency-free by design, so a
caller who imports ``local_verifier`` without that extra installed must get a
clear, actionable message naming the install command -- not a bare
``ImportError`` traceback pointing at an internal line number.

This simulates the missing dependency by setting ``sys.modules["jsonschema"]``
to ``None`` (the standard idiom for "this import must fail" -- see
https://docs.python.org/3/library/sys.html#sys.modules) rather than
uninstalling jsonschema from the development environment, which the rest of
this repository's test tree needs (``requirements-phase0.txt``).
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"


class MissingJsonschemaTests(unittest.TestCase):
    def test_import_error_names_the_verify_extra(self) -> None:
        if str(EXPERIMENTS) not in sys.path:
            sys.path.insert(0, str(EXPERIMENTS))
        # Drop any previously-cached local_verifier module so the import
        # below actually re-executes the guarded `from jsonschema import ...`
        # statement instead of returning a cached, already-imported module.
        sys.modules.pop("local_verifier", None)
        try:
            with mock.patch.dict(sys.modules, {"jsonschema": None}):
                with self.assertRaises(ImportError) as ctx:
                    importlib.import_module("local_verifier")
        finally:
            # Leave no partially-initialized module cached for later tests
            # or test ordering in the same process.
            sys.modules.pop("local_verifier", None)

        message = str(ctx.exception)
        self.assertIn("jsonschema", message)
        self.assertIn("verify", message)
        self.assertIn("pip install", message)
        self.assertIn("ADR-0012", message)


if __name__ == "__main__":
    unittest.main()
