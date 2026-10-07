"""Presence and structure of the idempotency/conflict metadata contract.

Issue #737 freezes every public API object as a machine-readable contract.
`schemas/idkmesh-idempotency-v0.1.schema.json` covers the request-identity
reservation and conflict vocabulary that `idkmesh/product_spine_idempotency.py`
and `idkmesh/github_delivery_idempotency.py` emit (API_CONVENTIONS_V0_1.md
section 12). These tests keep the file present, meta-valid, and honest about
its own required fields and invariants.

`jsonschema` is available in the PR Gate but not in the randomness-lab test
job, so the import is guarded and the validator-dependent tests skip there
rather than breaking collection for the whole module.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "idkmesh-idempotency-v0.1.schema.json"

AUTHORITY = {
    "dispatch": False, "executes_worker": False,
    "accepts_candidate": False, "merge": False,
}

ADMISSION = {
    "schema_version": "0.1",
    "kind": "idkmesh-idempotency-admission",
    "idempotency_key": "github-webhook:owner/repo:delivery-42",
    "request_id": "caller-request-1",
    "request_digest": "sha256:" + "a" * 64,
    "run_id": "offline/0123456789abcdef0123",
    "created": True,
    "replayed": False,
    "authority": dict(AUTHORITY),
}

CONFLICT = {
    "schema_version": "0.1",
    "kind": "idkmesh-idempotency-conflict",
    "idempotency_key": "github-webhook:owner/repo:delivery-42",
    "retained_request_digest": "sha256:" + "a" * 64,
    "presented_request_digest": "sha256:" + "b" * 64,
    "code": "idempotency_conflict",
    "message": "idempotency key already bound to a different canonical request digest",
    "authority": dict(AUTHORITY),
}


class IdempotencySchemaPresenceTests(unittest.TestCase):
    def test_schema_file_exists(self) -> None:
        self.assertTrue(
            SCHEMA_PATH.is_file(),
            f"{SCHEMA_PATH.relative_to(ROOT)} is missing; the idempotency/"
            "conflict vocabulary is defined only in prose without it.",
        )

    def test_schema_identity_follows_repository_conventions(self) -> None:
        document = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(document["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertTrue(document.get("title"))
        self.assertTrue(document["$id"].endswith(SCHEMA_PATH.name))

    def test_structure_freezes_the_required_metadata_fields(self) -> None:
        document = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        forms = {}
        for entry in document["oneOf"]:
            form = document["$defs"][entry["$ref"].rsplit("/", 1)[-1]]
            forms[form["properties"]["kind"]["const"]] = form
        self.assertEqual(
            set(forms),
            {"idkmesh-idempotency-admission", "idkmesh-idempotency-conflict"},
        )
        admission, conflict = forms["idkmesh-idempotency-admission"], forms["idkmesh-idempotency-conflict"]
        self.assertTrue(admission["additionalProperties"] is False)
        self.assertTrue(conflict["additionalProperties"] is False)
        self.assertLessEqual(
            {"schema_version", "kind", "idempotency_key", "request_id",
             "request_digest", "run_id", "created", "replayed", "authority"},
            set(admission["required"]),
        )
        self.assertLessEqual(
            {"schema_version", "kind", "idempotency_key", "retained_request_digest",
             "presented_request_digest", "code", "message", "authority"},
            set(conflict["required"]),
        )


@unittest.skipUnless(HAS_JSONSCHEMA, "instance validation requires jsonschema")
class IdempotencySchemaValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.document)
        cls.validator = Draft202012Validator(cls.document)

    def assert_invalid(self, instance: dict) -> None:
        self.assertNotEqual([], list(self.validator.iter_errors(instance)))

    def test_valid_admission_and_conflict_records_validate(self) -> None:
        self.assertEqual([], list(self.validator.iter_errors(dict(ADMISSION))))
        self.assertEqual([], list(self.validator.iter_errors(dict(CONFLICT))))

    def test_missing_required_fields_are_rejected(self) -> None:
        for form in (ADMISSION, CONFLICT):
            for field in form:
                with self.subTest(kind=form["kind"], missing=field):
                    self.assert_invalid({k: v for k, v in form.items() if k != field})

    def test_bad_digest_unknown_field_and_unknown_kind_are_rejected(self) -> None:
        self.assert_invalid({**ADMISSION, "request_digest": "sha1:" + "a" * 40})
        self.assert_invalid({**CONFLICT, "retained_request_digest": "not-a-digest"})
        self.assert_invalid({**ADMISSION, "accepted": True})
        self.assert_invalid({**ADMISSION, "kind": "idkmesh-idempotency-result"})
        self.assert_invalid({**ADMISSION, "authority": {**AUTHORITY, "merge": True}})

    def test_created_and_replayed_are_exact_complements(self) -> None:
        self.assertEqual([], list(self.validator.iter_errors(
            {**ADMISSION, "created": False, "replayed": True})))
        self.assert_invalid({**ADMISSION, "created": True, "replayed": True})
        self.assert_invalid({**ADMISSION, "created": False, "replayed": False})


if __name__ == "__main__":
    unittest.main()
