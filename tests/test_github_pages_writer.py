"""Writer and ``idkmesh pages-site`` coverage for C14-E (#609).

Every case runs in-process against a temporary directory: the CLI is invoked
through ``cli.main`` and the writer is called directly for the hostile file
maps that the renderer can never produce.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from idkmesh import cli
from idkmesh.candidate_reference import GitHubPullRequestCandidateReference
from idkmesh.github_pages_site import (
    MAX_SITE_BYTES,
    render_github_pages_site,
)
from idkmesh.github_pages_writer import (
    MAX_FILES,
    GitHubPagesWriteError,
    write_github_pages_site,
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
DIGEST_D = "sha256:" + "d" * 64


def _projection(run_id: str, *, state: str = "verification_requested") -> dict:
    candidate = GitHubPullRequestCandidateReference(
        repository=REPO, number=7, head_sha="2" * 40
    )
    run = ProductSpineRun(
        run_id=run_id,
        request_digest=DIGEST_D,
        project_id=REPO,
        work_unit_id="github/mskazemi/idkmesh/issue-609",
        work_unit_version=1,
        work_unit_digest=DIGEST_A,
        source_revision="1" * 40,
        authority_mode="agent_candidate",
        routing_policy_version="routing-v1",
        state=state,
        admitted_connectors=("jules",),
        attempts=(
            AttemptProjection(
                attempt_id="attempt-1",
                order=1,
                connector_id="jules",
                state=state,
                provider_reference="private-provider-session",
                candidate_reference_digest=canonical_digest(candidate.to_dict()),
                result_manifest_digest=DIGEST_B,
                verification_semantic_digest=None,
                error_code=None,
            ),
        ),
        evidence_report_digest=None,
        human_decision_record_digest=None,
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


class _TempDirCase(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        # realpath: a symlinked temp root must not look like a symlinked target
        self.root = Path(os.path.realpath(holder.name))

    def tree(self, directory: Path) -> dict[str, bytes]:
        return {
            str(p.relative_to(directory)): p.read_bytes()
            for p in sorted(directory.rglob("*"))
            if p.is_file()
        }


class WriterTests(_TempDirCase):
    FILES = {
        ".nojekyll": "",
        "index.html": "<p>hi</p>\n",
        "runs/0123456789abcdef.html": "run\n",
    }

    def test_writes_exactly_the_file_map_byte_for_byte(self):
        files = {**self.FILES, "data/runs/0123456789abcdef.json": '{"a":"é"}\n'}
        out = self.root / "site"
        result = write_github_pages_site(files, out)
        self.assertEqual(
            self.tree(out), {k: v.encode("utf-8") for k, v in files.items()}
        )
        self.assertEqual([f[0] for f in result.files], sorted(files))
        self.assertFalse(result.replaced_existing)
        # only the target remains beside it: no staging or backup leftovers
        self.assertEqual([p.name for p in self.root.iterdir()], ["site"])

    def test_line_endings_are_not_translated(self):
        out = self.root / "site"
        write_github_pages_site({"index.html": "a\r\nb\n"}, out)
        self.assertEqual((out / "index.html").read_bytes(), b"a\r\nb\n")

    def test_hostile_paths_are_refused_before_anything_is_written(self):
        hostile = [
            "../escape.html",
            "a/../../escape.html",
            "a/./b.html",
            "/abs/escape.html",
            "C:/escape.html",
            "a\\b.html",
            "a//b.html",
            "trailing/",
            "",
            ".hidden",
            "name\x00.html",
            "dir/.git",
            "x" * 300,
        ]
        for path in hostile:
            with self.subTest(path=path):
                out = self.root / "site"
                with self.assertRaises(GitHubPagesWriteError):
                    write_github_pages_site({"index.html": "ok", path: "x"}, out)
                self.assertEqual(list(self.root.iterdir()), [])
        self.assertFalse((self.root.parent / "escape.html").exists())

    def test_non_string_and_structural_conflicts_are_refused(self):
        cases = [
            ({1: "x"}, "strings"),
            ({"index.html": b"bytes"}, "strings"),
            ({"index.html": "x", "INDEX.html": "y"}, "duplicate"),
            ({"runs": "x", "runs/a.html": "y"}, "conflicts"),
            ({}, "empty"),
        ]
        for files, needle in cases:
            with self.subTest(files=files):
                with self.assertRaisesRegex(GitHubPagesWriteError, needle):
                    write_github_pages_site(files, self.root / "site")
                self.assertEqual(list(self.root.iterdir()), [])

    def test_oversize_and_too_many_files_are_refused(self):
        with self.assertRaises(GitHubPagesWriteError):
            write_github_pages_site(
                {"index.html": "x" * (MAX_SITE_BYTES + 1)}, self.root / "big"
            )
        many = {f"f{i}.html": "" for i in range(MAX_FILES + 1)}
        with self.assertRaises(GitHubPagesWriteError):
            write_github_pages_site(many, self.root / "many")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_symlink_target_is_refused_and_not_written_through(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        link = self.root / "site"
        link.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(GitHubPagesWriteError, "symlink"):
            write_github_pages_site(self.FILES, link, force=True)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_dangling_symlink_target_is_refused(self):
        link = self.root / "site"
        link.symlink_to(self.root / "missing", target_is_directory=True)
        with self.assertRaisesRegex(GitHubPagesWriteError, "symlink"):
            write_github_pages_site(self.FILES, link)
        self.assertFalse((self.root / "missing").exists())

    def test_missing_parent_and_file_target_and_bad_names_are_refused(self):
        with self.assertRaisesRegex(GitHubPagesWriteError, "parent"):
            write_github_pages_site(self.FILES, self.root / "no" / "site")
        occupied = self.root / "file"
        occupied.write_text("keep")
        with self.assertRaisesRegex(GitHubPagesWriteError, "not a directory"):
            write_github_pages_site(self.FILES, occupied, force=True)
        self.assertEqual(occupied.read_text(), "keep")
        for bad in ("..", self.root / ".."):
            with self.subTest(out=str(bad)):
                with self.assertRaises(GitHubPagesWriteError):
                    write_github_pages_site(self.FILES, bad, force=True)

    def test_empty_existing_directory_is_accepted(self):
        out = self.root / "site"
        out.mkdir()
        result = write_github_pages_site(self.FILES, out)
        self.assertTrue(result.replaced_existing)
        self.assertEqual(sorted(self.tree(out)), sorted(self.FILES))

    def test_foreign_non_empty_directory_needs_force_and_is_left_untouched(self):
        out = self.root / "site"
        out.mkdir()
        (out / "notes.txt").write_text("mine")
        with self.assertRaisesRegex(GitHubPagesWriteError, "--force"):
            write_github_pages_site(self.FILES, out)
        self.assertEqual(self.tree(out), {"notes.txt": b"mine"})
        self.assertEqual([p.name for p in self.root.iterdir()], ["site"])
        write_github_pages_site(self.FILES, out, force=True)
        self.assertEqual(sorted(self.tree(out)), sorted(self.FILES))
        self.assertEqual([p.name for p in self.root.iterdir()], ["site"])

    def _generated(self, name="site", runs=("run-1",)):
        out = self.root / name
        files = render_github_pages_site(
            [_projection(r) for r in runs], repository=REPO
        )
        write_github_pages_site(files, out)
        return out, files

    def test_a_previous_generated_site_is_replaced_without_force(self):
        out, _ = self._generated(runs=("run-1", "run-2"))
        files = render_github_pages_site([_projection("run-3")], repository=REPO)
        result = write_github_pages_site(files, out)
        self.assertTrue(result.replaced_existing)
        self.assertEqual(
            self.tree(out), {k: v.encode("utf-8") for k, v in files.items()}
        )

    def test_a_tampered_generated_site_is_treated_as_foreign(self):
        for tamper in ("extra", "symlink", "index", "stray-dir"):
            with self.subTest(tamper=tamper):
                out, _ = self._generated(name=f"site-{tamper}")
                if tamper == "extra":
                    (out / "secret.txt").write_text("x")
                elif tamper == "symlink":
                    (out / "runs" / "link").symlink_to(self.root)
                elif tamper == "index":
                    (out / "index.html").write_text("<p>mine</p>")
                else:
                    (out / "other").mkdir()
                before = self.tree(out)
                new = render_github_pages_site([_projection("r")], repository=REPO)
                with self.assertRaisesRegex(GitHubPagesWriteError, "--force"):
                    write_github_pages_site(new, out)
                self.assertEqual(self.tree(out), before)

    def test_force_refuses_dangerous_targets(self):
        project = self.root / "project"
        (project / ".git").mkdir(parents=True)
        (project / "file.txt").write_text("x")
        with self.assertRaisesRegex(GitHubPagesWriteError, r"\.git"):
            write_github_pages_site(self.FILES, project, force=True)
        inner = project / "inner"
        inner.mkdir()
        (inner / "f").write_text("x")
        with contextlib.chdir(inner):
            for target in (inner, project, self.root):
                with self.subTest(target=str(target)):
                    with self.assertRaisesRegex(GitHubPagesWriteError, "ancestors"):
                        write_github_pages_site(self.FILES, target, force=True)
        self.assertEqual(self.tree(inner), {"f": b"x"})

    def test_failed_swap_restores_the_previous_site(self):
        out, _ = self._generated()
        before = self.tree(out)
        real_rename = os.rename

        def failing(src, dst):
            if ".idkmesh-tmp-" in os.fspath(src):
                raise PermissionError(13, "Permission denied")
            return real_rename(src, dst)

        new = render_github_pages_site([_projection("r2")], repository=REPO)
        with mock.patch("idkmesh.github_pages_writer.os.rename", failing):
            with self.assertRaisesRegex(GitHubPagesWriteError, "Permission"):
                write_github_pages_site(new, out)
        self.assertEqual(self.tree(out), before)
        self.assertEqual([p.name for p in self.root.iterdir()], ["site"])

    def test_failed_write_leaves_no_target_and_no_staging(self):
        real_open = open

        def failing(path, mode="r", *a, **k):
            if mode == "xb" and str(path).endswith("index.html"):
                raise OSError(28, "No space left on device")
            return real_open(path, mode, *a, **k)

        with mock.patch("builtins.open", failing):
            with self.assertRaisesRegex(GitHubPagesWriteError, "No space"):
                write_github_pages_site(self.FILES, self.root / "site")
        self.assertEqual(list(self.root.iterdir()), [])


class PagesSiteCliTests(_TempDirCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(args))
        return types.SimpleNamespace(
            returncode=code, stdout=out.getvalue(), stderr=err.getvalue()
        )

    def write_projection(self, name: str, projection: dict) -> str:
        path = self.root / name
        path.write_text(json.dumps(projection), encoding="utf-8")
        return str(path)

    def setUp(self):
        super().setUp()
        self.first = _projection("run-a")
        self.second = _projection("run-b", state="candidate_observed")
        self.p1 = self.write_projection("p1.json", self.first)
        self.p2 = self.write_projection("p2.json", self.second)
        self.out = self.root / "site"

    def args(self, *extra, projections=None):
        return (
            "pages-site", "--repository", REPO,
            "--projection", *(projections or [self.p1, self.p2]),
            "--out", str(self.out), *extra,
        )

    def test_projections_to_files_on_disk_match_the_renderer_byte_for_byte(self):
        expected = render_github_pages_site(
            [self.first, self.second], repository=REPO
        )
        result = self.run_cli(*self.args())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.tree(self.out),
            {k: v.encode("utf-8") for k, v in expected.items()},
        )
        self.assertIn("published: no", result.stdout)

    def test_json_report_lists_every_file_with_its_digest(self):
        expected = render_github_pages_site(
            [self.first, self.second], repository=REPO
        )
        result = self.run_cli(*self.args("--json"))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "idkmesh-github-pages-site-write")
        self.assertFalse(payload["published"])
        self.assertFalse(payload["github_mutation_performed"])
        self.assertFalse(payload["network_access"])
        self.assertEqual(
            {f["path"]: f["sha256"] for f in payload["files"]},
            {
                k: hashlib.sha256(v.encode("utf-8")).hexdigest()
                for k, v in expected.items()
            },
        )

    def test_rerun_is_idempotent_and_input_order_is_irrelevant(self):
        self.assertEqual(self.run_cli(*self.args()).returncode, 0)
        first = self.tree(self.out)
        result = self.run_cli(*self.args(projections=[self.p2, self.p1]))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.tree(self.out), first)

    def test_invalid_projections_are_refused_before_any_write(self):
        broken_authority = copy.deepcopy(self.first)
        broken_authority["authority"]["merge"] = True
        extra_key = copy.deepcopy(self.first)
        extra_key["run"]["prompt"] = "secret prompt"
        bad_repo = copy.deepcopy(self.first)
        bad_repo["repository"] = "other/repo"
        for label, projection in (
            ("authority", broken_authority),
            ("extra key", extra_key),
            ("repository", bad_repo),
        ):
            with self.subTest(label=label):
                bad = self.write_projection("bad.json", projection)
                result = self.run_cli(*self.args(projections=[self.p1, bad]))
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertTrue(result.stderr.startswith("error: "))
                self.assertFalse(self.out.exists())
                (self.root / "bad.json").unlink()

    def test_unreadable_or_non_json_inputs_are_refused(self):
        dup = self.root / "dup.json"
        dup.write_text('{"kind": "a", "kind": "b"}')
        nan = self.root / "nan.json"
        nan.write_text('{"x": NaN}')
        listing = self.root / "list.json"
        listing.write_text("[]")
        for path in (dup, nan, listing, self.root, self.root / "missing.json"):
            with self.subTest(path=path.name):
                result = self.run_cli(*self.args(projections=[str(path)]))
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertFalse(self.out.exists())

    def test_duplicate_run_ids_are_refused(self):
        result = self.run_cli(*self.args(projections=[self.p1, self.p1]))
        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate", result.stderr)
        self.assertFalse(self.out.exists())

    def test_oversize_projection_count_is_refused_before_reading(self):
        with mock.patch.object(
            cli, "_strict_json_file", side_effect=AssertionError("read")
        ):
            result = self.run_cli(*self.args(projections=[self.p1] * 501))
        self.assertEqual(result.returncode, 2)
        self.assertIn("at most 500", result.stderr)
        self.assertFalse(self.out.exists())

    def test_non_empty_foreign_out_dir_is_refused_unless_forced(self):
        self.out.mkdir()
        (self.out / "keep.txt").write_text("mine")
        result = self.run_cli(*self.args())
        self.assertEqual(result.returncode, 2)
        self.assertIn("--force", result.stderr)
        self.assertEqual(self.tree(self.out), {"keep.txt": b"mine"})
        forced = self.run_cli(*self.args("--force"))
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertNotIn("keep.txt", self.tree(self.out))

    def test_symlink_out_dir_is_refused(self):
        target = self.root / "real"
        target.mkdir()
        self.out.symlink_to(target, target_is_directory=True)
        result = self.run_cli(*self.args("--force"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(list(target.iterdir()), [])

    def test_out_under_a_missing_parent_creates_nothing(self):
        result = self.run_cli(
            "pages-site", "--repository", REPO, "--projection", self.p1,
            "--out", str(self.root / "missing" / ".." / "site"),
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "site").exists())
        self.assertFalse((self.root / "missing").exists())


if __name__ == "__main__":
    unittest.main()
