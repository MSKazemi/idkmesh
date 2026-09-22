import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


oracles = _load("e017_oracles", "sim/e017_oracles.py")


def test_draw_inputs_determinism():
    a = oracles.draw_inputs("median_of_list", "small", 10, seed=42)
    b = oracles.draw_inputs("median_of_list", "small", 10, seed=42)
    assert a == b
    assert len(a) == 10


def test_draw_inputs_different_seeds_and_regions():
    res1 = oracles.draw_inputs("running_total", "small", 10, seed=1)
    res2 = oracles.draw_inputs("running_total", "small", 10, seed=2)
    res3 = oracles.draw_inputs("running_total", "large", 10, seed=1)
    assert res1 != res2
    assert res1 != res3


def test_draw_inputs_respects_count():
    for count in (0, 1, 5, 20):
        draws = oracles.draw_inputs("clamp_value", "small", count, seed=100)
        assert len(draws) == count


def test_unknown_problem_raises_key_error():
    with pytest.raises(KeyError):
        oracles.draw_inputs("non_existent_problem", "small", 5, seed=1)


def test_all_registered_generators_and_regions_work():
    for problem in oracles.GENERATORS:
        for region in oracles.REGIONS:
            draws = oracles.draw_inputs(problem, region, 5, seed=123)
            assert len(draws) == 5
            for item in draws:
                assert isinstance(item, tuple)


def test_merge_sorted_and_intersection_sorted_constraints():
    for problem in ("merge_sorted", "intersection_sorted"):
        for region in oracles.REGIONS:
            draws = oracles.draw_inputs(problem, region, 10, seed=777)
            for list1, list2 in draws:
                assert list1 == sorted(list1)
                assert list2 == sorted(list2)


def test_second_largest_constraint():
    for region in oracles.REGIONS:
        draws = oracles.draw_inputs("second_largest", region, 10, seed=888)
        for (xs,) in draws:
            assert len(set(xs)) >= 2


def test_nonempty_list_constraints():
    nonempty_problems = ("median_of_list", "max_subarray_sum", "normalise_scores")
    for problem in nonempty_problems:
        for region in oracles.REGIONS:
            draws = oracles.draw_inputs(problem, region, 10, seed=999)
            for (xs,) in draws:
                assert len(xs) > 0


def test_clamp_value_constraints():
    for region in oracles.REGIONS:
        draws = oracles.draw_inputs("clamp_value", region, 10, seed=555)
        for val, lo, hi in draws:
            assert lo <= hi
            assert isinstance(val, int)


def test_binary_search_constraints():
    for region in oracles.REGIONS:
        draws = oracles.draw_inputs("binary_search", region, 10, seed=444)
        for xs, target in draws:
            assert xs == sorted(xs)
            assert isinstance(target, int)


def test_chunk_list_constraints():
    for region in oracles.REGIONS:
        draws = oracles.draw_inputs("chunk_list", region, 10, seed=333)
        for xs, chunk_size in draws:
            assert isinstance(xs, list)
            assert chunk_size > 0


def test_gen_int_list_helper_options():
    rng = oracles.random.Random(42)
    distinct_list = oracles.gen_int_list(rng, "duplicate", distinct=True)
    assert len(distinct_list) == len(set(distinct_list))

    nonempty_list = oracles.gen_int_list(rng, "tiny", nonempty=True)
    assert len(nonempty_list) >= 1
