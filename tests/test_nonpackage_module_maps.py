"""Guard source coverage in the two non-package Python documentation maps.

Class-based tests keep module-level test_* counts unchanged.
This is a source-path drift check, not evidence of runtime correctness.
"""
from __future__ import annotations

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
    def test_maps_have_exact_source_coverage(self):
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
                labels = [target for label, target in pairs]\n                self.assertTrue(all(\n                    label == target or label == Path(target).name\n                    for label, target in pairs\n                ))
                self.assertEqual(sorted(labels), actual)
                self.assertEqual(len(labels), len(set(labels)))
                self.assertTrue(all(label == target for label, target in pairs))


if __name__ == "__main__":
    unittest.main()
