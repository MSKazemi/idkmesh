"""Keep non-package Python reference tables complete, accurate, and nonduplicative.

This guards source *navigation*, not correctness or empirical claim quality.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAPS = {
    "RESEARCH_MODULE_MAP.md": ("experiments", "interop", "sim", "randomness_lab"),
    "OPERATIONS_MODULE_MAP.md": ("tools", "scripts"),
}
LINK = re.compile(
    r"\[\x60([^\x60]+\.py)\x60\]"
    r"\(https://github\.com/MSKazemi/idkmesh/blob/main/([^\s)]+\.py)\)"
)


class NonpackageModuleMapTests(unittest.TestCase):
    def test_maps_match_direct_python_sources(self):
        for filename, dirs in MAPS.items():
            with self.subTest(document=filename):
                text = (ROOT / "docs" / "reference" / filename).read_text(
                    encoding="utf-8"
                )
                pairs = LINK.findall(text)
                actual = sorted(
                    path.relative_to(ROOT).as_posix()
                    for dirname in dirs
                    for path in (ROOT / dirname).glob("*.py")
                )
                targets = [target for _, target in pairs]
                self.assertEqual(sorted(targets), actual)
                self.assertEqual([p for p, n in Counter(targets).items() if n > 1], [])
                for label, target in pairs:
                    with self.subTest(module=target):
                        self.assertIn(label, (target, Path(target).name))


if __name__ == "__main__":
    unittest.main()
