"""E3-E operator check (#670): ``idkmesh break-glass check`` drives main(argv).

The verb is a read-only file front end over the strict grant validator in
``idkmesh.enterprise_break_glass``. These tests pin the exit-code contract
(0 well formed and grantable, 1 refused, 2 unusable input with empty stdout),
that a valid grant is never reported as an authorization, that the clock is
never read, that free text from the document is never echoed, and that the
JSON is stable and sorted. Offline, synthetic ids only. The CLI reads a file,
so each fixture is written (minimum fields, no credential-like key names) to a
temporary directory.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from idkmesh import cli
from idkmesh.enterprise_break_glass import parse_break_glass_grant

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads(
    (ROOT / "examples/enterprise/break-glass-grant.example.json").read_text(
        encoding="utf-8"
    )
)
ISSUED = EXAMPLE["issued_at_epoch"]
EXPIRES = EXAMPLE["expires_at_epoch"]
HOSTILE = "ZZHOSTILE<b>x</b>\x1b[31m"


def _grant(**overrides):
    document = copy.deepcopy(EXAMPLE)
    document.update(overrides)
    return document


class BreakGlassCheckCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # main() would rebuild the argparse tree on every call; the parser is
        # only read, so one instance is shared for the whole class.
        parser = cli.build_parser()
        patcher = mock.patch.object(cli, "build_parser", return_value=parser)
        patcher.start()
        cls.addClassCleanup(patcher.stop)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def write(self, value, name="grant.json"):
        path = self.dir / name
        path.write_text(
            value if isinstance(value, str) else json.dumps(value),
            encoding="utf-8",
        )
        return str(path)

    def run_check(self, value, *extra):
        return self.run_path(self.write(value), *extra)

    def run_path(self, path, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["break-glass", "check", "--grant", path, *extra])
        return code, out.getvalue(), err.getvalue()

    def report(self, value, *extra):
        code, out, err = self.run_check(value, "--json", *extra)
        self.assertEqual(err, "")
        return code, json.loads(out)

    def codes(self, report):
        return [(r["code"], r["path"]) for r in report["reasons"]]

    # well formed ------------------------------------------------------------

    def test_valid_grant_without_now_epoch_exits_zero_window_not_evaluated(self):
        code, report = self.report(EXAMPLE)
        self.assertEqual(code, 0)
        self.assertIs(report["ok"], True)
        self.assertEqual(
            report["window"], {"now_epoch": None, "status": "not_evaluated"}
        )
        self.assertEqual(report["reasons"], [])
        self.assertEqual(
            report["grant_digest"], parse_break_glass_grant(EXAMPLE).digest
        )
        self.assertNotIn("reason", report["grant"])

    def test_valid_grant_is_never_reported_as_an_authorization(self):
        code, report = self.report(EXAMPLE, "--now-epoch", str(ISSUED + 1))
        self.assertEqual(code, 0)
        self.assertEqual(report["window"]["status"], "within")
        self.assertIs(report["is_authorization"], False)
        self.assertIs(report["evaluates_authorization"], False)
        self.assertIs(report["writes_anything"], False)
        code, out, err = self.run_check(EXAMPLE, "--now-epoch", str(ISSUED))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("is authorization: no", out)
        self.assertIn("not an authorization", out)

    def test_json_is_stable_sorted_compact_and_newline_terminated(self):
        args = ("--json", "--now-epoch", str(ISSUED))
        _, first, _ = self.run_check(EXAMPLE, *args)
        _, second, _ = self.run_check(EXAMPLE, *args)
        self.assertEqual(first, second)
        self.assertEqual(
            first,
            json.dumps(json.loads(first), sort_keys=True, separators=(",", ":"))
            + "\n",
        )

    # window -----------------------------------------------------------------

    def test_window_boundaries_use_the_caller_supplied_instant(self):
        cases = (
            (ISSUED - 1, 1, "not_yet_valid", "break_glass_not_yet_valid"),
            (ISSUED, 0, "within", None),
            (EXPIRES - 1, 0, "within", None),
            (EXPIRES, 1, "expired", "break_glass_expired"),
        )
        for now, exit_code, status, reason in cases:
            with self.subTest(now=now):
                code, report = self.report(EXAMPLE, "--now-epoch", str(now))
                self.assertEqual(code, exit_code)
                self.assertEqual(report["window"]["status"], status)
                self.assertEqual(
                    [c for c, _ in self.codes(report)], [reason] if reason else []
                )

    # non-grantable requests ---------------------------------------------------

    def test_every_non_grantable_request_is_refused_with_a_specific_code(self):
        cases = (
            ({"actions": ["manage_policy"]}, "action_not_grantable", "$.actions", "manage_policy"),
            ({"actions": ["audit_export"]}, "action_not_grantable", "$.actions", "audit_export"),
            ({"granted_roles": ["owner"]}, "role_not_grantable", "$.granted_roles", "owner"),
            ({"granted_roles": ["admin"]}, "role_not_grantable", "$.granted_roles", "admin"),
            ({"granted_roles": ["auditor"]}, "role_not_grantable", "$.granted_roles", "auditor"),
            ({"max_risk": "critical"}, "risk_above_ceiling", "$.max_risk", "critical"),
            (
                {"max_data_classification": "restricted"},
                "data_class_above_ceiling",
                "$.max_data_classification",
                "restricted",
            ),
        )
        for overrides, code_name, path, value in cases:
            with self.subTest(overrides=overrides):
                code, report = self.report(
                    _grant(**overrides), "--now-epoch", str(ISSUED)
                )
                self.assertEqual(code, 1)
                self.assertIs(report["ok"], False)
                self.assertIs(report["well_formed"], False)
                self.assertIs(report["requests_non_grantable"], True)
                self.assertIsNone(report["grant_digest"])
                self.assertEqual(
                    report["reasons"],
                    [{"code": code_name, "path": path, "value": value}],
                )

    def test_all_non_grantable_requests_are_reported_together_and_sorted(self):
        document = _grant(
            actions=["manage_policy", "audit_export", "dispatch"],
            granted_roles=["owner", "dispatcher"],
            max_risk="critical",
            max_data_classification="restricted",
        )
        code, report = self.report(document)
        self.assertEqual(code, 1)
        self.assertEqual(
            [(r["code"], r.get("value")) for r in report["reasons"]],
            [
                ("action_not_grantable", "audit_export"),
                ("action_not_grantable", "manage_policy"),
                ("data_class_above_ceiling", "restricted"),
                ("risk_above_ceiling", "critical"),
                ("role_not_grantable", "owner"),
            ],
        )

    def test_non_grantable_request_is_named_even_when_the_document_is_malformed(self):
        document = _grant(actions=["manage_policy"])
        del document["incident_id"]
        code, report = self.report(document)
        self.assertEqual(code, 1)
        self.assertIs(report["requests_non_grantable"], True)
        self.assertEqual(
            sorted(c for c, _ in self.codes(report)),
            ["action_not_grantable", "missing_field"],
        )

    # malformed ----------------------------------------------------------------

    def test_malformed_grants_are_refused_with_the_library_reason_code(self):
        cases = (
            ({"kind": "other"}, "invalid_kind"),
            ({"schema_version": "9"}, "unsupported_version"),
            ({"expires_at_epoch": ISSUED + 5}, "invalid_ttl"),
            ({"expires_at_epoch": ISSUED + 4 * 60 * 60 + 1}, "invalid_ttl"),
            (
                {"approver_principal_id": EXAMPLE["beneficiary_principal_id"]},
                "self_approval_forbidden",
            ),
            ({"reason": "short"}, "invalid_reason"),
            ({"actions": []}, "invalid_collection"),
            ({"actions": ["dispatch", "dispatch"]}, "duplicate_value"),
            ({"scope": {"tenant_id": "tenant-a"}}, "invalid_scope"),
            ({"issued_at_epoch": True}, "invalid_epoch"),
        )
        for overrides, expected in cases:
            with self.subTest(expected=expected, overrides=sorted(overrides)):
                code, report = self.report(_grant(**overrides))
                self.assertEqual(code, 1)
                self.assertIs(report["well_formed"], False)
                self.assertIs(report["requests_non_grantable"], False)
                self.assertIsNone(report["grant"])
                self.assertEqual([c for c, _ in self.codes(report)], [expected])

    def test_unhashable_list_member_is_refused_not_a_traceback(self):
        code, report = self.report(_grant(actions=[["dispatch"]]))
        self.assertEqual(code, 1)
        self.assertEqual(self.codes(report), [("invalid_type", "$")])

    def test_unknown_member_values_are_refused_without_being_echoed(self):
        code, out, err = self.run_check(
            _grant(actions=[HOSTILE], granted_roles=[HOSTILE]), "--json"
        )
        self.assertEqual((code, err), (1, ""))
        self.assertNotIn("ZZHOSTILE", out)
        self.assertEqual(
            self.codes(json.loads(out)),
            [("value_not_grantable", "$.granted_roles")],
        )

    # no free text echo ----------------------------------------------------------

    def test_reason_and_unknown_keys_are_never_echoed(self):
        document = _grant(reason=HOSTILE + " incident text")
        document[HOSTILE] = HOSTILE
        for extra in ((), ("--json",)):
            with self.subTest(extra=extra):
                code, out, err = self.run_check(document, *extra)
                self.assertEqual(code, 1)
                self.assertNotIn("ZZHOSTILE", out + err)
                self.assertNotIn("\x1b", out + err)
        code, report = self.report(document)
        self.assertEqual(self.codes(report), [("unknown_field", "$")])

    def test_valid_reason_text_is_not_printed(self):
        document = _grant(reason="ZZREASONMARK rollback of the failed deploy")
        for extra in ((), ("--json",)):
            code, out, err = self.run_check(document, *extra)
            self.assertEqual((code, err), (0, ""))
            self.assertNotIn("ZZREASONMARK", out)

    # unusable input -------------------------------------------------------------

    def test_unusable_input_exits_two_with_empty_stdout(self):
        marker = "ZZHOSTILEKEY"
        duplicate = '{"%s": 1, "%s": 2}' % (marker, marker)
        cases = (
            (str(self.dir / "missing.json"), ()),
            (str(self.dir), ()),
            (self.write("{not json", "bad.json"), ()),
            (self.write("[]", "list.json"), ()),
            (self.write('{"a": NaN}', "nan.json"), ()),
            (self.write(duplicate, "dup.json"), ()),
            (self.write(EXAMPLE, "ok.json"), ("--now-epoch", "-1")),
        )
        for path, extra in cases:
            with self.subTest(path=Path(path).name, extra=extra):
                code, out, err = self.run_path(path, *extra)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.startswith("error: "))
                self.assertNotIn(marker, err)

    def test_non_integer_now_epoch_is_rejected_by_the_parser(self):
        path = self.write(EXAMPLE)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main(
                    ["break-glass", "check", "--grant", path, "--now-epoch", "soon"]
                )
        self.assertEqual(caught.exception.code, 2)

    # read-only --------------------------------------------------------------------

    def test_the_check_writes_nothing_and_leaves_the_grant_unchanged(self):
        path = self.write(EXAMPLE)
        before_bytes = Path(path).read_bytes()
        before_listing = sorted(p.name for p in self.dir.iterdir())
        for extra in ((), ("--json",), ("--now-epoch", str(EXPIRES))):
            self.run_path(path, *extra)
        self.assertEqual(Path(path).read_bytes(), before_bytes)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), before_listing)

    def test_the_check_never_reads_the_clock(self):
        with mock.patch("time.time", side_effect=AssertionError("clock read")):
            code, report = self.report(EXAMPLE)
        self.assertEqual(code, 0)
        self.assertEqual(report["window"]["status"], "not_evaluated")


if __name__ == "__main__":
    unittest.main()
