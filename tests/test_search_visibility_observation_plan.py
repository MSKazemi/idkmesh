"""Cross-engine search/answer observation plans must be balanced and evidence-free."""

from __future__ import annotations

import json
import unittest

from scripts import search_visibility_observation_plan as planner


class SearchVisibilityObservationPlanTests(unittest.TestCase):
    def test_full_plan_is_100_queries_across_eight_surfaces(self) -> None:
        plan = planner.build_plan(sample="full")
        self.assertEqual(8, plan["summary"]["surfaces"])
        self.assertEqual(100, plan["summary"]["queries_per_surface"])
        self.assertEqual(800, plan["summary"]["work_items"])
        self.assertEqual(10, plan["summary"]["clusters"])

    def test_head_plan_is_one_query_per_cluster_per_surface(self) -> None:
        plan = planner.build_plan(sample="heads")
        self.assertEqual(8, plan["summary"]["surfaces"])
        self.assertEqual(10, plan["summary"]["queries_per_surface"])
        self.assertEqual(80, plan["summary"]["work_items"])
        self.assertEqual(
            10,
            len({item["mapped_intent"] for item in plan["items"]}),
        )

    def test_every_item_uses_a_canonical_query_and_target(self) -> None:
        topics = planner.load_json(planner.TOPICS)
        expected = {
            query: (cluster["id"], cluster["url"])
            for cluster in topics["clusters"]
            for query in cluster["queries"]
        }
        plan = planner.build_plan(sample="full")
        self.assertEqual(100, len(expected))
        for item in plan["items"]:
            with self.subTest(plan_id=item["plan_id"]):
                cluster, target = expected[item["mapped_intent"]]
                self.assertEqual(item["mapped_intent"], item["query"])
                self.assertEqual(cluster, item["cluster"])
                self.assertEqual(target, item["target_url"])

    def test_surface_configuration_matches_visibility_schema(self) -> None:
        payload = planner.load_json(planner.SURFACES)
        surfaces = planner.validate_surfaces(payload)
        self.assertEqual(
            {
                "google-web",
                "bing-web",
                "yahoo-web",
                "chatgpt-search",
                "gemini-apps",
                "claude-search",
                "perplexity-answer",
                "copilot-answer",
            },
            {surface["id"] for surface in surfaces},
        )

    def test_single_surface_filter_produces_exactly_100_items(self) -> None:
        plan = planner.build_plan(sample="full", surface_ids={"gemini-apps"})
        self.assertEqual(1, plan["summary"]["surfaces"])
        self.assertEqual(100, plan["summary"]["work_items"])
        self.assertTrue(
            all(item["engine"] == "gemini" for item in plan["items"])
        )

    def test_unknown_surface_fails_closed(self) -> None:
        with self.assertRaisesRegex(planner.ObservationPlanError, "unknown surface"):
            planner.build_plan(sample="full", surface_ids={"made-up-engine"})

    def test_plan_contains_no_fake_observation_result(self) -> None:
        plan = planner.build_plan(sample="heads")
        serialized = json.dumps(plan)
        for forbidden in (
            '"surfaced"',
            '"position"',
            '"citation_url"',
            '"observed_at"',
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)
        self.assertFalse(plan["authority"]["visibility_claim"])
        self.assertFalse(plan["authority"]["ranking_claim"])
        self.assertFalse(plan["authority"]["citation_claim"])

    def test_csv_is_deterministic_and_has_80_head_rows(self) -> None:
        plan = planner.build_plan(sample="heads")
        first = planner.render_csv(plan)
        second = planner.render_csv(plan)
        self.assertEqual(first, second)
        self.assertEqual(81, len(first.strip().splitlines()))
        self.assertTrue(first.startswith("plan_id,engine,product_surface,"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
