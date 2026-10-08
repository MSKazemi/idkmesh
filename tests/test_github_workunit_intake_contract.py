import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "github-workunit-intake-v0.1.json"
FORM_PATH = ROOT / ".github" / "ISSUE_TEMPLATE" / "06-idkmesh-workunit.yml"


_BLOCK_RE = re.compile(
    r"(?ms)^  - type: (?P<type>[a-z]+)\n(?P<body>.*?)(?=^  - type: |\Z)"
)
_ID_RE = re.compile(r"(?m)^    id: ([a-z0-9_]+)\s*$")


def _form_blocks(text):
    blocks = {}
    for match in _BLOCK_RE.finditer(text):
        body = match.group("body")
        field = _ID_RE.search(body)
        if field is None:
            continue
        field_id = field.group(1)
        if field_id in blocks:
            raise AssertionError(f"duplicate Issue Form id: {field_id}")
        blocks[field_id] = (match.group("type"), body)
    return blocks


class GitHubWorkUnitIntakeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.form = FORM_PATH.read_text(encoding="utf-8")
        cls.blocks = _form_blocks(cls.form)

    def test_contract_targets_current_work_unit_and_real_form(self):
        self.assertEqual(cls_value(self.contract, "schema_version"), "0.1")
        self.assertEqual(
            cls_value(self.contract, "work_unit_schema"),
            "schemas/work-unit-v0.2.schema.json",
        )
        self.assertTrue((ROOT / self.contract["work_unit_schema"]).is_file())
        self.assertEqual(
            cls_value(self.contract, "issue_form_path"),
            ".github/ISSUE_TEMPLATE/06-idkmesh-workunit.yml",
        )
        self.assertTrue((ROOT / self.contract["issue_form_path"]).is_file())

    def test_form_ids_types_labels_and_requiredness_match_contract(self):
        fields = self.contract["fields"]
        expected_ids = [field["id"] for field in fields]
        self.assertEqual(set(self.blocks), set(expected_ids))
        self.assertEqual(len(self.blocks), len(expected_ids))

        for field in fields:
            with self.subTest(field=field["id"]):
                block_type, block = self.blocks[field["id"]]
                self.assertEqual(block_type, field["input_type"])
                self.assertIn(f"label: {field['label']}", block)
                if field["required"]:
                    self.assertIn("required: true", block)
                for option in field.get("allowed_values", []):
                    self.assertIn(f"- {option}", block)

    def test_all_issue_fields_are_non_authoritative(self):
        fields = self.contract["fields"]
        self.assertTrue(fields)
        self.assertTrue(all(field["direct_authority"] is False for field in fields))

        blocked = set(self.contract["authority_boundary"]["must_not_set_from_issue"])
        self.assertIn("permissions.secrets", blocked)
        self.assertIn("permissions.network", blocked)
        self.assertIn("dispatch_authority", blocked)
        self.assertIn("merge_authority", blocked)

    def test_scope_and_policy_hints_are_monotonic_restrictions(self):
        boundary = self.contract["authority_boundary"]
        self.assertEqual(
            boundary["allowed_path_semantics"],
            "intersect_with_trusted_project_policy_only",
        )
        self.assertEqual(
            boundary["forbidden_path_semantics"],
            "union_with_trusted_project_policy_only",
        )
        self.assertIn("never_lower", boundary["risk_semantics"])
        self.assertIn("never_lower", boundary["data_sensitivity_semantics"])
        self.assertIn("never_expand", boundary["external_processing_semantics"])
        self.assertIn("never_remove", boundary["human_review_semantics"])
        self.assertIn("already_eligible", boundary["preferred_connector_semantics"])

    def test_form_states_untrusted_and_no_secret_boundary(self):
        lowered = self.form.casefold()
        self.assertIn("untrusted input", lowered)
        self.assertIn("cannot grant", lowered)
        self.assertIn("do not paste credentials", lowered)
        self.assertIn("cannot authorize sending data", lowered)
        self.assertNotIn("id: secret", lowered)
        self.assertNotIn("id: command", lowered)
        self.assertNotIn("id: merge", lowered)


def cls_value(mapping, key):
    if key not in mapping:
        raise AssertionError(f"contract missing required key: {key}")
    return mapping[key]


if __name__ == "__main__":
    unittest.main()
