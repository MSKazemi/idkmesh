import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).with_name("github_observatory.py")
spec = importlib.util.spec_from_file_location("github_observatory", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


class PolicyTests(unittest.TestCase):
    def base_snapshot(self):
        return {
            "generated_at": "2026-08-28T14:00:00Z",
            "repository": {"protection": {"default_branch_protected": False, "ruleset_count": 0}},
            "metrics": {"review_capacity": 1.0, "failed_workflow_runs": 0},
            "collaboration": {"items": []},
        }

    def test_unprotected_main_caps_autonomy(self):
        self.assertEqual(mod.autonomy_ceiling(False, 0), 1)
        self.assertEqual(mod.autonomy_ceiling(True, 1), 2)

    def test_unprotected_main_generates_constitutional_guard(self):
        candidates = mod.build_candidates(self.base_snapshot())
        guard = next(c for c in candidates if c["id"] == "guard-default-branch")
        self.assertEqual(guard["risk"], "constitutional")
        self.assertEqual(guard["actuator"], "manual-admin-change")

    def test_discussion_requires_independent_authors(self):
        snapshot = self.base_snapshot()
        snapshot["repository"]["protection"] = {"default_branch_protected": True, "ruleset_count": 1}
        snapshot["collaboration"]["items"] = [{
            "number": 7,
            "title": "Example",
            "state": "open",
            "is_pull_request": False,
            "url": "https://example.invalid/7",
            "comment_count": 6,
            "distinct_comment_authors": 1,
            "created_at": "2026-08-20T00:00:00Z",
        }]
        ids = {c["id"] for c in mod.build_candidates(snapshot)}
        self.assertNotIn("synthesize-issue-7", ids)
        snapshot["collaboration"]["items"][0]["distinct_comment_authors"] = 2
        ids = {c["id"] for c in mod.build_candidates(snapshot)}
        self.assertIn("synthesize-issue-7", ids)

    def test_review_capacity_falls_as_load_rises(self):
        self.assertGreater(mod.review_capacity(1, 0), mod.review_capacity(20, 20))


if __name__ == "__main__":
    unittest.main()
