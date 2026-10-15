"""C10 (#598): ``idkmesh github-authority-audit`` drives the alignment audit.

The verb is a thin, read-only file front end over
``idkmesh.github_authority_alignment``. These tests pin its exit-code
contract (0 aligned, 1 error finding, 2 unusable input), that it never prints
login text, that its JSON is stable and sorted, and that it writes nothing.
Offline, synthetic numeric actor ids and logins only.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from idkmesh import cli

ROOT = Path(__file__).resolve().parents[1]
ALICE, BOB, BOT = 1001, 1002, 2001
LOGINS = ("zz-alice-login", "zz-bob-login", "zz-bot-login[bot]")


def _binding(actor_id, login, roles, actor_type="human", **extra):
    item = {
        "actor_id": actor_id,
        "login": login,
        "actor_type": actor_type,
        "issuer": "github.com",
        "roles": roles,
        "scopes": [{"tenant_id": "tenant-a", "project_id": "project-main"}],
        "data_clearance": "confidential",
        "identity_revision": "github-identity:1",
        "revoked": False,
        "expires_at_epoch": None,
    }
    item.update(extra)
    return item


def _bindings(*items):
    return {
        "kind": "idkmesh-enterprise-github-identity-binding-table",
        "schema_version": "0.1",
        "bindings": list(items),
    }


def _trusted(*actors, **extra):
    document = {
        "kind": "idkmesh-github-dispatch-trusted-actors",
        "schema_version": "0.1",
        "repository": "MSKazemi/idkmesh",
        "dispatch_labels": ["agent-ready"],
        "trusted_actors": [
            {"actor_id": a, "login": login, "role": role}
            for a, login, role in actors
        ],
    }
    document.update(extra)
    return document


ALIGNED_BINDINGS = _bindings(
    _binding(ALICE, "zz-alice-login", ["owner"]),
    _binding(BOB, "zz-bob-login", ["worker"]),
)
ALIGNED_TRUSTED = _trusted((ALICE, "zz-alice-login", "owner"))


class AuditCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, name, value):
        path = self.dir / name
        text = value if isinstance(value, str) else json.dumps(value)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def run_cli(self, bindings, trusted, *extra):
        argv = [
            "github-authority-audit",
            "--bindings",
            bindings if isinstance(bindings, str) else self.write("b.json", bindings),
            "--trusted-actors",
            trusted if isinstance(trusted, str) else self.write("t.json", trusted),
            *extra,
        ]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        for stream in (out.getvalue(), err.getvalue()):
            for login in LOGINS:
                self.assertNotIn(login, stream)
        return code, out.getvalue(), err.getvalue()

    def codes(self, bindings, trusted, *extra):
        code, out, _ = self.run_cli(bindings, trusted, "--json", *extra)
        report = json.loads(out)
        return code, [(f["actor_id"], f["code"]) for f in report["findings"]]

    # aligned ---------------------------------------------------------------

    def test_aligned_pair_exits_zero_in_text_and_json(self):
        code, out, err = self.run_cli(ALIGNED_BINDINGS, ALIGNED_TRUSTED)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("aligned: yes", out)
        self.assertIn("grants authority: no", out)
        code, out, err = self.run_cli(
            ALIGNED_BINDINGS,
            ALIGNED_TRUSTED,
            "--json",
            "--scope",
            "tenant-a/project-main",
            "--now-epoch",
            "1000",
        )
        self.assertEqual((code, err), (0, ""))
        report = json.loads(out)
        self.assertIs(report["aligned"], True)
        self.assertIs(report["grants_authority"], False)
        self.assertEqual(report["findings"], [])

    def test_warning_only_report_still_exits_zero(self):
        # BOB holds a kernel dispatch role but is not in the trusted list.
        bindings = _bindings(
            _binding(ALICE, "zz-alice-login", ["owner"]),
            _binding(BOB, "zz-bob-login", ["dispatcher"]),
        )
        code, found = self.codes(bindings, ALIGNED_TRUSTED)
        self.assertEqual(code, 0)
        self.assertEqual(found, [(BOB, "kernel_dispatcher_not_dispatch_gate_trusted")])

    # each error class exits 1 ------------------------------------------------

    def test_unbound_actor_exits_one(self):
        bindings = _bindings(_binding(BOB, "zz-bob-login", ["worker"]))
        code, found = self.codes(bindings, ALIGNED_TRUSTED)
        self.assertEqual((code, found), (1, [(ALICE, "dispatch_actor_unbound")]))

    def test_login_mismatch_exits_one(self):
        trusted = _trusted((ALICE, "zz-alice-renamed", "owner"))
        code, found = self.codes(ALIGNED_BINDINGS, trusted)
        self.assertEqual((code, found), (1, [(ALICE, "dispatch_actor_login_mismatch")]))
        code, out, _ = self.run_cli(ALIGNED_BINDINGS, trusted)
        self.assertEqual(code, 1)
        self.assertNotIn("zz-alice-renamed", out)

    def test_kind_mismatch_exits_one(self):
        bindings = _bindings(
            _binding(BOT, "zz-bot-login[bot]", ["dispatcher"], actor_type="github_app")
        )
        trusted = _trusted((BOT, "zz-bot-login[bot]", "maintainer"))
        code, found = self.codes(bindings, trusted)
        self.assertEqual((code, found), (1, [(BOT, "dispatch_actor_kind_mismatch")]))

    def test_revoked_binding_exits_one(self):
        bindings = _bindings(_binding(ALICE, "zz-alice-login", ["owner"], revoked=True))
        code, found = self.codes(bindings, ALIGNED_TRUSTED)
        self.assertEqual((code, found), (1, [(ALICE, "dispatch_actor_binding_revoked")]))

    def test_expiry_needs_explicit_clock_then_exits_one(self):
        bindings = _bindings(
            _binding(ALICE, "zz-alice-login", ["owner"], expires_at_epoch=500)
        )
        self.assertEqual(self.codes(bindings, ALIGNED_TRUSTED), (0, []))
        self.assertEqual(
            self.codes(bindings, ALIGNED_TRUSTED, "--now-epoch", "500"),
            (1, [(ALICE, "dispatch_actor_binding_expired")]),
        )

    def test_scope_missing_exits_one_only_with_scope(self):
        self.assertEqual(self.codes(ALIGNED_BINDINGS, ALIGNED_TRUSTED), (0, []))
        self.assertEqual(
            self.codes(
                ALIGNED_BINDINGS, ALIGNED_TRUSTED, "--scope", "tenant-b/project-other"
            ),
            (1, [(ALICE, "dispatch_actor_scope_missing")]),
        )

    def test_missing_kernel_dispatch_role_exits_one(self):
        bindings = _bindings(_binding(ALICE, "zz-alice-login", ["worker"]))
        code, found = self.codes(bindings, ALIGNED_TRUSTED)
        self.assertEqual(
            (code, found), (1, [(ALICE, "dispatch_actor_lacks_kernel_dispatch_role")])
        )

    def test_error_findings_print_the_report_and_text_names_ids_only(self):
        bindings = _bindings(_binding(BOB, "zz-bob-login", ["worker"]))
        code, out, err = self.run_cli(bindings, ALIGNED_TRUSTED)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("aligned: no", out)
        self.assertIn(f"actor {ALICE} [error] dispatch_actor_unbound", out)

    # unusable input exits 2 ----------------------------------------------------

    def assert_input_error(self, bindings, trusted, *extra):
        code, out, err = self.run_cli(bindings, trusted, *extra)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("error: "), err)
        return err

    def test_missing_and_directory_inputs_exit_two(self):
        self.assert_input_error(str(self.dir / "absent.json"), ALIGNED_TRUSTED)
        self.assert_input_error(ALIGNED_BINDINGS, str(self.dir))

    def test_malformed_json_exits_two(self):
        self.assert_input_error("{not json", ALIGNED_TRUSTED)
        self.assert_input_error(ALIGNED_BINDINGS, "[1, 2]")
        self.assert_input_error(
            ALIGNED_BINDINGS, '{"kind": "a", "kind": "b"}'
        )

    def test_invalid_documents_exit_two(self):
        bad_bindings = dict(ALIGNED_BINDINGS, kind="something-else")
        self.assert_input_error(bad_bindings, ALIGNED_TRUSTED)
        for broken in (
            dict(ALIGNED_TRUSTED, kind="something-else"),
            dict(ALIGNED_TRUSTED, schema_version="9"),
            dict(ALIGNED_TRUSTED, surprise=1),
            dict(ALIGNED_TRUSTED, trusted_actors=[]),
            dict(ALIGNED_TRUSTED, repository="not a repo"),
            dict(ALIGNED_TRUSTED, allowed_roles=["wizard"]),
            dict(ALIGNED_TRUSTED, allowed_roles=[["unhashable"]]),
            _trusted((ALICE, "zz-alice-login", "wizard")),
            _trusted((ALICE, "zz-alice-login", "owner"), (ALICE, "zz-x", "owner")),
            _trusted((0, "zz-alice-login", "owner")),
        ):
            with self.subTest(broken=broken):
                self.assert_input_error(ALIGNED_BINDINGS, broken)

    def test_bad_flags_exit_two(self):
        self.assert_input_error(ALIGNED_BINDINGS, ALIGNED_TRUSTED, "--scope", "no-slash")
        self.assert_input_error(ALIGNED_BINDINGS, ALIGNED_TRUSTED, "--scope", "a/b/c")
        self.assert_input_error(ALIGNED_BINDINGS, ALIGNED_TRUSTED, "--now-epoch=-1")

    def test_input_errors_never_echo_a_login(self):
        # A login accidentally placed in a role field must not be printed by
        # the loader's own message.
        bindings = _bindings(_binding(ALICE, "zz-alice-login", ["zz-alice-login"]))
        err = self.assert_input_error(bindings, ALIGNED_TRUSTED)
        self.assertIn("<login>", err)

    # determinism and read-only ----------------------------------------------------

    def test_json_is_stable_sorted_and_compact(self):
        bindings = _bindings(
            _binding(ALICE, "zz-alice-login", ["worker"]),
            _binding(BOB, "zz-bob-login", ["worker"]),
        )
        trusted = _trusted(
            (BOB, "zz-bob-login", "owner"), (ALICE, "zz-alice-login", "owner")
        )
        _, first, _ = self.run_cli(bindings, trusted, "--json")
        _, second, _ = self.run_cli(bindings, trusted, "--json")
        self.assertEqual(first, second)
        self.assertTrue(first.endswith("}\n"))
        report = json.loads(first)
        self.assertEqual(
            first,
            json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
        )
        ids = [f["actor_id"] for f in report["findings"]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(report["kind"], "idkmesh-github-authority-alignment-report")

    def test_verb_writes_nothing(self):
        b = self.write("b.json", ALIGNED_BINDINGS)
        t = self.write("t.json", ALIGNED_TRUSTED)

        def snapshot():
            return {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.dir.iterdir())
            }

        before = snapshot()
        self.run_cli(b, t, "--json")
        self.run_cli(b, str(self.dir / "absent.json"))
        self.assertEqual(snapshot(), before)

    def test_real_process_exit_codes(self):
        b = self.write("b.json", ALIGNED_BINDINGS)
        t = self.write("t.json", ALIGNED_TRUSTED)
        bad = self.write("bad.json", _bindings(_binding(BOB, "zz-bob-login", ["worker"])))
        env = dict(os.environ, PYTHONPATH=str(ROOT))

        def run(bindings):
            return subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "idkmesh.cli",
                    "github-authority-audit",
                    "--bindings",
                    bindings,
                    "--trusted-actors",
                    t,
                    "--json",
                ],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(self.dir),
                check=False,
            )

        self.assertEqual(run(b).returncode, 0)
        self.assertEqual(run(bad).returncode, 1)
        self.assertEqual(run(str(self.dir / "absent.json")).returncode, 2)


if __name__ == "__main__":
    unittest.main()
