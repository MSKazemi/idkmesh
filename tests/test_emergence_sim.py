import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "sim" / "emergence_sim.py"
spec = importlib.util.spec_from_file_location("emergence_sim", MODULE_PATH)
sim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sim
assert spec.loader is not None
spec.loader.exec_module(sim)


def test_random_candidate_respects_bounds_and_budget():
    rng = sim.random.Random(11)
    for _ in range(1000):
        c = sim.Candidate.random(rng)
        assert all(0.0 <= x <= 1.0 for x in c.traits)
        assert sum(c.traits) <= sim.BUDGET + 1e-9


def test_same_seed_is_deterministic():
    a = sim.run("all", seed=5, agents=50, generations=30, change_at=15, bins=6)
    b = sim.run("all", seed=5, agents=50, generations=30, change_at=15, bins=6)
    assert a == b


def test_qd_maintains_multiple_niches():
    result = sim.run("qd", seed=7, agents=80, generations=40, change_at=20, bins=6)
    qd = result["results"][0]
    assert qd["archive_size"] >= 10


def test_qd_beats_fixed_scalar_after_goal_change_for_reference_seed():
    result = sim.run("all", seed=7, agents=120, generations=70, change_at=35, bins=8)
    rows = {r["strategy"]: r for r in result["results"]}
    assert rows["qd"]["post_change_mean"] > rows["scalar"]["post_change_mean"]
