import copy
import json
import unittest

from tools.idkgraph_warning_sample import sample_findings, serialize_sample


class WarningSampleTests(unittest.TestCase):
    def _observatory(self):
        return {
            "schema_version": "idkgraph-observatory-v0.1",
            "source_revision": "fixture:sample",
            "findings": [
                {
                    "severity": "warning",
                    "category": "orphan_document_candidate",
                    "source_id": f"doc:{index}",
                    "source_path": f"docs/note-{index}.md",
                    "line": 0,
                    "message": "candidate",
                }
                for index in range(20)
            ]
            + [
                {
                    "severity": "warning",
                    "category": "accepted_decision_without_document_link",
                    "source_id": "decision:ADR-0001",
                    "source_path": "docs/decisions/ADR-0001-test.md",
                    "line": 0,
                    "message": "decision candidate",
                }
            ],
        }

    def test_fixed_seed_returns_same_sample_independent_of_input_order(self):
        observatory = self._observatory()
        expected = sample_findings(
            observatory,
            category="orphan_document_candidate",
            size=5,
            seed="issue-152-v1",
        )
        reversed_observatory = copy.deepcopy(observatory)
        reversed_observatory["findings"].reverse()
        observed = sample_findings(
            reversed_observatory,
            category="orphan_document_candidate",
            size=5,
            seed="issue-152-v1",
        )
        self.assertEqual(observed, expected)
        self.assertEqual(serialize_sample(observed), serialize_sample(expected))

    def test_sample_is_bounded_and_category_specific(self):
        result = sample_findings(
            self._observatory(),
            category="orphan_document_candidate",
            size=7,
            seed="issue-152-v1",
        )
        self.assertEqual(result["eligible_count"], 20)
        self.assertEqual(result["selected_count"], 7)
        self.assertEqual(len(result["sample"]), 7)
        self.assertTrue(all(item["category"] == "orphan_document_candidate" for item in result["sample"]))
        self.assertTrue(all(len(item["rank_hash"]) == 64 for item in result["sample"]))

    def test_all_small_category_can_be_selected(self):
        result = sample_findings(
            self._observatory(),
            category="accepted_decision_without_document_link",
            size=15,
            seed="issue-152-v1",
        )
        self.assertEqual(result["eligible_count"], 1)
        self.assertEqual(result["selected_count"], 1)
        self.assertEqual(result["sample"][0]["source_id"], "decision:ADR-0001")

    def test_negative_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "size must be >= 0"):
            sample_findings(
                self._observatory(),
                category="orphan_document_candidate",
                size=-1,
                seed="issue-152-v1",
            )

    def test_output_is_json_and_preserves_source_revision(self):
        result = sample_findings(
            self._observatory(),
            category="orphan_document_candidate",
            size=3,
            seed="issue-152-v1",
        )
        decoded = json.loads(serialize_sample(result))
        self.assertEqual(decoded["source_revision"], "fixture:sample")
        self.assertEqual(decoded["selected_count"], 3)


if __name__ == "__main__":
    unittest.main()
