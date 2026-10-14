"""C14-G: unsigned in-toto Statement built from a C14-F release record."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from idkmesh import cli
from idkmesh.github_release_provenance import (
    GitHubReleaseArtifact,
    build_github_release_provenance,
)
from idkmesh.github_release_statement import (
    PREDICATE_TYPE,
    STATEMENT_TYPE,
    GitHubReleaseStatementError,
    build_github_release_statement,
    render_github_release_statement_json,
    validate_github_release_statement,
)
from idkmesh.work_unit_binding import canonical_digest
from tests.test_github_release_provenance import (
    DIGEST_B,
    DIGEST_C,
    REPO,
    TARGET,
    _build,
    _projection,
)


def _statement(**overrides):
    return build_github_release_statement(_build(**overrides))


class ReleaseStatementTests(unittest.TestCase):
    def test_subjects_are_the_release_artifacts_with_bare_hex_digests(self):
        statement = _statement()
        self.assertEqual(statement["_type"], STATEMENT_TYPE)
        self.assertEqual(statement["predicateType"], PREDICATE_TYPE)
        self.assertEqual(
            statement["subject"],
            [
                {
                    "name": "idkmesh-0.1.0-py3-none-any.whl",
                    "digest": {"sha256": "c" * 64},
                },
                {
                    "name": "idkmesh-0.1.0.tar.gz",
                    "digest": {"sha256": "b" * 64},
                },
            ],
        )
        for subject in statement["subject"]:
            self.assertEqual(set(subject["digest"]), {"sha256"})
            self.assertFalse(subject["digest"]["sha256"].startswith("sha256:"))

    def test_predicate_embeds_the_record_and_claims_nothing_signed(self):
        record = _build()
        statement = build_github_release_statement(record)
        predicate = statement["predicate"]
        self.assertEqual(predicate["record"], record)
        self.assertEqual(
            predicate["record"]["record_digest"], record["record_digest"]
        )
        self.assertEqual(predicate["signature"]["status"], "unsigned")
        self.assertEqual(
            predicate["claims"],
            {
                "signed": False,
                "attestation_registered": False,
                "slsa_build_provenance": False,
                "subjects_verified_against_build": False,
                "functional_correctness": False,
            },
        )
        self.assertFalse(any(predicate["record"]["authority"].values()))

    def test_statement_does_not_alias_the_input_record(self):
        record = _build()
        statement = build_github_release_statement(record)
        statement["predicate"]["record"]["evidence"].clear()
        self.assertTrue(record["evidence"])

    def test_output_is_deterministic_and_input_order_independent(self):
        a = render_github_release_statement_json(_statement())
        b = render_github_release_statement_json(
            _statement(
                artifacts=[
                    GitHubReleaseArtifact("idkmesh-0.1.0-py3-none-any.whl", DIGEST_C),
                    GitHubReleaseArtifact("idkmesh-0.1.0.tar.gz", DIGEST_B),
                ]
            )
        )
        self.assertEqual(a, b)
        self.assertTrue(a.endswith("\n"))
        self.assertEqual(json.loads(a), _statement())

    def test_no_timestamps_or_private_material(self):
        text = render_github_release_statement_json(_statement())
        for needle in (
            "private-provider-session",
            "/private/tmp",
            "locator",
            '"created_at"',
            '"timestamp"',
            '"issued_at"',
        ):
            self.assertNotIn(needle, text)
        self.assertEqual(
            set(json.loads(text)),
            {"_type", "subject", "predicateType", "predicate"},
        )

    def test_a_statement_without_subjects_is_refused(self):
        with self.assertRaises(GitHubReleaseStatementError):
            build_github_release_statement(_build(artifacts=[]))

    def test_invalid_or_tampered_records_are_refused(self):
        tampered = copy.deepcopy(_build())
        tampered["release"]["tag"] = "v9.9.9"
        with self.assertRaises(GitHubReleaseStatementError):
            build_github_release_statement(tampered)
        with self.assertRaises(GitHubReleaseStatementError):
            build_github_release_statement({"kind": "nope"})
        with self.assertRaises(GitHubReleaseStatementError):
            build_github_release_statement([])  # type: ignore[arg-type]

    def test_a_mutated_statement_cannot_be_validated_or_rendered(self):
        base = _statement()
        mutations = {
            "wrong type": lambda s: s.__setitem__(
                "_type", "https://in-toto.io/Statement/v0.1"
            ),
            "wrong predicate type": lambda s: s.__setitem__(
                "predicateType", "https://example.invalid/x"
            ),
            "extra root key": lambda s: s.__setitem__("signatures", []),
            "extra predicate key": lambda s: s["predicate"].__setitem__("x", 1),
            "signed status": lambda s: s["predicate"]["signature"].__setitem__(
                "status", "signed"
            ),
            "extra signature key": lambda s: s["predicate"]["signature"].__setitem__(
                "sig", "abc"
            ),
            "claim flipped": lambda s: s["predicate"]["claims"].__setitem__(
                "signed", True
            ),
            "verified claim flipped": lambda s: s["predicate"][
                "claims"
            ].__setitem__("subjects_verified_against_build", True),
            "claim not bool": lambda s: s["predicate"]["claims"].__setitem__(
                "signed", 0
            ),
            "subject digest swapped": lambda s: s["subject"][0]["digest"].__setitem__(
                "sha256", "d" * 64
            ),
            "subject name swapped": lambda s: s["subject"][0].__setitem__(
                "name", "evil.whl"
            ),
            "subject dropped": lambda s: s["subject"].pop(),
            "subject reordered": lambda s: s["subject"].reverse(),
            "subject extra digest alg": lambda s: s["subject"][0][
                "digest"
            ].__setitem__("sha512", "0" * 128),
            "subject extra key": lambda s: s["subject"][0].__setitem__("uri", "x"),
            "subject not a list": lambda s: s.__setitem__("subject", {}),
            "no subjects": lambda s: s.__setitem__("subject", []),
            "record digest broken": lambda s: s["predicate"][
                "record"
            ].__setitem__("record_digest", "sha256:" + "0" * 64),
            "record claim flipped": lambda s: s["predicate"]["record"][
                "claims"
            ].__setitem__("attestation_present", True),
            "record authority flipped": lambda s: s["predicate"]["record"][
                "authority"
            ].__setitem__("merge", True),
            "predicate version": lambda s: s["predicate"].__setitem__(
                "schema_version", "9"
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label):
                mutated = copy.deepcopy(base)
                mutate(mutated)
                with self.assertRaises(GitHubReleaseStatementError):
                    validate_github_release_statement(mutated)
                with self.assertRaises(GitHubReleaseStatementError):
                    render_github_release_statement_json(mutated)

    def test_subjects_cannot_diverge_even_with_a_recomputed_record_digest(self):
        statement = _statement()
        record = statement["predicate"]["record"]
        record["artifacts"][0]["digest"] = "sha256:" + "e" * 64
        record["record_digest"] = canonical_digest(
            {k: v for k, v in record.items() if k != "record_digest"}
        )
        with self.assertRaises(GitHubReleaseStatementError):
            validate_github_release_statement(statement)

    def test_non_mapping_is_rejected(self):
        for value in (None, [], "x", 1):
            with self.subTest(value=value):
                with self.assertRaises(GitHubReleaseStatementError):
                    validate_github_release_statement(value)  # type: ignore[arg-type]

    def test_error_is_a_value_error(self):
        self.assertTrue(issubclass(GitHubReleaseStatementError, ValueError))


class ReleaseStatementCliTests(unittest.TestCase):
    def _run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def _base(self):
        return [
            "release-provenance", "--repository", REPO, "--tag", "v0.1.0",
            "--target-commit", TARGET,
        ]

    def test_cli_statement_matches_the_library(self):
        projections = [_projection("run-b")]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run-b.json"
            path.write_text(json.dumps(projections[0]), encoding="utf-8")
            code, out, err = self._run_cli(
                self._base()
                + ["--artifact", f"idkmesh-0.1.0.tar.gz={DIGEST_B}",
                   "--projection", str(path), "--statement"]
            )
        self.assertEqual((code, err), (0, ""))
        record = build_github_release_provenance(
            projections,
            repository=REPO,
            tag="v0.1.0",
            target_commit=TARGET,
            artifacts=[GitHubReleaseArtifact("idkmesh-0.1.0.tar.gz", DIGEST_B)],
        )
        self.assertEqual(
            out,
            render_github_release_statement_json(
                build_github_release_statement(record)
            ),
        )
        self.assertEqual(json.loads(out)["_type"], STATEMENT_TYPE)

    def test_cli_statement_fails_closed(self):
        cases = {
            "no artifacts": ["--statement"],
            "notes and statement": [
                "--artifact", f"a.tar.gz={DIGEST_B}", "--notes", "--statement",
            ],
            "bad digest": ["--artifact", "a.tar.gz=sha256:zz", "--statement"],
        }
        for label, extra in cases.items():
            with self.subTest(label):
                code, out, err = self._run_cli(self._base() + extra)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertTrue(err.startswith("error: "))

    def test_default_output_is_unchanged_without_the_flag(self):
        code, out, err = self._run_cli(
            self._base() + ["--artifact", f"a.tar.gz={DIGEST_B}"]
        )
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(
            json.loads(out)["kind"], "idkmesh-github-release-provenance"
        )


if __name__ == "__main__":
    unittest.main()
