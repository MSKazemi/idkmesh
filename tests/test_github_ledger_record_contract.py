import copy
import json
from pathlib import Path
import unittest

import jsonschema

from idkmesh.connector_routing import (
    AUTHORITY_MODES,
    RISK_ORDER,
    TIER_ORDER,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "github-ledger-record-v0.1.schema.json"
EXAMPLE_PATH = (
    ROOT
    / "examples"
    / "github-ledger"
    / "dispatch-record-v0.1.json"
)


class GitHubLedgerRecordContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
        cls.validator = jsonschema.Draft202012Validator(
            cls.schema,
            format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
        )

    def assert_invalid(self, document):
        errors = list(self.validator.iter_errors(document))
        self.assertTrue(errors, "document unexpectedly validated")

    def test_representative_dispatch_record_validates(self):
        self.validator.validate(self.example)

    def test_routing_vocabularies_match_current_connector_contract(self):
        routing = self.schema["$defs"]["routing"]["properties"]
        self.assertEqual(
            set(routing["required_capability_tier"]["enum"]),
            set(TIER_ORDER),
        )
        self.assertEqual(
            set(routing["authority_mode"]["enum"]),
            set(AUTHORITY_MODES),
        )
        self.assertEqual(
            set(routing["risk_class"]["enum"]),
            set(RISK_ORDER),
        )

    def test_exact_work_unit_digest_source_and_idempotency_are_required(self):
        for path in (
            ("work_unit", "digest"),
            ("work_unit", "source_revision"),
            ("idempotency", "dispatch_key"),
            ("idempotency", "request_digest"),
            ("idempotency", "attempt_number"),
        ):
            with self.subTest(path=path):
                document = copy.deepcopy(self.example)
                del document[path[0]][path[1]]
                self.assert_invalid(document)

    def test_source_revision_must_be_exact_git_object_id(self):
        document = copy.deepcopy(self.example)
        document["work_unit"]["source_revision"] = "main"
        self.assert_invalid(document)

    def test_unknown_secret_or_payload_fields_fail_closed(self):
        mutations = (
            ("provider", "api_token", "secret-value"),
            ("provider", "raw_response", {"ok": True}),
            ("event", "authorization", "Bearer secret"),
            ("idempotency", "secret_ref", "env:PROVIDER_TOKEN"),
        )
        for container, key, value in mutations:
            with self.subTest(container=container, key=key):
                document = copy.deepcopy(self.example)
                document[container][key] = value
                self.assert_invalid(document)

    def test_repository_relative_evidence_path_rejects_traversal(self):
        document = copy.deepcopy(self.example)
        document["candidate_reference"] = {
            "kind": "candidate_reference",
            "digest": "sha256:" + "d" * 64,
            "storage_path": "../private/candidate.json",
        }
        self.assert_invalid(document)

    def test_negative_and_ambiguous_provider_state_remain_representable(self):
        ambiguous = copy.deepcopy(self.example)
        ambiguous["provider"]["submission_state"] = "ambiguous"
        ambiguous["failure"] = {
            "code": "provider_submission_ambiguous",
            "classification": "recovery_required",
            "retryable": False,
        }
        self.validator.validate(ambiguous)

        failed = copy.deepcopy(self.example)
        failed["event"]["state"] = "attempt_failed"
        failed["provider"]["submission_state"] = "definite_failure"
        failed["failure"] = {
            "code": "provider_unavailable",
            "classification": "provider",
            "retryable": True,
        }
        self.validator.validate(failed)

    def test_evidence_is_referenced_by_digest_not_embedded(self):
        document = copy.deepcopy(self.example)
        document["candidate_reference"] = {
            "kind": "candidate_reference",
            "digest": "sha256:" + "d" * 64,
            "storage_path": "ledger/evidence/candidate-1.json",
        }
        document["result_manifest"] = {
            "kind": "result_manifest",
            "digest": "sha256:" + "e" * 64,
            "storage_path": "ledger/evidence/result-1.json",
        }
        document["verification_results"] = [
            {
                "kind": "verification_result",
                "digest": "sha256:" + "f" * 64,
                "storage_path": "ledger/evidence/verify-1.json",
            }
        ]
        self.validator.validate(document)
        rendered = json.dumps(document, sort_keys=True)
        self.assertNotIn("prompt", rendered.casefold())
        self.assertNotIn("stdout", rendered.casefold())
        self.assertNotIn("authorization", rendered.casefold())

    def test_authority_ceiling_cannot_be_enabled(self):
        authority = self.schema["$defs"]["authority"]["properties"]
        self.assertTrue(authority)
        self.assertTrue(
            all(field_schema == {"const": False} for field_schema in authority.values())
        )
        for field in authority:
            with self.subTest(field=field):
                document = copy.deepcopy(self.example)
                document["authority"][field] = True
                self.assert_invalid(document)

    def test_first_record_can_have_no_previous_digest(self):
        document = copy.deepcopy(self.example)
        document["ledger_sequence"] = 1
        document["previous_record_digest"] = None
        self.validator.validate(document)

    def test_record_is_closed_at_every_security_sensitive_object(self):
        self.assertFalse(self.schema["additionalProperties"])
        for definition in (
            "event",
            "workUnit",
            "routing",
            "idempotency",
            "attempt",
            "provider",
            "evidenceRef",
            "humanDecision",
            "failure",
            "authority",
        ):
            with self.subTest(definition=definition):
                self.assertFalse(
                    self.schema["$defs"][definition]["additionalProperties"]
                )


if __name__ == "__main__":
    unittest.main()
