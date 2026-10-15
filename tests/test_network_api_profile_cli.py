"""Tests for ``idkmesh api-network-profile check`` (#743).

Class-based on purpose, like ``tests/test_network_api_profile.py``: the
documented test counts guard module-level ``test_*`` functions.

Fixtures reach the command in memory (``_strict_json_file`` is patched to return
a dict) so no secret-looking value is ever written to disk; only the committed
example, a missing path and three secret-free malformed files touch the file
system. ``main`` is driven with one parser built in ``setUpClass``.
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
from idkmesh.network_api_profile import (
    CHECKS_NOT_PERFORMED,
    CHECKS_PERFORMED,
    NetworkProfileError,
    check_network_profile,
    parse_network_profile,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "enterprise" / "network-api-profile.example.json"
SENTINEL = "zq7Xk2LEAKEDvalue9"


class NetworkProfileCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = cli.build_parser()
        cls.example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def run_cli(self, *args: str, document=None) -> tuple[int, str, str]:
        """Run ``main``; ``document`` replaces the file read, in memory."""
        out, err = io.StringIO(), io.StringIO()
        patches = [mock.patch.object(cli, "build_parser", return_value=self.parser)]
        if document is not None:
            patches.append(mock.patch.object(cli, "_strict_json_file", return_value=document))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            try:
                code = cli.main(list(args))
            except SystemExit as exc:  # argparse rejects a flag
                code = int(exc.code)
        return code, out.getvalue(), err.getvalue()

    def check(self, document, *flags: str) -> tuple[int, str, str]:
        return self.run_cli("api-network-profile", "check", "--profile", "profile.json", *flags, document=document)

    def mutated(self, mutate) -> dict:
        raw = copy.deepcopy(self.example)
        mutate(raw)
        return raw

    # ------------------------------------------------------------------ valid

    def test_committed_example_is_valid(self) -> None:
        code, out, err = self.run_cli("api-network-profile", "check", "--profile", str(EXAMPLE))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("network API profile: VALID", out)
        self.assertIn("not a deployment approval", out)

    def test_json_output_is_sorted_stable_and_never_an_approval(self) -> None:
        first = self.run_cli("api-network-profile", "check", "--profile", str(EXAMPLE), "--json")
        second = self.run_cli("api-network-profile", "check", "--profile", str(EXAMPLE), "--json")
        self.assertEqual(first, second)
        code, out, err = first
        self.assertEqual((code, err), (0, ""))
        report = json.loads(out)
        self.assertEqual(out, json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
        self.assertEqual(report["status"], "valid")
        self.assertIs(report["deployment_approval"], False)
        self.assertIsNone(report["reason"])
        self.assertEqual(report["profile"]["exposure"], "non_loopback")
        self.assertNotIn("checks_performed", report)

    def test_explain_lists_checks_performed_and_not_performed(self) -> None:
        code, out, _ = self.run_cli("api-network-profile", "check", "--profile", str(EXAMPLE), "--json", "--explain")
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual([c["id"] for c in report["checks_performed"]], [i for i, _ in CHECKS_PERFORMED])
        not_performed = {c["id"] for c in report["checks_not_performed"]}
        self.assertLessEqual({"listener_wiring", "tls_verification", "per_process_state"}, not_performed)
        self.assertEqual(len(not_performed), len(CHECKS_NOT_PERFORMED))
        _, text, _ = self.run_cli("api-network-profile", "check", "--profile", str(EXAMPLE), "--explain")
        self.assertIn("checks NOT performed:", text)
        self.assertIn("tls_verification", text)

    def test_loopback_session_token_profile_is_valid(self) -> None:
        def mutate(raw: dict) -> None:
            raw["bind"] = {"host": "127.0.0.1", "port": 8765}
            raw["tls"] = {"mode": "loopback_plaintext"}
            raw["authentication"]["adapter"] = "local_session_token"
            raw["request_policy"]["allowed_hosts"] = []

        code, out, _ = self.check(self.mutated(mutate), "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["profile"]["exposure"], "loopback")

    def test_check_starts_no_listener_and_opens_no_socket(self) -> None:
        with mock.patch("socket.socket", side_effect=AssertionError("socket opened")) as sock:
            code, _, _ = self.run_cli("api-network-profile", "check", "--profile", str(EXAMPLE))
        self.assertEqual(code, 0)
        sock.assert_not_called()

    # ---------------------------------------------------------------- refused

    def test_refusals_report_stable_reason_codes_with_exit_1(self) -> None:
        def set_path(path: tuple, value):
            def mutate(raw: dict) -> None:
                node = raw
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = value

            return mutate

        def plaintext(raw: dict) -> None:
            raw["tls"] = {"mode": "loopback_plaintext"}

        cases = {
            "tls_required": plaintext,
            "session_token_not_authentication": set_path(("authentication", "adapter"), "local_session_token"),
            "unknown_auth_adapter": set_path(("authentication", "adapter"), {"not": "a string"}),
            "unsupported_tls_mode": set_path(("tls", "mode"), ["not", "a", "string"]),
            "invalid_origin": set_path(("request_policy", "allowed_origins"), ["*"]),
            "literal_secret": set_path(("secrets",), {"token_registry_ref": "not-a-reference-value"}),
            "invalid_value": set_path(("request_policy", "rate_limit", "principal_burst"), 10**9),
            "break_glass_unsupported": set_path(("break_glass",), {"enabled": True}),
            "host_allowlist_required": set_path(("request_policy", "allowed_hosts"), []),
            "unknown_field": set_path(("surprise",), 1),
            "denials_must_be_audited": set_path(("audit", "record_denials"), False),
        }
        for code_name, mutate in cases.items():
            with self.subTest(reason=code_name):
                code, out, err = self.check(self.mutated(mutate), "--json")
                self.assertEqual((code, err), (1, ""))
                report = json.loads(out)
                self.assertEqual(report["status"], "refused")
                self.assertEqual(report["reason"]["code"], code_name)
                self.assertIsNone(report["profile"])
                self.assertIs(report["deployment_approval"], False)

    def test_each_unsafe_cors_origin_is_refused(self) -> None:
        for origin in ("*", "null", "http://ui.example.org", "https://ui.example.org/path"):
            with self.subTest(origin=origin):
                raw = self.mutated(lambda r, o=origin: r["request_policy"].__setitem__("allowed_origins", [o]))
                code, out, _ = self.check(raw, "--json")
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(out)["reason"]["code"], "invalid_origin")

    def test_text_output_for_a_refusal_names_the_code(self) -> None:
        code, out, err = self.check(self.mutated(lambda r: r.__setitem__("tls", {"mode": "loopback_plaintext"})))
        self.assertEqual((code, err), (1, ""))
        self.assertIn("network API profile: REFUSED", out)
        self.assertIn("reason: tls_required:", out)

    # ------------------------------------------------------------ redaction

    def test_no_literal_value_from_the_file_reaches_stdout_or_stderr(self) -> None:
        def at(path: tuple, value):
            def mutate(raw: dict) -> None:
                node = raw
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = value

            return mutate

        cases = {
            "registry reference": at(("secrets",), {"token_registry_ref": SENTINEL}),
            "origin": at(("request_policy", "allowed_origins"), [f"https://{SENTINEL}.example.org/x"]),
            "host": at(("request_policy", "allowed_hosts"), [f"{SENTINEL}.EXAMPLE.org"]),
            "proxy": at(("tls", "trusted_proxies"), [SENTINEL]),
            "profile id": at(("profile_id",), f"{SENTINEL} !"),
            "issuer": at(("authentication", "issuer"), f"{SENTINEL} !"),
            "kind": at(("kind",), SENTINEL),
            "bind host": at(("bind", "host"), f"{SENTINEL} !"),
            "unknown field name": at((SENTINEL,), 1),
            "type confusion": at(("tls", "mode"), [SENTINEL]),
        }
        for label, mutate in cases.items():
            for flags in ((), ("--json",), ("--explain",)):
                with self.subTest(case=label, flags=flags):
                    code, out, err = self.check(self.mutated(mutate), *flags)
                    self.assertEqual(code, 1)
                    self.assertNotIn(SENTINEL, out)
                    self.assertNotIn(SENTINEL, err)

    def test_library_messages_never_repeat_an_offending_value(self) -> None:
        for path, key in (
            (("tls", "trusted_proxies"), "invalid_proxy"),
            (("request_policy", "allowed_hosts"), "invalid_host"),
            (("request_policy", "allowed_origins"), "invalid_origin"),
        ):
            with self.subTest(field=".".join(path)):
                raw = copy.deepcopy(self.example)
                raw[path[0]][path[1]] = [f"{SENTINEL}/bad"]
                with self.assertRaises(NetworkProfileError) as caught:
                    parse_network_profile(raw)
                self.assertEqual(caught.exception.code, key)
                self.assertNotIn(SENTINEL, str(caught.exception))

    # ------------------------------------------------------------ exit code 2

    def test_unusable_input_exits_2_with_empty_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            malformed = Path(tmp) / "malformed.json"
            malformed.write_text("{not json", encoding="utf-8")
            array = Path(tmp) / "array.json"
            array.write_text("[]", encoding="utf-8")
            duplicate = Path(tmp) / "duplicate.json"
            duplicate.write_text('{"zzkey123456": 1, "zzkey123456": 2}', encoding="utf-8")
            targets = {
                "missing": str(Path(tmp) / "absent.json"),
                "directory": tmp,
                "malformed": str(malformed),
                "not an object": str(array),
                "duplicate key": str(duplicate),
            }
            for label, target in targets.items():
                with self.subTest(case=label):
                    code, out, err = self.run_cli("api-network-profile", "check", "--profile", target, "--json")
                    self.assertEqual((code, out), (2, ""))
                    self.assertTrue(err.startswith("error: "))
                    self.assertNotIn("zzkey123456", err)

    def test_missing_or_unknown_flags_exit_2_with_empty_stdout(self) -> None:
        for argv in (
            ("api-network-profile", "check"),
            ("api-network-profile", "check", "--profile", "p.json", "--bogus"),
            ("api-network-profile",),
        ):
            with self.subTest(argv=argv):
                code, out, _ = self.run_cli(*argv)
                self.assertEqual((code, out), (2, ""))

    # ---------------------------------------------------------------- library

    def test_check_never_raises_on_garbage(self) -> None:
        for garbage in (None, [], 5, "profile", {}, {"kind": None}, {"tls": []}):
            with self.subTest(garbage=repr(garbage)):
                report = check_network_profile(garbage)
                self.assertEqual(report["status"], "refused")
                self.assertIs(report["deployment_approval"], False)

    def test_non_string_enumerated_fields_raise_the_domain_error(self) -> None:
        for path, value in ((("tls", "mode"), ["x"]), (("authentication", "adapter"), {"a": 1})):
            with self.subTest(field=".".join(path)):
                raw = copy.deepcopy(self.example)
                raw[path[0]][path[1]] = value
                with self.assertRaises(NetworkProfileError):
                    parse_network_profile(raw)


if __name__ == "__main__":
    unittest.main()
