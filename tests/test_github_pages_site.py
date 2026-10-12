import copy
import re
import unittest

from idkmesh.candidate_reference import GitHubPullRequestCandidateReference
from idkmesh.github_pages_site import (
    GitHubPagesSiteError,
    render_github_pages_site,
)
from idkmesh.github_public_evidence import (
    GitHubPublicEvidencePolicy,
    build_github_public_evidence_projection,
)
from idkmesh.product_spine import AttemptProjection, ProductSpineRun
from idkmesh.work_unit_binding import canonical_digest


REPO = "MSKazemi/idkmesh"
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64
SOURCE = "1" * 40


def _projection(run_id, *, run_state, attempt_state, with_candidate=True):
    candidate = GitHubPullRequestCandidateReference(
        repository=REPO, number=7, head_sha="2" * 40
    )
    verified = attempt_state == "verified"
    decided = run_state == "decided"
    has_evidence = run_state in {"decided", "evidence_ready"}
    run = ProductSpineRun(
        run_id=run_id,
        request_digest=DIGEST_D,
        project_id=REPO,
        work_unit_id="github/mskazemi/idkmesh/issue-609",
        work_unit_version=1,
        work_unit_digest=DIGEST_A,
        source_revision=SOURCE,
        authority_mode="agent_candidate",
        routing_policy_version="routing-v1",
        state=run_state,
        admitted_connectors=("jules",),
        attempts=(
            AttemptProjection(
                attempt_id="attempt-1",
                order=1,
                connector_id="jules",
                state=attempt_state,
                provider_reference="private-provider-session",
                candidate_reference_digest=(
                    canonical_digest(candidate.to_dict())
                    if with_candidate
                    else None
                ),
                result_manifest_digest=(
                    DIGEST_B if attempt_state != "candidate_observed" else None
                ),
                verification_semantic_digest=DIGEST_C if verified else None,
                error_code=(
                    "private-error-code"
                    if attempt_state == "verification_error"
                    else None
                ),
            ),
        ),
        evidence_report_digest=DIGEST_D if has_evidence else None,
        human_decision_record_digest=DIGEST_C if decided else None,
    )
    return build_github_public_evidence_projection(
        run,
        policy=GitHubPublicEvidencePolicy(
            repository=REPO,
            data_classification="public",
            public_projection_enabled=True,
        ),
        candidates={"attempt-1": candidate} if with_candidate else None,
    )


