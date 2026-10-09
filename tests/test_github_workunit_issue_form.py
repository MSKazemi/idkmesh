"""Keep the C13-B GitHub Issue Form aligned with the frozen C13-A intake schema (#608)."""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "github-workunit-intake-v0.1.json"
INTAKE_SCHEMA_PATH = ROOT / "schemas" / "github-workunit-intake-v0.1.schema.json"
FORM_PATH = ROOT / ".github" / "ISSUE_TEMPLATE" / "06-idkmesh-workunit.yml"

# Intake-object envelope fields that are set by the normalizer, never by a
# form value. Every other intake property must be collected by the form.
NORMALIZER_ONLY_PROPERTIES = {"schema_version", "kind", "authority_ceiling"}


_BLOCK_RE = re.compile(
    r"(?ms)^  - type: (?P<type>[a-z]+)\n(?P<body>.*?)(?=^  - type: |\Z)"
)
_ID_RE = re.compile(r"(?m)^    id: ([a-z0-9_]+)\s*$")
_OPTIONS_RE = re.compile(r"(?ms)^      options:\n(?P<items>(?:^        - .*\n?)+)")
_OPTION_RE = re.compile(r"(?m)^        - (.+?)\s*$")


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


def _dropdown_options(block):
    options = _OPTIONS_RE.search(block)
    if options is None:
        raise AssertionError("dropdown has no options list")
    return _OPTION_RE.findall(options.group("items"))


class GitHubWorkUnitIssueFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(INTAKE_SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.form = FORM_PATH.read_text(encoding="utf-8")
        cls.blocks = _form_blocks(cls.form)

    def _intake_fields(self):
        return [
            field
            for field in self.contract["fields"]
            if field["canonical_effect"] != "none"
        ]

    def test_contract_targets_current_schemas_and_real_form(self):
        self.assertEqual(cls_value(self.contract, "schema_version"), "0.1")
        self.assertEqual(
            cls_value(self.contract, "work_unit_schema"),
            "schemas/work-unit-v0.2.schema.json",
        )
        self.assertTrue((ROOT / self.contract["work_unit_schema"]).is_file())
        self.assertEqual(
            cls_value(self.contract, "intake_schema"),
            "schemas/github-workunit-intake-v0.1.schema.json",
        )
        self.assertTrue((ROOT / self.contract["intake_schema"]).is_file())
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
                else:
                    self.assertNotIn("required: true", block)

    def test_form_fields_are_exactly_the_frozen_intake_properties(self):
        # C13-A: "C13-B should use these names as the semantic field IDs of
        # the generated form." No second intake vocabulary may appear.
        form_intake_ids = {field["id"] for field in self._intake_fields()}
        schema_ids = set(self.schema["properties"]) - NORMALIZER_ONLY_PROPERTIES
        self.assertEqual(form_intake_ids, schema_ids)
        self.assertTrue(NORMALIZER_ONLY_PROPERTIES.isdisjoint(self.blocks))

    def test_dropdown_options_are_exactly_the_schema_enums(self):
        dropdowns = [
            field for field in self._intake_fields() if field["input_type"] == "dropdown"
        ]
        self.assertTrue(dropdowns)
        for field in dropdowns:
            with self.subTest(field=field["id"]):
                _, block = self.blocks[field["id"]]
                self.assertEqual(
                    _dropdown_options(block),
                    self.schema["properties"][field["id"]]["enum"],
                )
                self.assertNotIn("allowed_values", field)

    def test_optional_form_fields_map_to_schema_fields_that_accept_absence(self):
        for field in self._intake_fields():
            if field["required"]:
                continue
            with self.subTest(field=field["id"]):
                prop = self.schema["properties"][field["id"]]
                types = prop.get("type")
                types = types if isinstance(types, list) else [types]
                accepts_absence = "null" in types or (
                    "array" in types and prop.get("minItems", 0) == 0
                )
                self.assertTrue(accepts_absence)

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
        self.assertNotIn("id: authority", lowered)


def cls_value(mapping, key):
    if key not in mapping:
        raise AssertionError(f"contract missing required key: {key}")
    return mapping[key]


if __name__ == "__main__":
    unittest.main()
