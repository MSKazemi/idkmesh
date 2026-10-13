"""C13-C/D GitHub WorkUnit Form parsing and fail-closed preview tests."""

import json
from pathlib import Path
import unittest

import jsonschema

from idkmesh.connector_errors import ConnectorError
from idkmesh.github_issue_preview import (
    GitHubIssueWorkPolicy, GitHubIssueSnapshot, preview_github_issue_work_unit,
)
from idkmesh.github_workunit_intake import (
    ACKNOWLEDGEMENT, ENUMS, FORM_FIELDS, IntakeFormatError,
    parse_github_workunit_form, preview_github_workunit_form,
)
from idkmesh.work_unit_binding import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
SHA = "0123456789abcdef0123456789abcdef01234567"
VALUES = {
    "objective": "Build a bounded test.",
    "task_class": "documentation",
    "expected_outputs": "- tests\n- docs",
    "requested_allowed_paths": "tests/test_example.py\nidkmesh/**",
    "requested_forbidden_paths": ".github/**",
    "dependencies": "requires: #100",
    "acceptance_checks": "- validate schema",
    "risk_hint": "high",
    "data_sensitivity_hint": "confidential",
    "external_processing_hint": "forbidden",
    "human_review_hint": "required",
    "preferred_connector_hint": "jules",
    "safety_acknowledgement": "- [X] " + ACKNOWLEDGEMENT,
}


def form(**overrides):
    fields = dict(VALUES, **overrides)
    return "\n\n".join(
        f"### {label}\n\n{fields[field]}" for field, label in FORM_FIELDS
    ) + "\n"


def snapshot(body):
    return GitHubIssueSnapshot(
        repository="MSKazemi/idkmesh", issue_id=123, number=77,
        title="[WorkUnit] Safe intake", body=body, state="open", locked=False,
        author_login="example", author_id=44, author_association="CONTRIBUTOR",
        labels=(), html_url="https://github.com/MSKazemi/idkmesh/issues/77",
        updated_at="2026-10-11T19:00:00Z",
    )


def policy(**overrides):
    values = dict(repository="MSKazemi/idkmesh",
                  allowed_paths=("idkmesh/**", "tests/**"),
                  forbidden_paths=("SECURITY.md",),
                  risk_class="medium", network="allowlist",
                  network_allowlist=("model.example.invalid",))
    values.update(overrides)
    return GitHubIssueWorkPolicy(**values)


class FormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / "schemas/work-unit-v0.2.schema.json").read_text())
        cls.intake = json.loads((ROOT / "schemas/github-workunit-intake-v0.1.schema.json").read_text())

    def test_frozen_form_contract(self):
        contract = json.loads((ROOT / "config/github-workunit-intake-v0.1.json").read_text())
        self.assertEqual(list(FORM_FIELDS), [
            (entry["id"], entry["label"]) for entry in contract["fields"]
        ])
        for field, choices in ENUMS.items():
            self.assertEqual(list(choices), self.intake["properties"][field]["enum"])

    def test_form_normalizes_and_validates(self):
        value = parse_github_workunit_form(form())
        jsonschema.Draft202012Validator(self.intake).validate(value)
        self.assertEqual(value["expected_outputs"], ["tests", "docs"])
        self.assertEqual(value["dependencies"], [{"relation": "requires", "reference": "#100"}])
        self.assertTrue(all(flag is False for flag in value["authority_ceiling"].values()))
        self.assertEqual(value, parse_github_workunit_form(form()))

    def test_normal_issue_keeps_generic_preview(self):
        issue = snapshot("A normal issue.")
        self.assertIsNone(parse_github_workunit_form(issue.body))
        self.assertEqual(
            preview_github_workunit_form(issue, source_revision=SHA, policy=policy()),
            preview_github_issue_work_unit(issue, source_revision=SHA, policy=policy()),
        )

    def test_policy_bounded_preview(self):
        result = preview_github_workunit_form(snapshot(form()), source_revision=SHA, policy=policy())
        work = result.work_unit
        jsonschema.Draft202012Validator(self.schema).validate(work)
        self.assertEqual(work["constraints"]["allowed_paths"], ["tests/test_example.py", "idkmesh/**"])
        self.assertEqual(work["permissions"]["filesystem_write"], work["constraints"]["allowed_paths"])
        self.assertEqual(work["constraints"]["forbidden_paths"], ["SECURITY.md", ".github/**"])
        self.assertEqual(work["security"]["risk_class"], "high")
        self.assertEqual(work["security"]["data_classification"], "confidential")
        self.assertEqual(work["permissions"]["network"], "none")
        self.assertNotIn("network_allowlist", work["permissions"])
        self.assertEqual(work["permissions"]["secrets"], [])
        self.assertEqual(work["kind"], "coding")
        self.assertTrue(work["verification_policy"]["independent_from_worker"])
        self.assertFalse(result.to_dict()["dispatch_performed"])
        self.assertEqual(result.work_unit_digest, canonical_digest(work))

    def test_low_hints_do_not_downgrade_policy(self):
        result = preview_github_workunit_form(
            snapshot(form(risk_hint="low", data_sensitivity_hint="public", external_processing_hint="allowed")),
            source_revision=SHA,
            policy=policy(risk_class="critical", network="none", network_allowlist=()),
        )
        self.assertEqual(result.work_unit["security"]["risk_class"], "critical")
        self.assertEqual(result.work_unit["permissions"]["network"], "none")

    def test_bad_forms_fail_closed(self):
        for edited in (
            form(objective="_No response_"),
            form(task_class="admin"),
            form(expected_outputs=""),
            form(acceptance_checks=""),
            form(dependencies="run shell command"),
            form(safety_acknowledgement="- [ ] " + ACKNOWLEDGEMENT),
            form().replace("### Task class", "### Unknown", 1),
            form().replace("### Task class", "### Objective", 1),
            form().replace("### Task class", "### Merge\n\ntrue\n\n### Task class", 1),
            "non-form preamble\n" + form(),
            "### Entirely unknown\n\nvalue",
        ):
            with self.subTest(case=edited[:80]):
                with self.assertRaises(ConnectorError):
                    preview_github_workunit_form(snapshot(edited), source_revision=SHA, policy=policy())

    def test_unsafe_path_hints_are_not_accepted(self):
        for hint in (".github/**", "tests/*", "../secrets",
                     "/etc/passwd", "tests/../../other",
                     "tests\\file", "tests/x/", "tests/**/../x"):
            with self.subTest(hint=hint):
                with self.assertRaises(ConnectorError):
                    preview_github_workunit_form(
                        snapshot(form(requested_allowed_paths=hint)),
                        source_revision=SHA, policy=policy(),
                    )

    def test_optional_fields_and_scope_narrowing(self):
        value = parse_github_workunit_form(form(
            requested_forbidden_paths="_No response_", dependencies="_No response_",
            preferred_connector_hint="_No response_",
        ))
        self.assertEqual(value["dependencies"], [])
        self.assertEqual(value["requested_forbidden_paths"], [])
        self.assertIsNone(value["preferred_connector_hint"])
        preview = preview_github_workunit_form(
            snapshot(form(requested_allowed_paths="tests/regression/**")),
            source_revision=SHA, policy=policy(),
        )
        self.assertEqual(preview.work_unit["constraints"]["allowed_paths"], ["tests/regression/**"])

    def test_malformed_duplicate_and_unbound_sha(self):
        with self.assertRaises(IntakeFormatError):
            parse_github_workunit_form(form(acceptance_checks="- test\n- test"))
        with self.assertRaises(ValueError):
            preview_github_workunit_form(snapshot(form()), source_revision="main", policy=policy())


if __name__ == "__main__":
    unittest.main()
