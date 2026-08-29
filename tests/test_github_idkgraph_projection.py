import copy
import json
import random
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.github_idkgraph_projection import project_snapshot, serialize


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/github_idkgraph_snapshot.json"


class GitHubIDKGraphProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_output_validates_against_idkgraph_schema(self) -> None:
        output = project_snapshot(self.snapshot)
        schema = json.loads((ROOT / "schemas/idkgraph.schema.json").read_text())
        errors = list(Draft202012Validator(schema).iter_errors(output["graph"]))
        self.assertEqual([], errors)

    def test_replay_and_input_order_are_deterministic(self) -> None:
        expected = serialize(project_snapshot(self.snapshot))
        shuffled = copy.deepcopy(self.snapshot)
        random.Random(46).shuffle(shuffled["records"])
        self.assertEqual(expected, serialize(project_snapshot(shuffled)))

    def test_untrusted_text_is_hashed_not_copied(self) -> None:
        output = project_snapshot(self.snapshot)
        issue = next(
            node for node in output["graph"]["nodes"]
            if node["id"].endswith(":issue:issue-46")
        )
        self.assertTrue(issue["attributes"]["untrusted_text"])
        self.assertNotIn("Treat this text", serialize(output))
        self.assertEqual(64, len(issue["attributes"]["body_sha256"]))
        self.assertFalse(output["authority"]["execute_untrusted_text"])

    def test_correlated_and_self_evidence_do_not_inflate_count(self) -> None:
        result = project_snapshot(self.snapshot)["independent_verification"]["pr-250"]
        self.assertEqual(2, result["count"])
        self.assertEqual(["ci:unit-tests", "human:reviewer"], result["independence_keys"])

    def test_shared_capacity_is_counted_once(self) -> None:
        observations = project_snapshot(self.snapshot)["capacity_observations"]
        self.assertEqual(1, len(observations))
        self.assertEqual("review:epoch-7", observations[0]["observation_id"])

    def test_conflicting_capacity_fails_closed(self) -> None:
        changed = copy.deepcopy(self.snapshot)
        record = next(row for row in changed["records"] if row["source_id"] == "evolution-capacity")
        record["attributes"]["value"] = 4
        with self.assertRaisesRegex(ValueError, "conflicting capacity"):
            project_snapshot(changed)

    def test_guards_precede_score_and_actuator_is_disabled(self) -> None:
        output = project_snapshot(self.snapshot)
        ranking = output["candidate_ranking"]
        self.assertEqual("github:MSKazemi/idkmesh:evolution_candidate:candidate-safe", ranking[0]["candidate_id"])
        self.assertTrue(ranking[0]["eligible"])
        self.assertFalse(ranking[1]["eligible"])
        self.assertEqual(["protected_main"], ranking[1]["blocked_by"])
        self.assertFalse(output["actuator"]["enabled"])
        self.assertFalse(output["authority"]["github_write"])

    def test_evidence_classes_do_not_treat_attention_as_verification(self) -> None:
        changed = copy.deepcopy(self.snapshot)
        changed["records"].append({
            "source_type": "reaction",
            "source_id": "reaction-1",
            "title": "Thumbs up",
            "url": "https://github.com/MSKazemi/idkmesh/issues/46#reaction-1",
            "timestamp": "2026-08-29T09:21:00Z",
            "actor": "reader",
            "parent_ids": ["pr-250"],
        })
        output = project_snapshot(changed)
        reaction = next(node for node in output["graph"]["nodes"] if node["id"].endswith(":reaction:reaction-1"))
        self.assertEqual("attention", reaction["attributes"]["evidence_class"])
        self.assertEqual(2, output["independent_verification"]["pr-250"]["count"])

    def test_explicit_repository_links_join_the_graphs(self) -> None:
        changed = copy.deepcopy(self.snapshot)
        changed["records"][0]["repository_node_ids"] = ["file:README.md"]
        base = {
            "graph_id": "repository:test",
            "version": "0.1",
            "nodes": [{"id": "file:README.md", "type": "document", "title": "README"}],
            "hyperedges": [],
            "events": [],
        }
        output = project_snapshot(changed, base)
        links = [edge for edge in output["graph"]["hyperedges"] if edge["relation"] == "documents"]
        self.assertEqual(["file:README.md"], links[0]["targets"])

    def test_incomplete_outcome_fails_closed(self) -> None:
        changed = copy.deepcopy(self.snapshot)
        outcome = next(row for row in changed["records"] if row["source_type"] == "outcome")
        del outcome["attributes"]["health_delta"]
        with self.assertRaisesRegex(ValueError, "complete learning record"):
            project_snapshot(changed)

    def test_cli_output_shape_can_be_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "projection.json"
            destination.write_text(serialize(project_snapshot(self.snapshot), pretty=True))
            self.assertIn("graph", json.loads(destination.read_text()))


if __name__ == "__main__":
    unittest.main()
