"""E5 (#672): ``idkmesh egress-policy check`` and ``idkmesh secret-reference check``.

Both verbs are thin, read-only front ends over ``idkmesh.enterprise_egress_policy``
and ``idkmesh.enterprise_secret_reference``. These tests drive the real
``cli.main(argv)`` and pin the exit-code contract (0 allowed, 1 denied, 2 unusable
input with empty stdout), host normalisation identical to the library, stable
sorted JSON, and that no DNS, socket, environment or secret value is touched or
printed.

Control profiles are the committed example documents (read from disk by path);
the only files written are egress policies, which contain hostnames, zones and
data-class names only.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from idkmesh import cli
from idkmesh.enterprise_egress_policy import decide_classified_egress

ROOT = Path(__file__).resolve().parents[1]
G1 = "examples/enterprise/g1-github-native.example.json"  # github_actions backend
G2 = "examples/enterprise/g2-self-hosted.example.json"  # oidc_workload_identity
SM = "<external_secret_manager variant of G1, supplied in memory>"
POLICY_PATH = ROOT / "examples/enterprise/egress-policy.example.json"
POLICY = json.loads(POLICY_PATH.read_text("utf-8"))

INTERNAL = "artifacts.corp.example"
PROVIDER = "api.provider-a.example"
PUBLIC = "packages.registry.example"


def _profile(rel: str) -> str:
    return str(ROOT / rel)


def _secret_manager_profile() -> dict:
    """G1 with the secret-manager backend, kept in memory (never written to disk)."""
    profile = json.loads((ROOT / G1).read_text("utf-8"))
    profile["secrets"]["backend"] = "external_secret_manager"
    return profile


class _CliCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # One parser for the whole class; parse_args never mutates it.
        parser = cli.build_parser()
        cls._patch = mock.patch.object(cli, "build_parser", lambda: parser)
        cls._patch.start()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls._tmp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patch.stop()
        cls._tmp.cleanup()

    @classmethod
    def write(cls, name: str, value: object) -> str:
        path = cls.dir / name
        path.write_text(
            value if isinstance(value, str) else json.dumps(value), encoding="utf-8"
        )
        return str(path)

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(list(argv))
            except SystemExit as exc:  # argparse usage errors
                code = int(exc.code)
        return code, out.getvalue(), err.getvalue()


class EgressPolicyCheckTests(_CliCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.policy = str(POLICY_PATH)
        # Provider destination listed for restricted data; the profile flag for
        # restricted stays false, so only the profile can deny it.
        widened = copy.deepcopy(POLICY)
        widened["destinations"][1]["allowed_classes"] = ["public", "restricted"]
        cls.widened = cls.write("widened.json", widened)

    def check(self, destination, classification="public", profile=G1, *extra, policy=None):
        return self.run_cli(
            "egress-policy", "check",
            "--policy", policy or self.policy,
            "--profile", _profile(profile),
            "--classification", classification,
            "--destination", destination,
            *extra,
        )

    def decision(self, destination, classification="public", profile=G1, *extra, policy=None):
        code, out, err = self.check(
            destination, classification, profile, "--json", *extra, policy=policy
        )
        self.assertEqual(err, "")
        return code, json.loads(out)

    def test_allowed_and_denied_exit_codes(self):
        code, doc = self.decision(PUBLIC)
        self.assertEqual((code, doc["effect"], doc["code"]), (0, "allow", "classified_egress_allowed"))
        self.assertEqual(doc["destination_id"], "package-index")
        code, doc = self.decision(INTERNAL, "restricted")
        self.assertEqual((code, doc["effect"]), (0, "allow"))
        code, doc = self.decision(PROVIDER, "restricted")
        self.assertEqual((code, doc["effect"], doc["code"]), (1, "deny", "class_not_permitted_for_destination"))
        self.assertEqual(doc["destination_id"], "provider-a-api")

    def test_decision_equals_the_library_decision(self):
        profile = json.loads((ROOT / G1).read_text("utf-8"))
        for host, klass in ((PUBLIC, "public"), (PROVIDER, "internal"), ("other.test", "public")):
            expected = decide_classified_egress(
                profile, POLICY, destination_host=host, data_class=klass
            ).to_dict()
            code, doc = self.decision(host, klass)
            self.assertEqual(doc, expected)
            self.assertEqual(code, 0 if expected["effect"] == "allow" else 1)

    def test_profile_denies_even_when_the_policy_lists_the_class(self):
        # Non-compensating: widening the policy does not override the profile.
        code, doc = self.decision(PROVIDER, "restricted", G1, policy=self.widened)
        self.assertEqual((code, doc["effect"]), (1, "deny"))
        self.assertNotEqual(doc["code"], "classified_egress_allowed")
        self.assertEqual(doc["destination_id"], "provider-a-api")

    def test_host_is_normalised_like_the_library(self):
        _, plain = self.decision(PROVIDER)
        code, shouted = self.decision("API.Provider-A.Example.")
        self.assertEqual(code, 0)
        self.assertEqual(shouted, plain)
        self.assertEqual(shouted["destination_host"], PROVIDER)

    def test_look_alike_hosts_are_denied(self):
        for host in (
            "artifacts.corp.example.evil.test",
            "evil-artifacts.corp.example",
            "artifacts.corp.example.evil.test.",
            "xartifacts.corp.example",
            "corp.example",
        ):
            with self.subTest(host=host):
                code, doc = self.decision(host, "public")
                self.assertEqual((code, doc["effect"]), (1, "deny"))
                self.assertEqual(doc["destination_id"], "")
                self.assertEqual(doc["code"], "egress_denied_by_default")

    def test_malformed_destination_or_class_is_exit_two_with_empty_stdout(self):
        for host in ("https://packages.registry.example", "packages.registry.example:443",
                     "*.registry.example", "a b.example", "", "user@host.example"):
            with self.subTest(host=host):
                code, out, err = self.check(host)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.startswith("error: "))
        code, out, _ = self.check(PUBLIC, "top-secret")
        self.assertEqual((code, out), (2, ""))
        code, out, _ = self.run_cli("egress-policy", "check", "--policy", self.policy)
        self.assertEqual((code, out), (2, ""))

    def test_unreadable_or_invalid_inputs_are_exit_two_with_empty_stdout(self):
        bad_policy = copy.deepcopy(POLICY)
        bad_policy["destinations"][0]["extra_field"] = 1
        wildcard = copy.deepcopy(POLICY)
        wildcard["destinations"][0]["host"] = "*.corp.example"
        duplicate_keys = '{"kind": "a", "kind": "b"}'
        cases = {
            "missing": str(self.dir / "absent.json"),
            "not_json": self.write("nj.json", "{nope"),
            "duplicate": self.write("dup.json", duplicate_keys),
            "unknown_field": self.write("unk.json", bad_policy),
            "wildcard": self.write("wild.json", wildcard),
            "not_object": self.write("arr.json", "[]"),
            "directory": str(self.dir),
        }
        for label, path in cases.items():
            with self.subTest(policy=label):
                code, out, err = self.check(PUBLIC, policy=path)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.startswith("error: "))
        bad_profile = self.write("profile.json", '{"kind": "x"}')
        code, out, err = self.run_cli(
            "egress-policy", "check", "--policy", self.policy, "--profile", bad_profile,
            "--classification", "public", "--destination", PUBLIC,
        )
        self.assertEqual((code, out), (2, ""))
        self.assertIn("invalid enterprise control profile", err)

    def test_json_is_stable_sorted_and_carries_the_policy_digest(self):
        code, out, _ = self.check(PUBLIC, "public", G1, "--json")
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual(out, json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n")
        self.assertEqual(self.check(PUBLIC, "public", G1, "--json"), (code, out, ""))
        self.assertRegex(doc["policy_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(
            doc["authority"],
            {"canonical_state_write": False, "executes_action": False, "merge": False,
             "performs_network_io": False, "reads_secret_value": False},
        )
        code, text, _ = self.check(PUBLIC)
        self.assertEqual(code, 0)
        self.assertIn(f"policy_digest: {doc['policy_digest']}", text)
        self.assertIn("destination_id: package-index", text)

    def test_provider_flag_can_only_tighten(self):
        code, doc = self.decision(PROVIDER, "public", G1, "--provider", "provider-a")
        self.assertEqual((code, doc["effect"]), (0, "allow"))
        code, doc = self.decision(PROVIDER, "public", G1, "--provider", "provider-b")
        self.assertEqual((code, doc["effect"], doc["code"]), (1, "deny", "provider_mismatch"))
        code, doc = self.decision(PUBLIC, "public", G1, "--provider", "provider-a")
        self.assertEqual((code, doc["code"]), (1, "provider_mismatch"))
        # An existing denial keeps its own reason code.
        code, doc = self.decision(PROVIDER, "restricted", G1, "--provider", "provider-b")
        self.assertEqual(doc["code"], "class_not_permitted_for_destination")

    def test_offline_and_read_only(self):
        before = sorted(p.name for p in self.dir.iterdir())
        boom = AssertionError("network or environment touched")
        with mock.patch("socket.getaddrinfo", side_effect=boom), \
                mock.patch("socket.gethostbyname", side_effect=boom), \
                mock.patch("socket.socket.connect", side_effect=boom), \
                mock.patch.dict(os.environ, {"IDKMESH_SENTINEL": "must-not-appear"}):
            code, out, err = self.check(PROVIDER, "public", G1, "--json")
        self.assertEqual(code, 0)
        self.assertNotIn("must-not-appear", out + err)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), before)


class SecretReferenceCheckTests(_CliCase):
    def check(self, reference, *extra):
        return self.run_cli("secret-reference", "check", reference, *extra)

    def decision(self, reference, *extra):
        code, out, err = self.check(reference, "--json", *extra)
        self.assertEqual(err, "")
        return code, json.loads(out)

    def test_well_formed_references_exit_zero(self):
        for reference, scheme in (
            ("env:BUILD_REF", "env"),
            ("gh-secret:DEPLOY_REF", "gh-secret"),
            ("secret:team/ci/registry", "secret"),
            ("vault:team/ci/registry", "vault"),
        ):
            with self.subTest(reference=reference):
                code, doc = self.decision(reference)
                self.assertEqual((code, doc["effect"], doc["code"]), (0, "allow", "reference_well_formed"))
                self.assertEqual((doc["reference"], doc["scheme"]), (reference, scheme))
                self.assertIs(doc["secret_value_read"], False)
                self.assertIs(doc["authorization_evaluated"], False)

    def test_refused_references_exit_one_and_are_never_echoed(self):
        inline = "ghp_" + "aB3dE5gH7jK9" * 3  # credential-shaped, built at runtime
        cases = (
            (inline, "inline_secret_forbidden"),
            ("plain-value", "inline_secret_forbidden"),
            ("vault:a/../b", "invalid_name"),
            ("vault:a//b", "invalid_name"),
            ("env:1BAD", "invalid_name"),
            ("env:bad-name", "invalid_name"),
            ("file:etc/hostname", "unsupported_scheme"),
        )
        for reference, expected in cases:
            with self.subTest(code=expected):
                code, out, err = self.check(reference, "--json")
                self.assertEqual((code, err), (1, ""))
                doc = json.loads(out)
                self.assertEqual((doc["effect"], doc["code"]), ("deny", expected))
                self.assertNotIn("reference", doc)
                for fragment in (reference, reference.split(":", 1)[-1]):
                    self.assertNotIn(fragment, out)
                text_code, text_out, _ = self.check(reference)
                self.assertEqual(text_code, 1)
                self.assertNotIn(reference, text_out)

    def test_resolves_nothing(self):
        with mock.patch.dict(os.environ, {"BUILD_REF": "sentinel-value-1234"}), \
                mock.patch("socket.getaddrinfo", side_effect=AssertionError("network")):
            code, out, err = self.check("env:BUILD_REF", "--json")
        self.assertEqual(code, 0)
        self.assertNotIn("sentinel-value-1234", out + err)

    def test_profile_backend_compatibility(self):
        cases = (
            ("gh-secret:DEPLOY_REF", G1, 0, "credential_permitted"),
            ("env:BUILD_REF", G1, 1, "credential_not_from_profile_backend"),
            ("vault:team/ci/registry", SM, 0, "credential_permitted"),
            ("secret:team/ci/registry", SM, 0, "credential_permitted"),
            ("gh-secret:DEPLOY_REF", SM, 1, "credential_not_from_profile_backend"),
            # Workload identity has no stored secret to reference.
            ("vault:team/ci/registry", G2, 1, "credential_not_from_profile_backend"),
        )
        for reference, profile, exit_code, expected in cases:
            with self.subTest(reference=reference, profile=profile):
                if profile == SM:
                    with mock.patch.object(
                        cli, "_load_enterprise_profile_file",
                        return_value=_secret_manager_profile(),
                    ):
                        code, doc = self.decision(reference, "--profile", "in-memory")
                else:
                    code, doc = self.decision(reference, "--profile", _profile(profile))
                self.assertEqual((code, doc["code"]), (exit_code, expected))
                self.assertIs(doc["authorization_evaluated"], False)
        code, out, _ = self.check("gh-secret:DEPLOY_REF", "--profile", _profile(G1))
        self.assertIn("authorization: not evaluated", out)

    def test_unusable_profile_is_exit_two_with_empty_stdout(self):
        for label, path in (
            ("missing", str(self.dir / "absent.json")),
            ("invalid", self.write("p.json", '{"kind": "x"}')),
            ("not_json", self.write("pj.json", "{nope")),
        ):
            with self.subTest(profile=label):
                code, out, err = self.check("env:BUILD_REF", "--profile", path)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.startswith("error: "))

    def test_json_is_stable_and_sorted(self):
        code, out, _ = self.check("vault:team/ci/registry", "--json")
        doc = json.loads(out)
        self.assertEqual(out, json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n")
        self.assertEqual(self.check("vault:team/ci/registry", "--json"), (code, out, ""))


if __name__ == "__main__":
    unittest.main()
