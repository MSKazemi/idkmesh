from __future__ import annotations

import json
import unittest

from tools.idkgraph_warning_sample import (
    sample_findings,
    selection_hash,
    serialize_sample,
)


class IDKGraphWarningSampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.findings = [
            {
                "severity": "warning",
                "category": "orphan_document_candidate",
                "source_path": f"docs/example-{index}.md",
                "source_id": f"document:docs/example-{index}.md",
                "line": 0,
                "message": "Document has no deterministic inbound document relation.",
                "evidence": {"producer": "P0-residual-health"},
            }
            for index in range(8)
        ]
        self.findings.append(
            {
                "severity": "warning",
                "category": "accepted_decision_without_document_link",
                "source_path": "docs/decisions/ADR-X.md",
                "source_id": "decision:ADR-X",
                "line": 0,
                "message": "Different warning family.",
            }
        )

    def test_sample_is_invariant_to_input_order(self) -> None:
        first, population_first = sample_findings(
            self.findings,
            category="orphan_document_candidate",
            sample_size=4,
            seed="public-seed-v1",
        )
        second, population_second = sample_findings(
            list(reversed(self.findings)),
            category="orphan_document_candidate",
            sample_size=4,
            seed="public-seed-v1",
        )
        self.assertEqual(population_first, 8)
        self.assertEqual(population_second, 8)
        self.assertEqual(first, second)

    def test_sample_filters_category_and_clips_to_population(self) -> None:
        cohort, population = sample_findings(
            self.findings,
            category="accepted_decision_without_document_link",
            sample_size=15,
            seed="public-seed-v1",
        )
        self.assertEqual(population, 1)
        self.assertEqual(len(cohort), 1)
        self.assertEqual(cohort[0]["source_path"], "docs/decisions/ADR-X.md")
        self.assertEqual(cohort[0]["review"]["classification"], "unreviewed")

    def test_selection_hash_is_stable_for_equivalent_findings(self) -> None:
        original = self.findings[0]
        reordered = json.loads(json.dumps(original, sort_keys=True))
        self.assertEqual(
            selection_hash(original, "public-seed-v1"),
            selection_hash(reordered, "public-seed-v1"),
        )

    def test_invalid_sampling_parameters_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            sample_findings(
                self.findings,
                category="orphan_document_candidate",
                sample_size=0,
                seed="public-seed-v1",
            )
        with self.assertRaises(ValueError):
            sample_findings(self.findings, category="", sample_size=1, seed="public-seed-v1")
        with self.assertRaises(ValueError):
            sample_findings(
                self.findings,
                category="orphan_document_candidate",
                sample_size=1,
                seed="",
            )

    def test_serialization_is_byte_stable(self) -> None:
        cohort, population = sample_findings(
            self.findings,
            category="orphan_document_candidate",
            sample_size=3,
            seed="public-seed-v1",
        )
        payload = {
            "schema_version": "idkgraph-warning-sample-v0.1",
            "population_size": population,
            "candidates": cohort,
        }
        self.assertEqual(serialize_sample(payload), serialize_sample(payload))
        self.assertTrue(serialize_sample(payload).endswith("\n"))


if __name__ == "__main__":
    unittest.main()
