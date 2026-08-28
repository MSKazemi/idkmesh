import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "sim" / "e015_quorum_frontier.py"
spec = importlib.util.spec_from_file_location("e015_quorum_frontier", MODULE_PATH)
frontier = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = frontier
assert spec.loader is not None
spec.loader.exec_module(frontier)


def _row(verifiers, accuracy, correlation, quorum, false_accept, false_reject):
    return {
        "verifiers": verifiers, "accuracy": accuracy,
        "correlation": correlation, "quorum": quorum,
        "aggregate": {"qd": {
            "false_accept_rate": {"mean": false_accept},
            "false_reject_rate": {"mean": false_reject},
        }},
    }


def test_weighted_error_is_balanced_error_at_unit_cost():
    assert abs(frontier.weighted_error(0.2, 0.4, 1.0) - 0.3) < 1e-12


def test_weighted_error_approaches_false_accept_as_cost_grows():
    assert abs(frontier.weighted_error(0.2, 0.4, 1e6) - 0.2) < 1e-4


def test_cells_by_config_groups_quorums_under_one_key():
    rows = [_row(11, 0.75, 0.0, 0.5, 0.03, 0.03),
            _row(11, 0.75, 0.0, 0.7, 0.001, 0.29)]
    cells = frontier.cells_by_config(rows, "qd")
    assert list(cells) == [(11, 0.75, 0.0)]
    assert sorted(cells[(11, 0.75, 0.0)]) == [0.5, 0.7]


def test_cheap_false_accepts_prefer_simple_majority():
    qmap = {0.5: (0.03, 0.03), 0.7: (0.001, 0.29)}
    q, _ = frontier.best_for_cost(qmap, 1.0)
    assert q == 0.5


def test_expensive_false_accepts_prefer_a_strict_quorum():
    qmap = {0.5: (0.03, 0.03), 0.7: (0.001, 0.29)}
    q, _ = frontier.best_for_cost(qmap, 50.0)
    assert q == 0.7


def test_ties_resolve_to_the_lower_quorum():
    # identical error at both levels: prefer the cheaper-to-satisfy quorum
    qmap = {0.5: (0.02, 0.02), 0.7: (0.02, 0.02)}
    q, _ = frontier.best_for_cost(qmap, 1.0)
    assert q == 0.5


def test_an_interior_quorum_can_win():
    """With three levels the optimum need not be an endpoint."""
    qmap = {0.5: (0.10, 0.01), 0.6: (0.02, 0.02), 0.7: (0.001, 0.30)}
    q, _ = frontier.best_for_cost(qmap, 5.0)
    assert q == 0.6


def test_load_reads_plain_jsonl(tmp_path):
    p = tmp_path / "raw.jsonl"
    p.write_text(json.dumps(_row(3, 0.75, 0.0, 0.5, 0.1, 0.1)) + "\n")
    assert len(frontier.load(str(p))) == 1


def test_load_reads_gzipped_jsonl(tmp_path):
    import gzip
    p = tmp_path / "raw.jsonl.gz"
    with gzip.open(p, "wt") as fh:
        fh.write(json.dumps(_row(3, 0.75, 0.0, 0.5, 0.1, 0.1)) + "\n")
    assert len(frontier.load(str(p))) == 1