class GitHubPagesSiteTests(unittest.TestCase):
    def setUp(self):
        self.debt = _projection(
            "run-debt", run_state="verification_requested",
            attempt_state="verification_requested",
        )
        self.done = _projection(
            "run-done", run_state="decided", attempt_state="verified"
        )

    def test_site_has_index_run_pages_json_and_nojekyll(self):
        files = render_github_pages_site([self.done, self.debt], repository=REPO)
        self.assertIn(".nojekyll", files)
        self.assertEqual(files[".nojekyll"], "")
        self.assertIn("index.html", files)
        run_pages = [p for p in files if p.startswith("runs/")]
        data_pages = [p for p in files if p.startswith("data/runs/")]
        self.assertEqual(len(run_pages), 2)
        self.assertEqual(len(data_pages), 2)
        self.assertEqual(list(files), sorted(files))

    def test_verification_debt_lists_only_active_unverified_runs(self):
        files = render_github_pages_site([self.done, self.debt], repository=REPO)
        index = files["index.html"]
        debt_section = index.split("<h2>Verification debt</h2>")[1].split(
            "<h2>All runs</h2>"
        )[0]
        self.assertIn("run-debt", debt_section)
        self.assertNotIn("run-done", debt_section)
        active_section = index.split("<h2>Active work</h2>")[1].split(
            "<h2>Verification debt</h2>"
        )[0]
        self.assertIn("run-debt", active_section)
        self.assertNotIn("run-done", active_section)

    def test_every_unverified_attempt_state_is_debt_and_verified_is_not(self):
        for state in (
            "candidate_observed",
            "normalized",
            "verification_requested",
            "verification_error",
        ):
            with self.subTest(state=state):
                projection = _projection(
                    "run-x", run_state=state, attempt_state=state
                )
                index = render_github_pages_site(
                    [projection], repository=REPO
                )["index.html"]
                debt = index.split("<h2>Verification debt</h2>")[1].split(
                    "<h2>All runs</h2>"
                )[0]
                self.assertIn("run-x", debt)
                self.assertNotIn("private-error-code", index)
        verified = _projection(
            "run-v", run_state="evidence_ready", attempt_state="verified"
        )
        index = render_github_pages_site([verified], repository=REPO)[
            "index.html"
        ]
        debt = index.split("<h2>Verification debt</h2>")[1].split(
            "<h2>All runs</h2>"
        )[0]
        self.assertIn("No verification debt.", debt)

    def test_output_is_deterministic_and_order_independent(self):
        first = render_github_pages_site([self.done, self.debt], repository=REPO)
        second = render_github_pages_site([self.debt, self.done], repository=REPO)
        self.assertEqual(first, second)

    def test_pages_are_static_and_carry_no_private_material(self):
        files = render_github_pages_site([self.done, self.debt], repository=REPO)
        blob = "\n".join(files.values())
        self.assertNotIn("private-provider-session", blob)
        self.assertNotRegex(blob, r"(?i)<script|<form|<iframe|<link|<img|<input")
        self.assertNotRegex(blob, r"src=|https?://(?!github\.com/MSKazemi/idkmesh/pull/)")
        self.assertIn("does not accept a candidate", files["index.html"])
        # every external link is the canonical same-repository PR URL
        hrefs = re.findall(r'href="(https?://[^"]+)"', blob)
        self.assertTrue(hrefs)
        for href in hrefs:
            self.assertEqual(href, "https://github.com/MSKazemi/idkmesh/pull/7")

    def test_markup_and_liquid_in_run_id_are_neutralized(self):
        hostile = copy.deepcopy(self.debt)
        hostile["run"]["run_id"] = '<img src=x onerror=alert(1)>{{ site }}{% x %}'
        files = render_github_pages_site([hostile], repository=REPO)
        blob = "\n".join(
            text for path, text in files.items() if path.endswith(".html")
        )
        self.assertNotIn("<img", blob)
        self.assertNotIn("{{", blob)
        self.assertNotIn("{%", blob)
        self.assertIn("&lt;img", blob)

    def test_non_whitelisted_or_mutated_projection_is_rejected(self):
        extra = copy.deepcopy(self.debt)
        extra["run"]["prompt"] = "private prompt"
        with self.assertRaises(GitHubPagesSiteError):
            render_github_pages_site([extra], repository=REPO)
        relaxed = copy.deepcopy(self.debt)
        relaxed["authority"]["merge"] = True
        with self.assertRaises(GitHubPagesSiteError):
            render_github_pages_site([relaxed], repository=REPO)

    def test_unsafe_values_are_rejected_even_with_whitelisted_keys(self):
        bad_url = copy.deepcopy(self.debt)
        bad_url["attempts"][0]["candidate"]["url"] = "javascript:alert(1)"
        with self.assertRaises(GitHubPagesSiteError):
            render_github_pages_site([bad_url], repository=REPO)
        other_repo = copy.deepcopy(self.debt)
        other_repo["attempts"][0]["candidate"]["url"] = (
            "https://github.com/someone/else/pull/7"
        )
        with self.assertRaises(GitHubPagesSiteError):
            render_github_pages_site([other_repo], repository=REPO)
        bad_state = copy.deepcopy(self.debt)
        bad_state["run"]["state"] = "<b>merged</b>"
        with self.assertRaises(GitHubPagesSiteError):
            render_github_pages_site([bad_state], repository=REPO)
        bad_digest = copy.deepcopy(self.debt)
        bad_digest["run"]["work_unit_digest"] = "sha256:zz"
        with self.assertRaises(GitHubPagesSiteError):
            render_github_pages_site([bad_digest], repository=REPO)

    def test_repository_mismatch_and_duplicates_are_rejected(self):
        with self.assertRaises(GitHubPagesSiteError):
            render_github_pages_site([self.debt], repository="other/repo")
        with self.assertRaises(GitHubPagesSiteError):
            render_github_pages_site([self.debt, self.debt], repository=REPO)
        with self.assertRaises(GitHubPagesSiteError):
            render_github_pages_site([self.debt], repository="not-a-repo")

    def test_empty_input_renders_an_explicit_empty_site(self):
        files = render_github_pages_site([], repository=REPO)
        self.assertEqual(sorted(files), [".nojekyll", "index.html"])
        self.assertIn("No public runs are published.", files["index.html"])


if __name__ == "__main__":
    unittest.main()
