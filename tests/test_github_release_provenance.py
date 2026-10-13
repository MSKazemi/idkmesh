"""C14-F (#609): release metadata/provenance record over public-safe evidence.

Everything runs in-process. The integration cases drive the real chain
Product Spine run -> C14-D projection -> release record, and the same
projection through C14-E (``render_github_pages_site`` and ``idkmesh
pages-site``) to prove both surfaces describe the exact same public data.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from idkmesh import cli
from idkmesh.candidate_reference import (
    ArtifactBundleCandidateReference,
    GitHubPullRequestCandidateReference,
)
from idkmesh.github_pages_site import render_github_pages_site
from idkmesh.github_public_evidence import (
    GitHubPublicEvidencePolicy,
    build_github_public_evidence_projection,
)
from idkmesh.github_release_provenance import (
    GitHubReleaseArtifact,
    GitHubReleaseProvenanceError,
    build_github_release_provenance,
    render_github_release_notes,
    render_github_release_provenance_json,
    validate_github_release_provenance,
)
from idkmesh.product_spine import AttemptProjection, ProductSpineRun
from idkmesh.work_unit_binding import canonical_digest


REPO = "MSKazemi/idkmesh"
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64
DIGEST_E = "sha256:" + "e" * 64
SOURCE = "1" * 40
TARGET = "3" * 40


def _projection(run_id, *, bundle=False, state="decided"):
    if bundle:
        candidate = ArtifactBundleCandidateReference(
            digest=DIGEST_E, locator="/private/tmp/bundle.tgz"
        )
    else:
        candidate = GitHubPullRequestCandidateReference(
            repository=REPO, number=7, head_sha="2" * 40
        )
    decided = state == "decided"
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
        state=state,
        admitted_connectors=("jules",),
        attempts=(
            AttemptProjection(
                attempt_id="attempt-1",
                order=1,
                connector_id="jules",
                state="verified" if decided else "verification_requested",
                provider_reference="private-provider-session",
                candidate_reference_digest=canonical_digest(candidate.to_dict()),
                result_manifest_digest=DIGEST_B,
                verification_semantic_digest=DIGEST_C if decided else None,
                error_code=None,
            ),
        ),
        evidence_report_digest=DIGEST_D if decided else None,
        human_decision_record_digest=DIGEST_C if decided else None,
    )
    return build_github_public_evidence_projection(
        run,
        policy=GitHubPublicEvidencePolicy(
            repository=REPO,
            data_classification="public",
            public_projection_enabled=True,
        ),
        candidates={"attempt-1": candidate},
    )


def _build(projections=None, **overrides):
    kwargs = dict(
        repository=REPO,
        tag="v0.1.0",
        target_commit=TARGET,
        artifacts=[
            GitHubReleaseArtifact("idkmesh-0.1.0.tar.gz", DIGEST_B),
            GitHubReleaseArtifact("idkmesh-0.1.0-py3-none-any.whl", DIGEST_C),
        ],
    )
    kwargs.update(overrides)
    if projections is None:
        projections = [_projection("run-b"), _projection("run-a", bundle=True)]
    return build_github_release_provenance(projections, **kwargs)


class ReleaseRecordTests(unittest.TestCase):
    def test_record_binds_tag_commit_artifacts_and_evidence(self):
        record = _build()
        self.assertEqual(record["kind"], "idkmesh-github-release-provenance")
        self.assertEqual(
            record["release"],
            {
                "tag": "v0.1.0",
                "target_commit": TARGET,
                "publication_state": "metadata_only",
            },
        )
        self.assertEqual(
            [a["name"] for a in record["artifacts"]],
            ["idkmesh-0.1.0-py3-none-any.whl", "idkmesh-0.1.0.tar.gz"],
        )
        self.assertEqual([e["run_id"] for e in record["evidence"]], ["run-a", "run-b"])
        by_run = {e["run_id"]: e for e in record["evidence"]}
        self.assertEqual(
            by_run["run-b"]["candidates"],
            [
                {
                    "attempt_id": "attempt-1",
                    "type": "github_pull_request",
                    "number": 7,
                    "head_sha": "2" * 40,
                }
            ],
        )
        self.assertEqual(
            by_run["run-a"]["candidates"],
            [{"attempt_id": "attempt-1", "type": "artifact_bundle", "digest": DIGEST_E}],
        )
        self.assertEqual(by_run["run-b"]["run_source_revision"], SOURCE)
        self.assertEqual(by_run["run-b"]["work_unit_digest"], DIGEST_A)
        validate_github_release_provenance(record)

    def test_claims_and_authority_are_fixed_and_nothing_is_published(self):
        record = _build()
        self.assertTrue(all(v is False for v in record["claims"].values()))
        self.assertTrue(all(v is False for v in record["authority"].values()))
        self.assertEqual(record["attestation"]["status"], "not_claimed")
        self.assertIs(record["attestation"]["artifact_attestation_present"], False)

    def test_output_is_deterministic_and_input_order_independent(self):
        one = [_projection("run-b"), _projection("run-a")]
        two = [_projection("run-a"), _projection("run-b")]
        first = render_github_release_provenance_json(_build(one))
        self.assertEqual(first, render_github_release_provenance_json(_build(two)))
        self.assertEqual(first, render_github_release_provenance_json(_build(one)))
        self.assertTrue(first.endswith("\n"))

    def test_no_timestamps_are_invented(self):
        keys, strings = [], []

        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    keys.append(key)
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
            elif isinstance(value, str):
                strings.append(value)

        walk(json.loads(render_github_release_provenance_json(_build())))
        self.assertTrue(keys)
        for key in keys:
            self.assertFalse(
                key.endswith(("_at", "_time", "_date")) or key in {"timestamp", "time", "date"},
                key,
            )
        iso = re.compile(r"\d{4}-\d{2}-\d{2}")
        self.assertEqual([s for s in strings if iso.search(s)], [])

    def test_private_projection_inputs_never_reach_the_record(self):
        record = _build()
        text = render_github_release_provenance_json(record) + render_github_release_notes(
            record
        )
        for secret in (
            "private-provider-session",
            "/private/tmp/bundle.tgz",
            "jules",
        ):
            self.assertNotIn(secret, text)

    def test_empty_evidence_and_artifacts_are_valid_and_say_so(self):
        record = _build([], artifacts=[])
        validate_github_release_provenance(record)
        notes = render_github_release_notes(record)
        self.assertIn("No artifacts recorded.", notes)
        self.assertIn("No run evidence referenced.", notes)

    def test_projection_digest_is_the_canonical_digest_of_the_projection(self):
        projection = _projection("run-a")
        record = _build([projection])
        self.assertEqual(
            record["evidence"][0]["projection_digest"], canonical_digest(projection)
        )


class ReleaseInputRejectionTests(unittest.TestCase):
    def test_bad_tag_commit_and_repository_are_rejected(self):
        for overrides in (
            {"tag": ""},
            {"tag": "v1..0"},
            {"tag": "v1.0.lock"},
            {"tag": "v 1"},
            {"tag": "-v1"},
            {"tag": "v1\n"},
            {"tag": 5},
            {"target_commit": "main"},
            {"target_commit": "A" * 40},
            {"target_commit": "1" * 41},
            {"target_commit": "1" * 40 + "\n"},
            {"repository": "not a repo"},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(GitHubReleaseProvenanceError):
                    _build([], **overrides)

    def test_artifact_values_are_validated(self):
        for name, digest in (
            ("", DIGEST_A),
            ("../x", DIGEST_A),
            ("a b", DIGEST_A),
            ("a`b", DIGEST_A),
            ("ok", "sha1:" + "a" * 40),
            ("ok", "sha256:" + "A" * 64),
            ("ok", "sha256:" + "a" * 63),
        ):
            with self.subTest(name=name, digest=digest):
                with self.assertRaises(GitHubReleaseProvenanceError):
                    GitHubReleaseArtifact(name, digest)

    def test_duplicate_artifacts_and_runs_are_rejected(self):
        with self.assertRaisesRegex(GitHubReleaseProvenanceError, "duplicate artifact"):
            _build(
                [],
                artifacts=[
                    GitHubReleaseArtifact("A.whl", DIGEST_A),
                    GitHubReleaseArtifact("a.WHL", DIGEST_B),
                ],
            )
        with self.assertRaisesRegex(GitHubReleaseProvenanceError, "duplicate run_id"):
            _build([_projection("run-a"), _projection("run-a")])

    def test_non_artifact_objects_are_rejected(self):
        with self.assertRaisesRegex(GitHubReleaseProvenanceError, "GitHubReleaseArtifact"):
            _build([], artifacts=[("x.whl", DIGEST_A)])

    def test_projections_must_be_valid_public_safe_for_the_repository(self):
        good = _projection("run-a")
        wrong_repo = copy.deepcopy(good)
        wrong_repo["repository"] = "other/repo"
        extra = copy.deepcopy(good)
        extra["run"]["prompt"] = "secret"
        authority = copy.deepcopy(good)
        authority["authority"]["merge"] = True
        bad_state = copy.deepcopy(good)
        bad_state["run"]["state"] = "<script>"
        for label, bad in (
            ("repo", wrong_repo),
            ("extra", extra),
            ("authority", authority),
            ("state", bad_state),
            ("not-a-mapping", [good]),
        ):
            with self.subTest(label=label):
                with self.assertRaises(GitHubReleaseProvenanceError):
                    _build([bad])

    def test_run_ids_that_could_form_markdown_are_rejected(self):
        for run_id in ("run`x", "run [a](http://x)", "run a", "run{{x}}", "run\nx"):
            with self.subTest(run_id=run_id):
                projection = _projection("run-a")
                projection["run"]["run_id"] = run_id
                with self.assertRaises(GitHubReleaseProvenanceError):
                    _build([projection])


class ReleaseRecordValidationTests(unittest.TestCase):
    def setUp(self):
        self.record = _build()

    def _rejects(self, mutate, *, redigest=True):
        """Mutated records must fail.

        By default the digest is recomputed after the mutation, so the check
        under test is the structural one and not the digest mismatch that
        would otherwise mask it.
        """
        record = copy.deepcopy(self.record)
        mutate(record)
        if redigest:
            record["record_digest"] = canonical_digest(
                {k: v for k, v in record.items() if k != "record_digest"}
            )
        with self.assertRaises(GitHubReleaseProvenanceError):
            render_github_release_provenance_json(record)
        with self.assertRaises(GitHubReleaseProvenanceError):
            render_github_release_notes(record)

    def test_every_fixed_claim_authority_and_attestation_flag_is_enforced(self):
        for key in self.record["claims"]:
            with self.subTest(claim=key):
                self._rejects(lambda r, k=key: r["claims"].__setitem__(k, True))
        for key in self.record["authority"]:
            with self.subTest(authority=key):
                self._rejects(lambda r, k=key: r["authority"].__setitem__(k, True))
        self._rejects(
            lambda r: r["attestation"].__setitem__("artifact_attestation_present", True)
        )
        self._rejects(lambda r: r["attestation"].__setitem__("status", "verified"))
        self._rejects(lambda r: r["claims"].__setitem__("release_published", 0))

    def test_publication_state_cannot_claim_a_published_release(self):
        self._rejects(
            lambda r: r["release"].__setitem__("publication_state", "published")
        )

    def test_unknown_keys_anywhere_are_rejected(self):
        self._rejects(lambda r: r.__setitem__("signature", "x"))
        self._rejects(lambda r: r["release"].__setitem__("published_at", "x"))
        self._rejects(lambda r: r["artifacts"][0].__setitem__("url", "x"))
        self._rejects(lambda r: r["evidence"][0].__setitem__("log", "x"))
        self._rejects(lambda r: r["evidence"][0]["candidates"][0].__setitem__("url", "x"))

    def test_tampering_with_content_breaks_the_record_digest(self):
        stale = {"redigest": False}
        self._rejects(
            lambda r: r["release"].__setitem__("target_commit", "4" * 40), **stale
        )
        self._rejects(
            lambda r: r["artifacts"][0].__setitem__("digest", DIGEST_E), **stale
        )
        self._rejects(lambda r: r["evidence"].pop(), **stale)
        self._rejects(lambda r: r.__setitem__("record_digest", DIGEST_A), **stale)

    def test_unsafe_values_are_rejected_even_with_a_recomputed_digest(self):
        last = len(self.record["evidence"]) - 1
        for bad in ("run-z`x`", "run-z [a](http://x)", "run-z{{x}}", "run-z\nx"):
            with self.subTest(run_id=bad):
                self._rejects(lambda r, b=bad: r["evidence"][last].__setitem__("run_id", b))
        for key, bad in (
            ("run_state", "<script>"),
            ("human_decision_status", "recorded `x`"),
            ("work_unit_id", "a b"),
            ("run_source_revision", "main"),
            ("work_unit_digest", "sha256:xyz"),
            ("projection_digest", None),
            ("work_unit_version", True),
        ):
            with self.subTest(field=key):
                self._rejects(lambda r, k=key, b=bad: r["evidence"][0].__setitem__(k, b))
        self.assertEqual(
            self.record["evidence"][1]["candidates"][0]["type"], "github_pull_request"
        )
        for key, bad in (("head_sha", "main"), ("number", 0), ("number", True)):
            with self.subTest(pr_candidate=key, value=bad):
                self._rejects(
                    lambda r, k=key, b=bad: r["evidence"][1]["candidates"][0].__setitem__(k, b)
                )
        self._rejects(
            lambda r: r["evidence"][0]["candidates"][0].__setitem__("digest", "x")
        )
        self._rejects(
            lambda r: r["evidence"][0]["candidates"][0].__setitem__("attempt_id", "a`b")
        )
        self._rejects(lambda r: r["release"].__setitem__("tag", "v1..0"))
        self._rejects(lambda r: r["release"].__setitem__("target_commit", "main"))
        self._rejects(lambda r: r.__setitem__("repository", "not a repo"))

    def test_ordering_and_uniqueness_are_enforced_on_the_record(self):
        self._rejects(lambda r: r["evidence"].reverse())
        self._rejects(lambda r: r["artifacts"].reverse())
        self._rejects(lambda r: r["evidence"].append(copy.deepcopy(r["evidence"][-1])))
        self._rejects(
            lambda r: r["artifacts"].append(copy.deepcopy(r["artifacts"][-1]))
        )

    def test_wrong_kind_or_version_is_rejected(self):
        self._rejects(lambda r: r.__setitem__("kind", "other"))
        self._rejects(lambda r: r.__setitem__("schema_version", "0.2"))


class ReleaseNotesTests(unittest.TestCase):
    def test_notes_list_evidence_and_state_every_non_claim(self):
        notes = render_github_release_notes(_build())
        self.assertTrue(notes.startswith("# Release v0.1.0 (draft metadata, not published)"))
        for needle in (
            f"`{TARGET}`",
            "`idkmesh-0.1.0.tar.gz` | `" + DIGEST_B + "`",
            "`run-a`",
            "`run-b`",
            "No Git tag or GitHub Release has been created",
            "No artifact attestation exists or is claimed",
            "caller-supplied and were not verified",
            "not proven to be contained",
            "does not prove functional correctness",
        ):
            self.assertIn(needle, notes)
        self.assertNotIn("{", notes)
        self.assertNotIn("@", notes)
        self.assertNotIn("<", notes)


class ReleaseIntegrationTests(unittest.TestCase):
    """Projection -> release record, cross-checked against the Pages surface."""

    def setUp(self):
        self.projections = [
            _projection("run-b"),
            _projection("run-a", bundle=True),
            _projection("run-c", state="verification_requested"),
        ]

    def test_release_digests_match_the_published_pages_json(self):
        record = _build(self.projections)
        files = render_github_pages_site(self.projections, repository=REPO)
        published = {
            canonical_digest(json.loads(text))
            for path, text in files.items()
            if path.startswith("data/runs/")
        }
        self.assertEqual(
            {e["projection_digest"] for e in record["evidence"]}, published
        )
        by_run = {e["run_id"]: e for e in record["evidence"]}
        self.assertEqual(by_run["run-c"]["human_decision_status"], "not_recorded")
        self.assertEqual(by_run["run-c"]["run_state"], "verification_requested")
        self.assertIsNone(by_run["run-c"]["evidence_report_digest"])
        self.assertEqual(by_run["run-b"]["human_decision_status"], "recorded")

    def _run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_cli_pages_site_and_release_provenance_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            for projection in self.projections:
                path = root / f"{projection['run']['run_id']}.json"
                path.write_text(json.dumps(projection), encoding="utf-8")
                paths.append(str(path))
            site = root / "site"
            code, _, err = self._run_cli(
                ["pages-site", "--repository", REPO, "--projection", *paths,
                 "--out", str(site)]
            )
            self.assertEqual((code, err), (0, ""))
            code, out, err = self._run_cli(
                [
                    "release-provenance", "--repository", REPO, "--tag", "v0.1.0",
                    "--target-commit", TARGET,
                    "--artifact", f"idkmesh-0.1.0.tar.gz={DIGEST_B}",
                    "--artifact", f"idkmesh-0.1.0-py3-none-any.whl={DIGEST_C}",
                    "--projection", *paths,
                ]
            )
            self.assertEqual((code, err), (0, ""))
            record = json.loads(out)
            self.assertEqual(
                out, render_github_release_provenance_json(_build(self.projections))
            )
            written = {
                canonical_digest(json.loads(p.read_text(encoding="utf-8")))
                for p in (site / "data" / "runs").glob("*.json")
            }
            self.assertEqual(
                {e["projection_digest"] for e in record["evidence"]}, written
            )
            code, notes, err = self._run_cli(
                [
                    "release-provenance", "--repository", REPO, "--tag", "v0.1.0",
                    "--target-commit", TARGET, "--notes", "--projection", *paths,
                ]
            )
            self.assertEqual((code, err), (0, ""))
            self.assertIn("draft metadata, not published", notes)
            self.assertIn(record["evidence"][0]["run_id"], notes)

    def test_cli_fails_closed_with_exit_2_and_no_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            base = ["release-provenance", "--repository", REPO, "--tag", "v1",
                    "--target-commit", TARGET]
            for extra in (
                ["--artifact", "no-separator"],
                ["--artifact", "x=sha256:zz"],
                ["--projection", str(bad)],
                ["--projection", str(Path(tmp) / "missing.json")],
            ):
                with self.subTest(extra=extra):
                    code, out, err = self._run_cli(base + extra)
                    self.assertEqual(code, 2)
                    self.assertEqual(out, "")
                    self.assertTrue(err.startswith("error: "))
            code, out, err = self._run_cli(
                ["release-provenance", "--repository", REPO, "--tag", "v1",
                 "--target-commit", "main"]
            )
            self.assertEqual((code, out), (2, ""))


if __name__ == "__main__":
    unittest.main()
