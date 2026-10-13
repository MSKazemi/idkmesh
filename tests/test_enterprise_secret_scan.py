"""Tests for the E5 raw-secret scanner (#672).

Sample credentials are assembled from fragments at run time so that this file
never contains a complete credential-shaped literal that a repository secret
scanner would have to allow-list.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
import unittest

from idkmesh.connector_secrets import _SENSITIVE_KEYS as CONNECTOR_SENSITIVE_KEYS
from idkmesh.enterprise_secret_scan import (
    RULE_IDS,
    SENSITIVE_KEYS,
    SecretLeakError,
    assert_no_secrets,
    scan_for_secrets,
)

ROOT = Path(__file__).resolve().parents[1]

# rule id -> a synthetic credential of that shape.
SAMPLES = {
    "private_key_block": "-----BEGIN " + "RSA PRIVATE" + " KEY-----",
    "github_token": "gh" + "p_" + "A1b2C3d4E5" * 4,
    "aws_access_key_id": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
    "slack_token": "xo" + "xb-" + "1234567890-abcdefghij",
    "google_api_key": "AI" + "za" + "A" * 35,
    "api_key_sk": "sk" + "-ant-" + "x1Y2" * 10,
    "jwt": "ey" + "JhbGciOiJIUzI1" + ".ey" + "JzdWIiOiIxMjM0" + ".c2lnbmF0dXJl" + "AAAA",
    "bearer_credential": "Bear" + "er " + "conformance-secret-value-do-not-leak",
    "url_userinfo": "https://" + "deploy:" + "hunter2hunter2" + "@example.org/repo.git",
}


def rules(document, **limits) -> set[str]:
    return {f.rule for f in scan_for_secrets(document, **limits).findings}


class ValueRuleTests(unittest.TestCase):
    def test_every_value_rule_has_a_positive_sample(self) -> None:
        value_rules = {rule for rule in RULE_IDS if rule != "sensitive_key_literal"}
        self.assertEqual(set(SAMPLES), value_rules)

    def test_each_sample_is_detected_as_its_own_rule(self) -> None:
        for rule, sample in SAMPLES.items():
            with self.subTest(rule=rule):
                self.assertEqual(rules({"note": f"see {sample} now"}), {rule})
                self.assertEqual(rules(sample), {rule})

    def test_credential_inside_nested_list_is_located(self) -> None:
        report = scan_for_secrets(
            {"inputs": [{"locator": "ok"}, {"locator": SAMPLES["github_token"]}]}
        )
        self.assertEqual(
            [f.to_dict() for f in report.findings],
            [{"rule": "github_token", "location": "/inputs/1/locator"}],
        )

    def test_ordinary_content_is_not_flagged(self) -> None:
        benign = [
            "Implement the requested behavior and add tests.",
            "a" * 40,  # a git SHA
            "sha256:" + "ab" * 32,
            "https://github.com/MSKazemi/idkmesh/issues/77",
            "https://example.org/a:b/c@d",  # no user:password@ before the path
            "sk-learn is a library",
            "Bearer token authentication is described in the spec",
            "ghp_ is the prefix of a GitHub token",
            "-----BEGIN CERTIFICATE-----",  # public material
            "123e4567-e89b-12d3-a456-426614174000",
            "AKIA",
            "env:JULES_API_KEY",
        ]
        for text in benign:
            with self.subTest(text=text):
                self.assertTrue(scan_for_secrets({"v": text}).clean)


class SensitiveKeyTests(unittest.TestCase):
    def test_literal_value_under_a_credential_named_key_is_flagged(self) -> None:
        for key in ("password", "api_key", "Authorization", "client-secret", "TOKEN"):
            with self.subTest(key=key):
                self.assertEqual(
                    rules({key: "plain-literal-value"}), {"sensitive_key_literal"}
                )

    def test_references_and_placeholders_are_accepted(self) -> None:
        for value in (
            "env:DB_PASSWORD",
            "secret:projects/p/secrets/s",
            "vault:kv/data/app",
            "${DB_PASSWORD}",
            "<redacted>",
            "********",
            "<your token>",
        ):
            with self.subTest(value=value):
                self.assertTrue(scan_for_secrets({"password": value}).clean)

    def test_key_match_is_exact_not_substring(self) -> None:
        document = {
            "max_tokens": "1024-literal-text",
            "secret_ref": "some literal reference text",
            "token_budget": "large budget value",
            "api_key_env": "JULES_API_KEY_NAME",
        }
        self.assertTrue(scan_for_secrets(document).clean)

    def test_short_and_non_string_values_are_not_flagged(self) -> None:
        # Documented limitation: values shorter than 8 characters are ignored.
        self.assertTrue(scan_for_secrets({"token": "abc", "password": 12345678}).clean)

    def test_sensitive_keys_cover_the_connector_boundary(self) -> None:
        self.assertLessEqual(set(CONNECTOR_SENSITIVE_KEYS), set(SENSITIVE_KEYS))


class ReportHygieneTests(unittest.TestCase):
    def test_report_never_contains_the_matched_text(self) -> None:
        for rule, sample in SAMPLES.items():
            with self.subTest(rule=rule):
                report = scan_for_secrets({"leak": sample, "password": "literal-pw-1234"})
                blob = json.dumps(report.to_dict()) + repr(report)
                self.assertFalse(report.clean)
                self.assertNotIn(sample, blob)
                self.assertNotIn("literal-pw-1234", blob)
                # Not even a fragment long enough to be useful.
                self.assertNotIn(sample[len(sample) // 2 :], blob)

    def test_secret_used_as_a_mapping_key_cannot_leak_through_the_path(self) -> None:
        token = SAMPLES["github_token"]
        report = scan_for_secrets({token: "value", "ok": {token: 1}})
        self.assertEqual(
            [f.location for f in report.findings], ["/<key:0>", "/ok/<key:0>"]
        )
        self.assertNotIn(token, json.dumps(report.to_dict()))

    def test_unsafe_key_text_is_replaced_in_locations(self) -> None:
        hostile = "line\nbreak ::error::x"
        report = scan_for_secrets({hostile: SAMPLES["jwt"]})
        self.assertEqual([f.location for f in report.findings], ["/<key:0>"])

    def test_json_pointer_escaping(self) -> None:
        report = scan_for_secrets({"a/b": {"c~d": SAMPLES["aws_access_key_id"]}})
        self.assertEqual([f.location for f in report.findings], ["/a~1b/c~0d"])

    def test_report_declares_no_authority(self) -> None:
        body = scan_for_secrets({}).to_dict()
        self.assertEqual(
            body["authority"],
            {
                "grants_runtime_authority": False,
                "reads_environment": False,
                "performs_io": False,
            },
        )

    def test_findings_are_ordered_and_input_order_independent(self) -> None:
        forward = {"b": SAMPLES["jwt"], "a": SAMPLES["slack_token"], "password": "literal-pw-1234"}
        reverse = dict(reversed(list(forward.items())))
        first, second = scan_for_secrets(forward), scan_for_secrets(reverse)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(
            [f.location for f in first.findings], sorted(f.location for f in first.findings)
        )


class SensitiveKeyContainerTests(unittest.TestCase):
    """A literal secret must not escape by being wrapped in a list."""

    def rules(self, document) -> list[tuple[str, str]]:
        return [(f.rule, f.location) for f in scan_for_secrets(document).findings]

    def test_literal_in_a_list_under_a_sensitive_key_is_found(self) -> None:
        self.assertEqual(
            self.rules({"password": ["literal-pw-1234"]}),
            [("sensitive_key_literal", "/password/0")],
        )

    def test_nested_lists_inherit_the_sensitive_key(self) -> None:
        self.assertEqual(
            self.rules({"api_key": [["short", "literal-pw-1234"]]}),
            [("sensitive_key_literal", "/api_key/0/1")],
        )

    def test_references_and_short_values_in_such_a_list_stay_clean(self) -> None:
        self.assertTrue(scan_for_secrets({"token": ["env:DEPLOY_TOKEN", "abc"]}).clean)

    def test_list_under_an_ordinary_key_is_not_judged_by_key(self) -> None:
        self.assertTrue(scan_for_secrets({"labels": ["literal-pw-1234"]}).clean)

    def test_objects_under_a_sensitive_key_use_their_own_keys(self) -> None:
        # Documented boundary: no benign object is flagged merely for its parent's name.
        self.assertTrue(scan_for_secrets({"credentials": {"provider": "github-actions"}}).clean)
        self.assertEqual(
            self.rules({"credentials": {"password": "literal-pw-1234"}}),
            [("sensitive_key_literal", "/credentials/password")],
        )


class FailClosedTests(unittest.TestCase):
    def assert_incomplete(self, document, reason: str, **limits) -> None:
        report = scan_for_secrets(document, **limits)
        self.assertFalse(report.complete)
        self.assertFalse(report.clean)
        self.assertIn(reason, report.incomplete_reasons)

    def test_depth_limit_is_not_reported_as_clean(self) -> None:
        document: object = "leaf"
        for _ in range(40):
            document = [document]
        self.assert_incomplete(document, "depth_limit_exceeded")

    def test_node_limit_is_not_reported_as_clean(self) -> None:
        self.assert_incomplete(list(range(50)), "node_limit_exceeded", max_nodes=10)

    def test_oversized_string_is_not_reported_as_clean(self) -> None:
        self.assert_incomplete({"v": "x" * 100}, "string_too_large", max_string_chars=50)
        self.assert_incomplete({"x" * 100: 1}, "string_too_large", max_string_chars=50)

    def test_non_json_values_are_not_reported_as_clean(self) -> None:
        documents = (
            {"v": b"bytes"},
            {"v": {1, 2}},
            {"v": object()},
            {1: "non-string key"},
        )
        for document in documents:
            with self.subTest(document=repr(document)):
                self.assert_incomplete(document, "unsupported_value")

    def test_nonfinite_float_is_not_valid_json(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=str(value)):
                self.assert_incomplete({"value": value}, "unsupported_value")

    def test_container_budget_refuses_fanout_before_enqueue_or_sort(self) -> None:
        document = {f"field{i}": i for i in range(1000)}
        mapping = scan_for_secrets(document, max_nodes=10)
        sequence = scan_for_secrets(list(range(1000)), max_nodes=10)
        for report in (mapping, sequence):
            self.assertFalse(report.clean)
            self.assertIn("node_limit_exceeded", report.incomplete_reasons)
            self.assertEqual(report.nodes_scanned, 1)

    def test_non_json_container_subclasses_are_rejected_without_iteration(self) -> None:
        class HostileDict(dict):
            def __iter__(self):
                raise AssertionError("must not iterate custom mapping")

        class HostileList(list):
            def __iter__(self):
                raise AssertionError("must not iterate custom list")

        self.assert_incomplete(HostileDict({"token": "untrusted-value"}), "unsupported_value")
        self.assert_incomplete(HostileList(["value"]), "unsupported_value")

    def test_invalid_scan_limits_raise_configuration_errors(self) -> None:
        for options in (
            {"max_nodes": 0},
            {"max_nodes": True},
            {"max_depth": -1},
            {"max_string_chars": "invalid"},
        ):
            with self.subTest(options=options), self.assertRaisesRegex(
                ValueError, "positive integers"
            ):
                scan_for_secrets({"safe": "text"}, **options)

    def test_a_finding_and_an_incomplete_scan_can_coexist(self) -> None:
        report = scan_for_secrets([SAMPLES["jwt"], b"x"])
        self.assertEqual({f.rule for f in report.findings}, {"jwt"})
        self.assertFalse(report.complete)

    def test_cyclic_input_terminates(self) -> None:
        cycle: list = []
        cycle.append(cycle)
        self.assert_incomplete(cycle, "depth_limit_exceeded")

    def test_pathological_strings_scan_in_bounded_time(self) -> None:
        # Unbounded quantifiers make these inputs quadratic: with one reverted,
        # this set takes ~37 CPU-s instead of ~0.1. The budget sits between the
        # two with a wide margin either way, and measures CPU, not wall time.
        started = time.process_time()
        for text in ("a" * 200_000, "a://" * 50_000, "x:" * 100_000, "Bearer " * 30_000):
            with self.subTest(prefix=text[:8]):
                self.assertTrue(scan_for_secrets(text).complete)
        self.assertLess(time.process_time() - started, 5.0)


class AssertNoSecretsTests(unittest.TestCase):
    def test_clean_document_returns_the_report(self) -> None:
        report = assert_no_secrets({"objective": "do the thing"}, context="work_unit")
        self.assertTrue(report.clean)

    def test_leak_raises_without_the_value(self) -> None:
        sample = SAMPLES["github_token"]
        with self.assertRaises(SecretLeakError) as caught:
            assert_no_secrets({"objective": sample}, context="work_unit")
        message = str(caught.exception)
        self.assertTrue(message.startswith("secret_detected: work_unit: github_token at /objective"))
        self.assertNotIn(sample, message)
        self.assertEqual(caught.exception.report.findings[0].rule, "github_token")

    def test_incomplete_scan_raises_scan_incomplete(self) -> None:
        with self.assertRaises(SecretLeakError) as caught:
            assert_no_secrets([b"x"], context="result")
        self.assertTrue(str(caught.exception).startswith("scan_incomplete: result: "))

    def test_long_finding_lists_are_summarised(self) -> None:
        document = {f"k{i}": SAMPLES["slack_token"] for i in range(9)}
        with self.assertRaises(SecretLeakError) as caught:
            assert_no_secrets(document, context="audit")
        self.assertIn("(+4 more)", str(caught.exception))


class RepositoryCorpusTests(unittest.TestCase):
    """The scanner must not cry wolf on the repository's own documents."""

    def test_checked_in_json_examples_are_clean(self) -> None:
        paths = sorted((ROOT / "examples").rglob("*.json"))
        self.assertGreater(len(paths), 10)
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                document = json.loads(path.read_text(encoding="utf-8"))
                report = scan_for_secrets(document)
                self.assertTrue(report.clean, report.to_dict())


if __name__ == "__main__":
    unittest.main()
