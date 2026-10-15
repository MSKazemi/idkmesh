"""C14-H offline Pages-fallback bundle coverage (#609).

Everything runs in-process against temporary directories: no network, no
GitHub call, no workflow.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import re
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from idkmesh import cli
from idkmesh.candidate_reference import GitHubPullRequestCandidateReference
from idkmesh.github_pages_fallback_bundle import (
    MANIFEST_PATH,
    GitHubPagesFallbackError,
    escape_markdown,
    read_github_pages_fallback_dir,
    render_github_pages_fallback_bundle,
    verify_github_pages_fallback_bundle,
    verify_github_pages_fallback_dir,
    write_github_pages_fallback_bundle,
)
from idkmesh.github_pages_site import render_github_pages_site
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


HOSTILE = (
    "<img src=x onerror=alert(1)> [x](javascript:alert(1)) "
    "![i](http://e.test/p.png) `code` **b** _i_ # h | c | @octocat #123 "
    "www.evil.test https://evil.test {{ site }}{% raw %} $math$ \\ ~~s~~ "
    "&amp; &#60;"
)


class _TempCase(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.root = Path(os.path.realpath(holder.name))


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.a = _projection("run-a")
        self.b = _projection("run-b", state="candidate_observed")

    def test_layout_and_sorted_deterministic_output(self):
        files = render_github_pages_fallback_bundle(
            [self.b, self.a], repository=REPO
        )
        again = render_github_pages_fallback_bundle(
            [self.a, self.b], repository=REPO
        )
        self.assertEqual(files, again)
        self.assertEqual(list(files), sorted(files))
        self.assertEqual(
            [
                p
                for p in files
                if not re.fullmatch(r".+/[0-9a-f]{16}\.(md|json)", p)
            ],
            ["MANIFEST.json", "README.md"],
        )
        self.assertEqual(sum(p.startswith("runs/") for p in files), 2)
        self.assertEqual(sum(p.startswith("data/runs/") for p in files), 2)
        self.assertEqual(sum(p.startswith("outage/") for p in files), 2)

    def test_bytes_are_stable_across_repeated_renders(self):
        def digest():
            files = render_github_pages_fallback_bundle(
                [self.a, self.b], repository=REPO
            )
            blob = json.dumps(files, sort_keys=True).encode("utf-8")
            return hashlib.sha256(blob).hexdigest()

        self.assertEqual(digest(), digest())

    def test_input_is_not_mutated(self):
        before = copy.deepcopy(self.a)
        render_github_pages_fallback_bundle([self.a], repository=REPO)
        self.assertEqual(self.a, before)

    def test_empty_input_renders_a_valid_bundle(self):
        files = render_github_pages_fallback_bundle([], repository=REPO)
        self.assertIn("No public runs are published.", files["README.md"])
        self.assertEqual(verify_github_pages_fallback_bundle(files).run_count, 0)

    def test_parity_with_the_pages_renderer(self):
        pages = render_github_pages_site([self.a, self.b], repository=REPO)
        files = render_github_pages_fallback_bundle(
            [self.a, self.b], repository=REPO
        )
        pages_data = {p: t for p, t in pages.items() if p.startswith("data/runs/")}
        bundle_data = {p: t for p, t in files.items() if p.startswith("data/runs/")}
        self.assertEqual(len(pages_data), 2)
        self.assertEqual(pages_data, bundle_data)
        for label in (
            "Total runs",
            "Active runs",
            "Verification debt",
            "Awaiting human decision",
            "Control failure present",
            "Verification disagreement",
        ):
            html_value = re.search(
                rf"<td>{label}</td><td>(\d+)</td>", pages["index.html"]
            ).group(1)
            md_value = re.search(
                rf"\| {label} \| (\d+) \|", files["README.md"]
            ).group(1)
            self.assertEqual(html_value, md_value, label)
        for projection in (self.a, self.b):
            run = projection["run"]
            page = next(
                t
                for p, t in files.items()
                if p.startswith("runs/")
                and f"# Run {escape_markdown(run['run_id'])}\n" in t
            )
            for needle in (
                run["work_unit_digest"],
                run["source_revision"],
                run["state"],
            ):
                self.assertIn(escape_markdown(needle), page)
            self.assertIn("(https://github.com/MSKazemi/idkmesh/pull/7)", page)

    def test_no_active_html_images_or_foreign_links(self):
        files = render_github_pages_fallback_bundle([self.a], repository=REPO)
        blob = "\n".join(t for p, t in files.items() if p.endswith(".md"))
        self.assertNotRegex(blob, r"(?i)<script|<form|<iframe|<img|<input|<a ")
        self.assertNotIn("![", blob)
        allowed = re.compile(
            r"(\.\./)?(runs/[0-9a-f]{16}\.md|README\.md"
            r"|data/runs/[0-9a-f]{16}\.json|outage/[0-9a-f]{16}\.json)"
            r"|https://github\.com/MSKazemi/idkmesh/pull/7"
        )
        links = re.findall(r"\]\(([^)]*)\)", blob)
        self.assertTrue(links)
        for link in links:
            self.assertRegex(link, allowed)
            self.assertIsNotNone(allowed.fullmatch(link), link)

    def test_hostile_identifiers_are_inert_in_markdown(self):
        hostile = copy.deepcopy(self.a)
        hostile["run"]["run_id"] = HOSTILE
        hostile["attempts"][0]["attempt_id"] = HOSTILE
        hostile["attempts"][0]["connector_id"] = HOSTILE
        files = render_github_pages_fallback_bundle([hostile], repository=REPO)
        verify_github_pages_fallback_bundle(files)
        for path, body in files.items():
            if not path.endswith(".md"):
                continue
            for token in (
                "<img",
                "javascript:",
                "http://e",
                "https://evil",
                "www.",
                "@octocat",
                "{{",
                "{%",
                "`code`",
                "**b**",
                "![",
                "[x](",
                "&amp;",
            ):
                self.assertNotIn(token, body, (path, token))
            self.assertEqual(
                len([ln for ln in body.splitlines() if ln.startswith("# ")]),
                1,
                path,
            )
        self.assertIn("&#60;img", files["README.md"])

    def test_multiline_and_control_characters(self):
        multi = copy.deepcopy(self.a)
        multi["run"]["run_id"] = "line1\n# Injected heading\r\n| a | b |"
        files = render_github_pages_fallback_bundle([multi], repository=REPO)
        for path, text in files.items():
            if path.endswith(".md"):
                self.assertNotIn("\n# Injected", text)
                self.assertNotIn("\r", text)
        for bad in ("a\x00b", "a\x1bb", "a\u202eb", "a\u2028b"):
            hostile = copy.deepcopy(self.a)
            hostile["run"]["run_id"] = bad
            with self.subTest(bad=bad), self.assertRaises(GitHubPagesFallbackError):
                render_github_pages_fallback_bundle([hostile], repository=REPO)

    def test_escape_markdown_unit(self):
        self.assertEqual(escape_markdown("a|b"), "a&#124;b")
        self.assertEqual(escape_markdown("a\n\t b"), "a b")
        self.assertEqual(escape_markdown("<>"), "&#60;&#62;")
        self.assertEqual(escape_markdown(7), "7")

    def test_fail_closed_on_bad_input(self):
        with self.assertRaises(GitHubPagesFallbackError):
            render_github_pages_fallback_bundle([self.a], repository="not a repo")
        with self.assertRaises(GitHubPagesFallbackError):
            render_github_pages_fallback_bundle([self.a], repository="other/repo")
        with self.assertRaises(GitHubPagesFallbackError):
            render_github_pages_fallback_bundle([self.a, self.a], repository=REPO)
        with self.assertRaises(GitHubPagesFallbackError):
            render_github_pages_fallback_bundle([{"kind": "nope"}], repository=REPO)
        with self.assertRaises(GitHubPagesFallbackError):
            render_github_pages_fallback_bundle(["x"], repository=REPO)
        leaked = copy.deepcopy(self.a)
        leaked["run"]["provider_reference"] = "private-provider-session"
        with self.assertRaises(GitHubPagesFallbackError):
            render_github_pages_fallback_bundle([leaked], repository=REPO)
        foreign = copy.deepcopy(self.a)
        foreign["attempts"][0]["candidate"]["url"] = "https://evil.test/pull/7"
        with self.assertRaises(GitHubPagesFallbackError):
            render_github_pages_fallback_bundle([foreign], repository=REPO)

    def test_authority_claims_are_all_false(self):
        files = render_github_pages_fallback_bundle([self.a], repository=REPO)
        manifest = json.loads(files[MANIFEST_PATH])
        self.assertTrue(manifest["claims"])
        self.assertFalse(any(manifest["claims"].values()))
        outage = [t for p, t in files.items() if p.startswith("outage/")]
        self.assertEqual(len(outage), 1)
        data = json.loads(outage[0])
        self.assertEqual(data["canonical_evidence_availability"], "unverified")
        self.assertFalse(data["verification_authority"])


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.files = render_github_pages_fallback_bundle(
            [_projection("run-a"), _projection("run-b", state="candidate_observed")],
            repository=REPO,
        )

    def test_every_digest_is_correct_and_verified(self):
        manifest = json.loads(self.files[MANIFEST_PATH])
        self.assertEqual(
            [e["path"] for e in manifest["files"]],
            sorted(p for p in self.files if p != MANIFEST_PATH),
        )
        for entry in manifest["files"]:
            data = self.files[entry["path"]].encode("utf-8")
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(entry["size_bytes"], len(data))
        report = verify_github_pages_fallback_bundle(self.files)
        self.assertEqual(report.run_count, 2)
        self.assertEqual(report.repository, REPO)

    def test_tampered_file_is_detected_by_digest(self):
        for path in self.files:
            if path == MANIFEST_PATH:
                continue
            tampered = dict(self.files)
            tampered[path] = tampered[path] + " "
            with self.subTest(path=path):
                with self.assertRaisesRegex(GitHubPagesFallbackError, "mismatch"):
                    verify_github_pages_fallback_bundle(tampered)

    def test_recomputed_manifest_does_not_hide_an_edit(self):
        edited = dict(self.files)
        path = "README.md"
        edited[path] = edited[path] + "\n<script>alert(1)</script>\n"
        manifest = json.loads(edited[MANIFEST_PATH])
        for entry in manifest["files"]:
            if entry["path"] == path:
                data = edited[path].encode("utf-8")
                entry["size_bytes"] = len(data)
                entry["sha256"] = hashlib.sha256(data).hexdigest()
        edited[MANIFEST_PATH] = json.dumps(manifest, sort_keys=True) + "\n"
        with self.assertRaisesRegex(GitHubPagesFallbackError, "fresh render"):
            verify_github_pages_fallback_bundle(edited)

    def test_missing_extra_and_manifest_corruption_fail_closed(self):
        missing = {k: v for k, v in self.files.items() if k != "README.md"}
        with self.assertRaises(GitHubPagesFallbackError):
            verify_github_pages_fallback_bundle(missing)
        no_manifest = {k: v for k, v in self.files.items() if k != MANIFEST_PATH}
        with self.assertRaisesRegex(GitHubPagesFallbackError, "MANIFEST"):
            verify_github_pages_fallback_bundle(no_manifest)
        with self.assertRaisesRegex(GitHubPagesFallbackError, "unexpected file"):
            verify_github_pages_fallback_bundle({**self.files, "extra.txt": "x"})
        with self.assertRaisesRegex(GitHubPagesFallbackError, "unlisted"):
            verify_github_pages_fallback_bundle(
                {**self.files, "runs/0123456789abcdef.md": "x"}
            )
        manifest = json.loads(self.files[MANIFEST_PATH])
        mutations = {
            "claims": lambda m: m["claims"].update(signed=True),
            "field": lambda m: m.update(extra=1),
            "kind": lambda m: m.update(kind="other"),
            "sha": lambda m: m["files"][0].update(sha256="A" * 64),
            "size": lambda m: m["files"][0].update(size_bytes=True),
            "dup": lambda m: m["files"].append(dict(m["files"][0])),
            "self": lambda m: m["files"].append(
                {"path": MANIFEST_PATH, "size_bytes": 1, "sha256": "0" * 64}
            ),
            "count": lambda m: m.update(run_count=99),
        }
        for name, mutate in mutations.items():
            broken = copy.deepcopy(manifest)
            mutate(broken)
            with self.subTest(name):
                with self.assertRaises(GitHubPagesFallbackError):
                    verify_github_pages_fallback_bundle(
                        {**self.files, MANIFEST_PATH: json.dumps(broken) + "\n"}
                    )
        for text in ("not json", '{"a":1,"a":2}', "NaN", "[]"):
            with self.subTest(text=text), self.assertRaises(GitHubPagesFallbackError):
                verify_github_pages_fallback_bundle(
                    {**self.files, MANIFEST_PATH: text}
                )

    def test_hostile_paths_in_a_file_map_are_refused(self):
        for path in (
            "../x.md",
            "/abs.md",
            "a/../b.md",
            "a\\b.md",
            "runs/./x.md",
            "C:/x",
        ):
            with self.subTest(path=path):
                with self.assertRaises(GitHubPagesFallbackError):
                    verify_github_pages_fallback_bundle({**self.files, path: "x"})


class WriterTests(_TempCase):
    def setUp(self):
        super().setUp()
        self.files = render_github_pages_fallback_bundle(
            [_projection("run-a")], repository=REPO
        )

    def tree(self, directory: Path) -> dict[str, bytes]:
        return {
            p.relative_to(directory).as_posix(): p.read_bytes()
            for p in sorted(directory.rglob("*"))
            if p.is_file()
        }

    def test_writes_exact_bytes_and_round_trips_verification(self):
        out = self.root / "bundle"
        report = write_github_pages_fallback_bundle(self.files, out)
        self.assertEqual(
            self.tree(out), {k: v.encode("utf-8") for k, v in self.files.items()}
        )
        self.assertEqual([p.name for p in self.root.iterdir()], ["bundle"])
        self.assertEqual(verify_github_pages_fallback_dir(out), report)

    def test_empty_existing_directory_is_accepted(self):
        out = self.root / "bundle"
        out.mkdir()
        write_github_pages_fallback_bundle(self.files, out)
        self.assertEqual(verify_github_pages_fallback_dir(out).run_count, 1)

    def test_non_empty_or_non_directory_targets_are_never_replaced(self):
        out = self.root / "bundle"
        out.mkdir()
        (out / "keep.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(GitHubPagesFallbackError, "not empty"):
            write_github_pages_fallback_bundle(self.files, out)
        self.assertEqual((out / "keep.txt").read_text(encoding="utf-8"), "keep")
        regular = self.root / "file"
        regular.write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(GitHubPagesFallbackError, "not a directory"):
            write_github_pages_fallback_bundle(self.files, regular)

    def test_symlink_target_and_missing_parent_are_refused(self):
        real = self.root / "real"
        real.mkdir()
        link = self.root / "link"
        os.symlink(real, link)
        with self.assertRaisesRegex(GitHubPagesFallbackError, "symlink"):
            write_github_pages_fallback_bundle(self.files, link)
        self.assertEqual(list(real.iterdir()), [])
        with self.assertRaisesRegex(GitHubPagesFallbackError, "parent"):
            write_github_pages_fallback_bundle(self.files, self.root / "no" / "b")
        for bad in ("..", "."):
            with self.subTest(bad=bad), self.assertRaises(GitHubPagesFallbackError):
                write_github_pages_fallback_bundle(self.files, self.root / bad)

    def test_traversal_in_file_map_writes_nothing(self):
        hostile = {**self.files, "../escape.md": "x"}
        with self.assertRaises(GitHubPagesFallbackError):
            write_github_pages_fallback_bundle(hostile, self.root / "bundle")
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertFalse((self.root.parent / "escape.md").exists())

    def test_unverifiable_bundle_is_not_written(self):
        tampered = dict(self.files)
        tampered["README.md"] += "x"
        with self.assertRaises(GitHubPagesFallbackError):
            write_github_pages_fallback_bundle(tampered, self.root / "bundle")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_dir_verification_detects_tamper_symlink_and_extras(self):
        out = self.root / "bundle"
        write_github_pages_fallback_bundle(self.files, out)
        readme = out / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8") + "x", encoding="utf-8"
        )
        with self.assertRaisesRegex(GitHubPagesFallbackError, "mismatch"):
            verify_github_pages_fallback_dir(out)
        readme.write_text(self.files["README.md"], encoding="utf-8")
        verify_github_pages_fallback_dir(out)
        (out / "extra.md").write_text("x", encoding="utf-8")
        with self.assertRaises(GitHubPagesFallbackError):
            verify_github_pages_fallback_dir(out)
        (out / "extra.md").unlink()
        outside = self.root / "outside.md"
        outside.write_text("secret", encoding="utf-8")
        readme.unlink()
        os.symlink(outside, readme)
        with self.assertRaisesRegex(GitHubPagesFallbackError, "symlink"):
            read_github_pages_fallback_dir(out)
        with self.assertRaises(GitHubPagesFallbackError):
            verify_github_pages_fallback_dir(self.root / "missing")
        link = self.root / "dirlink"
        os.symlink(out, link)
        with self.assertRaises(GitHubPagesFallbackError):
            read_github_pages_fallback_dir(link)

    def test_write_failure_leaves_no_partial_output(self):
        out = self.root / "bundle"
        real_open = open

        def failing(path, *args, **kwargs):
            if str(path).endswith("MANIFEST.json"):
                raise OSError(28, "No space left on device")
            return real_open(path, *args, **kwargs)

        with mock.patch("builtins.open", failing):
            with self.assertRaisesRegex(GitHubPagesFallbackError, "No space"):
                write_github_pages_fallback_bundle(self.files, out)
        self.assertEqual(list(self.root.iterdir()), [])


class CliTests(_TempCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(args))
        return types.SimpleNamespace(
            returncode=code, stdout=out.getvalue(), stderr=err.getvalue()
        )

    def projection_file(self, name, projection):
        path = self.root / name
        path.write_text(json.dumps(projection), encoding="utf-8")
        return str(path)

    def test_write_then_verify_json(self):
        p1 = self.projection_file("p1.json", _projection("run-a"))
        out = self.root / "fb"
        result = self.run_cli(
            "pages-fallback", "--repository", REPO, "--projection", p1,
            "--out", str(out), "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "idkmesh-github-pages-fallback-write")
        self.assertFalse(payload["uploaded"])
        self.assertFalse(payload["network_access"])
        self.assertTrue(payload["verified"])
        again = self.run_cli("pages-fallback", "--verify", str(out), "--json")
        self.assertEqual(again.returncode, 0, again.stderr)
        verified = json.loads(again.stdout)
        self.assertEqual(verified["kind"], "idkmesh-github-pages-fallback-verify")
        self.assertEqual(verified["files"], payload["files"])
        text = self.run_cli("pages-fallback", "--verify", str(out))
        self.assertEqual(text.returncode, 0)
        self.assertIn("verified", text.stdout)

    def test_cli_is_byte_stable_across_runs(self):
        p1 = self.projection_file("p1.json", _projection("run-a"))
        trees = []
        for name in ("one", "two"):
            out = self.root / name
            result = self.run_cli(
                "pages-fallback", "--repository", REPO, "--projection", p1,
                "--out", str(out),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            trees.append(
                {
                    p.relative_to(out).as_posix(): p.read_bytes()
                    for p in out.rglob("*")
                    if p.is_file()
                }
            )
        self.assertEqual(trees[0], trees[1])

    def test_usage_errors_and_failures_are_nonzero_and_write_nothing(self):
        p1 = self.projection_file("p1.json", _projection("run-a"))
        out = self.root / "fb"
        cases = [
            ("pages-fallback",),
            ("pages-fallback", "--repository", REPO, "--projection", p1),
            ("pages-fallback", "--verify", str(out), "--out", str(out)),
            ("pages-fallback", "--repository", "other/repo", "--projection", p1,
             "--out", str(out)),
            ("pages-fallback", "--repository", REPO, "--projection",
             str(self.root / "missing.json"), "--out", str(out)),
            ("pages-fallback", "--verify", str(self.root / "missing")),
        ]
        for args in cases:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
