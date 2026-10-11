"""Guard for docs/reference/MODULE_MAP.md (maintainer-adopted with PR #1004).

The map is a one-row-per-module navigation aid. A second hand-kept inventory
rots unless something fails when it drifts, so this makes the table complete in
both directions: every top-level ``idkmesh/*.py`` module has a row, and every row
points at a module that exists. (``docs/EXECUTABLE_CAPABILITIES.md`` carries the
capability-level inventory and its own guard.)

Class-based on purpose: the documented test counts guard module-level
``test_*`` functions, and this file must not shift them.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_MAP = REPO_ROOT / "docs" / "reference" / "MODULE_MAP.md"
# Links to repository files outside docs/ must be absolute (the Pages site
# cannot resolve ../../), so each row links to the file on GitHub.
ROW = re.compile(
    r"^\| \[`([A-Za-z0-9_]+\.py)`\]\(https://github\.com/MSKazemi/idkmesh/blob/main/idkmesh/([A-Za-z0-9_]+\.py)\)",
    re.MULTILINE,
)


class ModuleMapTests(unittest.TestCase):
    def setUp(self):
        self.rows = ROW.findall(MODULE_MAP.read_text(encoding="utf-8"))
        self.modules = {p.name for p in (REPO_ROOT / "idkmesh").glob("*.py")}

    def test_every_package_module_has_exactly_one_row(self):
        listed = [name for name, _ in self.rows]
        self.assertEqual(sorted(set(self.modules) - set(listed)), [], "modules missing a row")
        duplicates = sorted({n for n in listed if listed.count(n) > 1})
        self.assertEqual(duplicates, [], "modules listed more than once")

    def test_every_row_points_at_a_module_that_exists(self):
        for label, target in self.rows:
            with self.subTest(row=label):
                self.assertEqual(label, target, "link text and target must agree")
                self.assertIn(target, self.modules)


if __name__ == "__main__":
    unittest.main()
