"""Contract tests for the API-2 human-decision transport schemas.

Issue #737 freezes the public request/response shapes before #740 implements
the mutation endpoint. These tests deliberately prove the authority split:
callers provide the decision and exact evidence binding, while identity,
timestamps, decision IDs and integration authority remain trusted outputs.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    import jsonschema
    from referencing import Registry, Resource

from idkmesh.work_unit_binding import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
RECORD_EXAMPLE = ROOT / "examples" / "api" / "human-decision-record.example.json"


def _validator(schema_name: str):
    registry = Registry()
    for path in sorted(SCHEMAS.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        registry = registry.with_resource(
            document.get("$id", path.name),
            Resource.from_contents(document),
        )
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema, registry=registry)


@unittest.skipUnless(HAS_JSONSCHEMA, "human-decision API schema tests require jsonschema")
class HumanDecisionApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(RECORD_EXAMPLE.read_text(encoding="utf-8"))
        cls.request_validator = _validator(
            "idkmesh-human-decision-request-v0.1.schema.json"
        )
        cls.response_validator = _validator(
            "idkmesh-human-decision-response-v0.1.schema.json"
        )

    def _request(self) -> dict:
        return {
            "schema_version": "0.1",
            "kind": "idkmesh-human-decision-request",
            "evidence_report": self.record["evidence_report"],
            "selected_attempt_id": self.record["selected_attempt_id"],
            "decision": self.record["decision"],
            "rationale": self.record["rationale"],
        }

    def test_request_is_exactly_the_untrusted_human_choice_surface(self) -> None:
        self.assertEqual([], list(self.request_validator.iter_errors(self._request())))

        forbidden_body_fields = {
            "decision_id": "attacker-chosen-id",
            "decider": {"id": "attacker", "type": "human"},
            "decided_at": "2026-01-01T00:00:00Z",
            "authority": {
                "canonical_state_write": True,
                "git_push": True,
                "merge": True,
            },
            "idempotency_key": "belongs-in-the-http-header",
        }
        for field, value in forbidden_body_fields.items():
            with self.subTest(field=field):
                request = self._request()
                request[field] = value
                self.assertTrue(
                    list(self.request_validator.iter_errors(request)),
                    f"{field} unexpectedly became caller-controlled",
                )

    def test_request_rejects_machine_recommendation_vocabulary(self) -> None:
        request = self._request()
        request["decision"] = "accept_candidate"
        self.assertTrue(list(self.request_validator.iter_errors(request)))

    def test_request_requires_exact_evidence_digest(self) -> None:
        request = self._request()
        request["evidence_report"] = dict(request["evidence_report"])
        request["evidence_report"]["digest"] = "not-a-digest"
        self.assertTrue(list(self.request_validator.iter_errors(request)))

    def test_success_response_wraps_the_existing_immutable_record(self) -> None:
        response = {
            "api_version": "v1",
            "schema_version": "0.1",
            "kind": "idkmesh-human-decision-response",
            "ok": True,
            "decision_record": self.record,
            "decision_record_digest": canonical_digest(self.record),
        }
        self.assertEqual([], list(self.response_validator.iter_errors(response)))
        self.assertEqual(
            response["decision_record_digest"],
            canonical_digest(response["decision_record"]),
        )

    def test_response_cannot_smuggle_integration_authority(self) -> None:
        record = json.loads(json.dumps(self.record))
        record["authority"]["merge"] = True
        response = {
            "api_version": "v1",
            "schema_version": "0.1",
            "kind": "idkmesh-human-decision-response",
            "ok": True,
            "decision_record": record,
            "decision_record_digest": canonical_digest(record),
        }
        self.assertTrue(list(self.response_validator.iter_errors(response)))

    def test_response_is_closed(self) -> None:
        response = {
            "api_version": "v1",
            "schema_version": "0.1",
            "kind": "idkmesh-human-decision-response",
            "ok": True,
            "decision_record": self.record,
            "decision_record_digest": canonical_digest(self.record),
            "merge_authority": True,
        }
        self.assertTrue(list(self.response_validator.iter_errors(response)))


if __name__ == "__main__":
    unittest.main()
