import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.idkgraph_workunit_cycles import check_graph, load_graph, serialize_result


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "idkgraph_workunit_cycles"
SCHEMA_PATH = REPO_ROOT / "schemas" / "idkgraph.schema.json"


class WorkUnitCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(schema)

    def _load(self, name: str) -> dict:
        graph = load_graph(FIXTURE_ROOT / name)
        errors = sorted(self.validator.iter_errors(graph), key=lambda error: list(error.absolute_path))
        self.assertEqual([error.message for error in errors], [], msg=f"schema errors in {name}")
        return graph

    def test_acyclic_workunit_projection_passes(self) -> None:
        result = check_graph(self._load("acyclic.json"))

        self.assertFalse(result["cycle_detected"])
        self.assertIsNone(result["cycle_witness"])
        self.assertEqual(result["projection"]["work_unit_ids"], ["wu:a", "wu:b", "wu:c"])
        self.assertEqual(result["projection"]["edge_count"], 2)
        self.assertEqual(result["projection"]["ignored_hyperedges"], [])

    def test_direct_cycle_returns_stable_closed_witness(self) -> None:
        result = check_graph(self._load("direct-cycle.json"))

        self.assertTrue(result["cycle_detected"])
        self.assertEqual(result["cycle_witness"], ["wu:a", "wu:b", "wu:a"])

    def test_long_cycle_witness_is_canonical_despite_input_order(self) -> None:
        graph = self._load("long-cycle.json")
        expected = check_graph(graph)

        shuffled = copy.deepcopy(graph)
        shuffled["nodes"].reverse()
        shuffled["hyperedges"].reverse()
        observed = check_graph(shuffled)

        self.assertTrue(expected["cycle_detected"])
        self.assertEqual(expected["cycle_witness"], ["wu:a", "wu:b", "wu:c", "wu:a"])
        self.assertEqual(observed, expected)
        self.assertEqual(serialize_result(observed), serialize_result(expected))

    def test_knowledge_cycle_and_mixed_dependency_do_not_create_executable_cycle(self) -> None:
        result = check_graph(self._load("knowledge-cycle.json"))

        self.assertFalse(result["cycle_detected"])
        self.assertEqual(result["projection"]["included_hyperedge_ids"], ["edge:wu-a-b"])
        self.assertEqual(
            result["projection"]["ignored_hyperedges"],
            [
                {"id": "edge:hyp-a-b", "reason": "non_executable_relation"},
                {"id": "edge:hyp-b-a", "reason": "non_executable_relation"},
                {"id": "edge:mixed", "reason": "non_workunit_or_mixed_dependency"},
            ],
        )

    def test_self_dependency_is_a_cycle(self) -> None:
        graph = self._load("acyclic.json")
        graph["hyperedges"].append(
            {
                "id": "edge:a-a",
                "relation": "depends_on",
                "sources": ["wu:a"],
                "targets": ["wu:a"],
            }
        )

        result = check_graph(graph)
        self.assertTrue(result["cycle_detected"])
        self.assertEqual(result["cycle_witness"], ["wu:a", "wu:a"])

    def test_checker_does_not_mutate_input_graph(self) -> None:
        graph = self._load("long-cycle.json")
        before = copy.deepcopy(graph)

        check_graph(graph)

        self.assertEqual(graph, before)


if __name__ == "__main__":
    unittest.main()
