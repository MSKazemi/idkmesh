import re
import unittest
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_FILE = re.compile(r"^(E\d{3})-")


class ExperimentRegistryTests(unittest.TestCase):
    def test_top_level_experiment_ids_are_unique(self):
        by_id: dict[str, list[str]] = defaultdict(list)
        for path in sorted((ROOT / "experiments").iterdir()):
            if not path.is_file():
                continue
            match = EXPERIMENT_FILE.match(path.name)
            if match:
                by_id[match.group(1)].append(path.name)

        duplicates = {
            experiment_id: names
            for experiment_id, names in by_id.items()
            if len(names) > 1
        }
        self.assertEqual({}, duplicates, f"duplicate experiment IDs: {duplicates}")


if __name__ == "__main__":
    unittest.main()
