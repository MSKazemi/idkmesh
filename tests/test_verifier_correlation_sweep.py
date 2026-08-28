import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "sim" / "run_verifier_correlation_sweep.py"
spec = importlib.util.spec_from_file_location("run_verifier_correlation_sweep", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_parse_correlations():
    assert mod.parse_correlations("0,0.5,1") == [0.0, 0.5, 1.0]


def test_full_correlation_has_zero_panel_disagreement():
    out = mod.correlation_sweep(
        correlations=[0.0, 1.0],
        seeds=3,
        seed_start=0,
        agents=10,
        generations=12,
        change_at=6,
        bins=4,
        verifiers=5,
        verifier_accuracy=0.75,
        verification_quorum=0.5,
    )
    full = out["levels"][1]
    for strategy in ("random", "scalar", "qd"):
        assert full["aggregate"][strategy]["panel_disagreement_rate"]["mean"] == 0.0
