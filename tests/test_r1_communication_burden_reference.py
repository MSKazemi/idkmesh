from __future__ import annotations

import hashlib
import importlib.util
import math
import unittest
from pathlib import Path

from randomness_lab.r1_communication_burden import (
    analyze_communication_burden,
    load_result,
)

# Tier hint for the replay below (about 0.7 CPU-seconds): the unit tier has a hard
# CPU budget, so the full-grid bootstrap runs in the simulation tier instead. Guarded
# the way neighbouring R1 tests guard it, so a bare interpreter still collects the file.
if importlib.util.find_spec("pytest") is not None:
    import pytest

    pytestmark = pytest.mark.sim
else:  # pragma: no cover - the bare-interpreter CI jobs take this path
    pytestmark = ()

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/experiments/r1/coordination-topology-seeds42-51.json.gz"
RESULT = ROOT / "results/experiments/r1/communication-burden-seeds42-51.json.gz"
# The frozen R1 topology artifact this analyzer reads; it must never be edited.
SOURCE_SHA256 = "2815cc524584f72afa6ebde73bb0590ffca5f6db0589a7b4aad37fbed86ce419"


def _same(left: object, right: object, path: str = "") -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        if left.keys() != right.keys():
            return [f"{path}: keys differ"]
        return [d for k in left for d in _same(left[k], right[k], f"{path}/{k}")]
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [f"{path}: length differs"]
        return [d for i, (a, b) in enumerate(zip(left, right)) for d in _same(a, b, f"{path}[{i}]")]
    if isinstance(left, float) or isinstance(right, float):
        return [] if math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12) else [f"{path}: {left} != {right}"]
    return [] if left == right else [f"{path}: {left!r} != {right!r}"]


class CommunicationBurdenReferenceTests(unittest.TestCase):
    def test_frozen_r1_input_is_unchanged(self) -> None:
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), SOURCE_SHA256)

    def test_committed_result_replays_in_value_from_the_frozen_input(self) -> None:
        replay = analyze_communication_burden(load_result(SOURCE))
        self.assertEqual(_same(load_result(RESULT), replay), [])

    def test_committed_result_is_labelled_and_complete(self) -> None:
        committed = load_result(RESULT)
        self.assertEqual(committed["evidence_level"], "synthetic_mechanism")
        self.assertEqual(committed["count_label"], "structural, not measured bytes")
        self.assertEqual(len(committed["groups"]), 27)
        self.assertEqual(len(committed["contrasts_vs_flat"]), 18)
        self.assertIsNone(committed["duplicated_attempts_in_r1_result"]["value"])


if __name__ == "__main__":
    unittest.main()
