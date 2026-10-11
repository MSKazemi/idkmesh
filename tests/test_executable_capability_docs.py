"""Drift guards for the human executable-capability reference."""

from __future__ import annotations

import argparse
from pathlib import Path
import unittest

from idkmesh.api_client import ControlTowerClient
from idkmesh.cli import build_parser
from idkmesh.control_tower_api import status_document


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "EXECUTABLE_CAPABILITIES.md"


def _command_paths(parser: argparse.ArgumentParser, prefix=()):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in sorted(action.choices.items()):
                path = (*prefix, name)
                yield path
                yield from _command_paths(child, path)


class ExecutableCapabilityDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_every_recursive_cli_command_is_documented(self):
        paths = list(_command_paths(build_parser()))
        self.assertGreaterEqual(len(paths), 30)
        for path in paths:
            marker = "`idkmesh " + " ".join(path) + "`"
            with self.subTest(command=" ".join(path)):
                self.assertIn(marker, self.text)

    def test_every_control_tower_discovery_endpoint_is_documented(self):
        endpoints = status_document()["endpoints"]
        self.assertGreaterEqual(len(endpoints), 15)
        for name, endpoint in sorted(endpoints.items()):
            with self.subTest(endpoint=name):
                self.assertIn(f"`{endpoint}`", self.text)

    def test_every_public_control_tower_client_method_is_documented(self):
        methods = sorted(
            name
            for name, value in ControlTowerClient.__dict__.items()
            if not name.startswith("_") and callable(value)
        )
        self.assertGreaterEqual(len(methods), 10)
        for name in methods:
            with self.subTest(method=name):
                self.assertIn(f"`ControlTowerClient.{name}()`", self.text)

    def test_every_top_level_package_module_is_in_the_inventory(self):
        modules = sorted(
            path
            for path in (ROOT / "idkmesh").glob("*.py")
            if path.name != "__init__.py"
        )
        self.assertGreaterEqual(len(modules), 80)
        for path in modules:
            marker = f"`idkmesh/{path.name}`"
            with self.subTest(module=path.name):
                self.assertIn(marker, self.text)


if __name__ == "__main__":
    unittest.main()
