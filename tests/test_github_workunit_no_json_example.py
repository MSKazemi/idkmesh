"""C13-H: committed no-JSON issue form fixtures run through the real offline preview.

No API calls, provider calls, sandbox execution, GitHub mutation, or secrets.
The input snapshots represent synthetic, nonexistent issues.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import unittest

import jsonschema

from idkmesh import cli
from idkmesh.github_workunit_intake import parse_workunit_intake
from idkmesh.work_preview import (
    WorkPreviewError, render_work_preview_text, run_work_preview,
)
from idkmesh.work_unit_binding import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "github-workunit-intake"
PROJECT = FIXTURES / "project"
REPOSITORY = "MSKazemi/idkmesh"
# Input is offline: this is a format-valid synthetic digest, not a claim that
# the sample was produced from this actual repository revision.
SOURCE_SHA = "0123456789abcdef0123456789abcdef01234567"


def preview(name: str, *, use_intake_form: bool = True) -> dict:
    return run_work_preview(
        issue_json=FIXTURES / name,
        project_root=PROJECT,
        repository=REPOSITORY,
        source_revision=SOURCE_SHA,
        use_intake_form=use_intake_form,
    )


class WorkUnitNoJsonExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (ROOT / "schemas" / "work-unit-v0.2.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.intake_schema = json.loads(
            (ROOT / "schemas" / "github-workunit-intake-v0.1.schema.json").read_text(
                encoding="utf-8"
            )
        )

    def test_fixture_parses_with_frozen_schema_and_no_authority(self) -> None:
        issue = json.loads((FIXTURES / "issue-valid.json").read_text(encoding="utf-8"))
        result = parse_workunit_intake(issue["body"])
        self.assertTrue(result.parsed, result.reasons)
        jsonschema.Draft202012Validator(self.intake_schema).validate(result.intake)
        self.assertFalse(any(result.intake["authority_ceiling"].values()))
        self.assertEqual(result.intake["task_class"], "documentation")

    def test_real_preview_is_deterministic_restrictive_and_schema_valid(self) -> None:
        first, second = preview("issue-valid.json"), preview("issue-valid.json")
        self.assertEqual(first, second)
        actual = first["preview"]
        work = actual["work_unit"]
        jsonschema.Draft202012Validator(self.schema).validate(work)
        self.assertEqual(actual["intake"]["status"], "parsed")
        self.assertEqual(work["kind"], "coding")  # trusted policy, not form hint
        self.assertEqual(work["security"]["risk_class"], "high")  # raised
        self.assertEqual(
            work["constraints"]["allowed_paths"],
            ["docs/BEGINNER_GUIDE.md", "tests/test_github_workunit_no_json_example.py"],
        )
        self.assertEqual(
            work["permissions"]["filesystem_write"], work["constraints"]["allowed_paths"]
        )
        for restricted in ("SECURITY.md", ".github/**", ".idkmesh/**"):
            self.assertIn(restricted, work["constraints"]["forbidden_paths"])
        self.assertEqual(work["permissions"]["network"], "none")
        self.assertEqual(work["permissions"]["secrets"], [])
        self.assertEqual(work["budget"]["project_spend_usd_max"], 0)
        self.assertIn("human-review-required", work["constraints"]["policies"])
        self.assertIn("external-processing-forbidden", work["constraints"]["policies"])
        self.assertIn("intake_task_class_differs_from_policy_kind", actual["warnings"])
        self.assertEqual(work["dependencies"], [])
        self.assertTrue(work["verification_policy"]["independent_from_worker"])
        self.assertEqual(actual["work_unit_digest"], canonical_digest(work))
        self.assertIs(first["dispatch_performed"], False)
        self.assertIs(first["github_mutation_performed"], False)
        self.assertIs(first["secret_values_accessed"], False)

    def test_human_summary_redacts_untrusted_body_and_never_dispatches(self) -> None:
        summary = render_work_preview_text(preview("issue-valid.json"))
        self.assertIn("intake form: parsed", summary)
        self.assertIn("dispatch performed: no", summary)
        self.assertNotIn("Clarify the beginner guide", summary)
        self.assertNotIn("informs: #608", summary)

    def test_malformed_form_falls_back_only_to_trusted_generic_policy(self) -> None:
        fallback = preview("issue-unchecked.json")
        generic = preview("issue-unchecked.json", use_intake_form=False)
        self.assertEqual(fallback["preview"]["intake"]["status"], "fallback")
        self.assertIn("intake_fallback", fallback["preview"]["warnings"])
        self.assertEqual(
            fallback["preview"]["work_unit_digest"],
            generic["preview"]["work_unit_digest"],
        )
        # Malformed hints were NOT applied; this is not a dispatch approval.
        self.assertEqual(
            fallback["preview"]["work_unit"]["constraints"]["allowed_paths"],
            ["docs/**", "tests/**"],
        )
        self.assertFalse(fallback["dispatch_performed"])

    def test_valid_form_outside_policy_is_denied(self) -> None:
        with self.assertRaises(WorkPreviewError) as captured:
            preview("issue-out-of-scope.json")
        self.assertEqual(captured.exception.code, "policy_denied")

    def test_documented_cli_entrypoint_json_is_read_only(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main([
                "work", "preview", "--json",
                "--issue-json", str(FIXTURES / "issue-valid.json"),
                "--project-root", str(PROJECT),
                "--repository", REPOSITORY,
                "--source-revision", SOURCE_SHA,
            ])
        self.assertEqual((code, stderr.getvalue()), (0, ""))
        output = json.loads(stdout.getvalue())
        self.assertEqual(output, preview("issue-valid.json"))

    def test_docs_link_to_the_fixture_and_actual_command(self) -> None:
        guide = (ROOT / "docs" / "help" / "GITHUB_WORKUNIT_FORM.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("issue-valid.json", guide)
        self.assertIn("issue-unchecked.json", guide)
        self.assertIn("issue-out-of-scope.json", guide)
        self.assertIn("work preview", guide)
        self.assertIn("git rev-parse HEAD", guide)


if __name__ == "__main__":
    unittest.main()
