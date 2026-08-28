import json
import unittest
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # Generic dependency-light suites may omit Phase 0 extras.
    Draft202012Validator = None

from tools.idkgraph_repository_mapping import build_repository_graph, serialize_graph


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "idkgraph_repository_mapping"
SCHEMA_PATH = REPO_ROOT / "schemas" / "idkgraph.schema.json"
EXAMPLE_PATH = REPO_ROOT / "examples" / "idkgraph.repository-mapping.example.json"


class RepositoryMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if Draft202012Validator is None:
            cls.validator = None
        else:
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            cls.validator = Draft202012Validator(schema)

    def _assert_schema_valid(self, graph: dict) -> None:
        if self.validator is None:
            self.skipTest("IDKGraph schema validation requires jsonschema")
        errors = sorted(self.validator.iter_errors(graph), key=lambda error: list(error.absolute_path))
        self.assertEqual([error.message for error in errors], [])

    def test_synthetic_fixture_maps_exact_explicit_types_and_relations(self) -> None:
        graph = build_repository_graph(FIXTURE_ROOT)
        nodes = {node["id"]: node for node in graph["nodes"]}
        edges = {(edge["relation"], tuple(edge["sources"]), tuple(edge["targets"])) for edge in graph["hyperedges"]}

        self.assertEqual(
            set(nodes),
            {
                "artifact:examples/input.json",
                "artifact:schemas/demo.schema.json",
                "decision:ADR-0001",
                "doc:995cb72e3f53f7d0b91a66db",
                "work_unit:demo/work",
            },
        )
        self.assertEqual(nodes["doc:995cb72e3f53f7d0b91a66db"]["type"], "document")
        self.assertTrue(nodes["doc:995cb72e3f53f7d0b91a66db"]["attributes"]["t1_identity"])
        self.assertEqual(nodes["decision:ADR-0001"]["type"], "decision")
        self.assertEqual(nodes["work_unit:demo/work"]["attributes"]["work_unit_source_id"], "demo/work")

        self.assertEqual(
            edges,
            {
                ("implements", ("doc:995cb72e3f53f7d0b91a66db",), ("decision:ADR-0001",)),
                ("implements", ("artifact:schemas/demo.schema.json",), ("decision:ADR-0001",)),
                ("requires", ("work_unit:demo/work",), ("artifact:examples/input.json",)),
            },
        )

        semantic_relations = {"supports", "contradicts", "duplicates"}
        self.assertTrue(semantic_relations.isdisjoint({edge["relation"] for edge in graph["hyperedges"]}))
        self.assertFalse(any(node["type"] == "concept" for node in graph["nodes"]))

    def test_mapping_is_byte_deterministic_for_same_tree(self) -> None:
        first = serialize_graph(build_repository_graph(FIXTURE_ROOT))
        second = serialize_graph(build_repository_graph(FIXTURE_ROOT))
        self.assertEqual(first, second)
        json.loads(first)

    def test_traceability_is_present_on_every_mapped_fact(self) -> None:
        graph = build_repository_graph(FIXTURE_ROOT)
        for node in graph["nodes"]:
            self.assertTrue(node["attributes"]["repository_path"])
            self.assertEqual(node["attributes"]["mapping_method"], "deterministic_repository_structure")
            self.assertEqual(node["provenance"]["source"], node["attributes"]["repository_path"])
        for edge in graph["hyperedges"]:
            self.assertTrue(edge["attributes"]["declared_in"])
            self.assertTrue(edge["attributes"]["declared_path"])
            self.assertTrue(edge["attributes"]["mapping_rule"])
            self.assertEqual(edge["provenance"]["source"], edge["attributes"]["declared_in"])

    @unittest.skipIf(Draft202012Validator is None, "IDKGraph schema validation requires jsonschema")
    def test_synthetic_graph_validates_against_current_schema(self) -> None:
        self._assert_schema_valid(build_repository_graph(FIXTURE_ROOT))

    @unittest.skipIf(Draft202012Validator is None, "IDKGraph schema validation requires jsonschema")
    def test_real_repository_example_validates_and_is_reproduced_as_subset(self) -> None:
        example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
        self._assert_schema_valid(example)

        full = build_repository_graph(REPO_ROOT)
        full_nodes = {node["id"]: node for node in full["nodes"]}
        full_edges = {edge["id"]: edge for edge in full["hyperedges"]}

        for expected in example["nodes"]:
            self.assertIn(expected["id"], full_nodes)
            self.assertEqual(full_nodes[expected["id"]], expected)
        for expected in example["hyperedges"]:
            self.assertIn(expected["id"], full_edges)
            self.assertEqual(full_edges[expected["id"]], expected)


if __name__ == "__main__":
    unittest.main()
