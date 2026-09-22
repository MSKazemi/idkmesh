"""Tests for sim/e016_corpus.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from sim import e016_corpus


@pytest.fixture(scope="module")
def built_tasks():
    return e016_corpus.build()


def test_ground_truth_returns_true_for_matching_candidate():
    source = "def solve(x, y):\n    return x + y"
    tests = [("solve(1, 2)", 3), ("solve(-1, 1)", 0)]
    assert e016_corpus.ground_truth(source, tests) is True


def test_ground_truth_returns_false_for_wrong_value():
    source = "def solve(x, y):\n    return x - y"
    tests = [("solve(1, 2)", 3)]
    assert e016_corpus.ground_truth(source, tests) is False


def test_ground_truth_returns_false_for_wrong_type():
    source = "def solve(x, y):\n    return x // y"
    tests = [("solve(6, 2)", 3.0)]
    assert e016_corpus.ground_truth(source, tests) is False


def test_ground_truth_returns_false_for_exception():
    source = "def solve(x):\n    raise ValueError('error')"
    tests = [("solve(1)", 1)]
    assert e016_corpus.ground_truth(source, tests) is False


def test_ground_truth_returns_false_for_timeout(monkeypatch):
    def mock_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=0.1)

    monkeypatch.setattr(subprocess, "run", mock_run)
    source = "def solve(x):\n    return x"
    tests = [("solve(1)", 1)]
    assert e016_corpus.ground_truth(source, tests) is False


def test_ground_truth_removes_temp_files_on_success_and_failure(monkeypatch):
    created_paths = []
    orig_named_temp = tempfile.NamedTemporaryFile

    def wrapping_named_temp(*args, **kwargs):
        fh = orig_named_temp(*args, **kwargs)
        created_paths.append(fh.name)
        return fh

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", wrapping_named_temp)

    # Success path
    e016_corpus.ground_truth("def solve(x):\n    return x", [("solve(1)", 1)])
    # Failure path
    e016_corpus.ground_truth("def solve(x):\n    return x + 1", [("solve(1)", 1)])
    # Timeout path
    def mock_run_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=0.1)

    monkeypatch.setattr(subprocess, "run", mock_run_timeout)
    e016_corpus.ground_truth("def solve(x):\n    return x", [("solve(1)", 1)])

    assert len(created_paths) == 3
    for p in created_paths:
        assert not Path(p).exists()


def test_build_returns_deterministic_tasks_with_unique_ids(built_tasks):
    tasks2 = e016_corpus.build()
    assert built_tasks == tasks2
    ids = [t["task_id"] for t in built_tasks]
    assert len(ids) == len(set(ids))


def test_build_record_schema_and_types(built_tasks):
    assert len(built_tasks) > 0
    expected_keys = {"task_id", "problem", "variant", "spec", "candidate", "viable"}
    for t in built_tasks:
        assert set(t.keys()) == expected_keys
        assert isinstance(t["task_id"], str)
        assert isinstance(t["problem"], str)
        assert isinstance(t["variant"], str)
        assert isinstance(t["spec"], str)
        assert isinstance(t["candidate"], str)
        assert isinstance(t["viable"], bool)


def test_build_covers_all_declared_problem_variants(built_tasks):
    declared_pairs = {
        (prob, var)
        for prob, _, variants, _ in e016_corpus.PROBLEMS
        for var in variants
    }
    built_pairs = {(t["problem"], t["variant"]) for t in built_tasks}
    assert built_pairs == declared_pairs
    assert len(built_tasks) == len(declared_pairs)


def test_main_cli_creates_jsonl_output(tmp_path, monkeypatch, built_tasks):
    out_file = tmp_path / "out.jsonl"
    monkeypatch.setattr(sys, "argv", ["e016_corpus.py", "--out", str(out_file)])
    ret = e016_corpus.main()
    assert ret == 0
    assert out_file.exists()
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(built_tasks)
    first_record = json.loads(lines[0])
    assert "task_id" in first_record
