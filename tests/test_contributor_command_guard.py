"""Regression coverage for the canonical contributor-command drift guard."""

from __future__ import annotations

from pathlib import Path
import unittest

from tools.contributor_command_guard import (
    Finding,
    documented_make_targets,
    inspect_document,
    inspect_repository,
    parse_makefile_targets,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MAKE_TARGETS = {"setup", "smoke", "test", "integration", "nightly", "gate"}


def _valid_doc(extra: str = "") -> str:
    return f"""# Contributor commands

```bash
make setup
make test
make integration
python -m pytest -q
{extra}
```
"""


class ContributorCommandGuardTests(unittest.TestCase):
    def test_current_repository_has_no_command_drift(self) -> None:
        self.assertEqual(inspect_repository(REPO_ROOT), [])

    def test_makefile_parser_finds_named_targets_not_dot_directives(self) -> None:
        makefile = """.PHONY: setup test\nsetup: ## install\n\t@true\ntest: setup\n\t@true\n"""
        self.assertEqual(parse_makefile_targets(makefile), {"setup", "test"})

    def test_documented_make_targets_come_only_from_literal_code_surfaces(self) -> None:
        text = """We make a contribution. Use `make test` when ready.\n\n```bash\nmake integration\n```\n"""
        self.assertEqual(documented_make_targets(text), {"test", "integration"})

    def test_negative_fixture_rejects_documented_absent_make_target(self) -> None:
        findings = inspect_document(
            name="fixture.md",
            text=_valid_doc("make definitely-not-a-target"),
            make_targets=MAKE_TARGETS,
            pytest_root_is_configured=True,
        )
        self.assertIn(
            "missing-make-target",
            {finding.code for finding in findings},
        )
        self.assertTrue(
            any("definitely-not-a-target" in finding.detail for finding in findings)
        )

    def test_negative_fixture_rejects_obsolete_pytest_pythonpath_requirement(self) -> None:
        findings = inspect_document(
            name="fixture.md",
            text=_valid_doc("PYTHONPATH=. python -m pytest -q"),
            make_targets=MAKE_TARGETS,
            pytest_root_is_configured=True,
        )
        self.assertIn(
            Finding(
                source="fixture.md",
                code="obsolete-pytest-pythonpath",
                detail=(
                    "fenced code block 1 reintroduces `PYTHONPATH=.` for pytest "
                    "even though pytest.ini sets `pythonpath = .`"
                ),
            ),
            findings,
        )

    def test_negative_fixture_rejects_current_unmerged_make_claim(self) -> None:
        text = _valid_doc() + "\nDo not depend on unmerged `make test` commands.\n"
        findings = inspect_document(
            name="fixture.md",
            text=text,
            make_targets=MAKE_TARGETS,
            pytest_root_is_configured=True,
        )
        self.assertIn("unmerged-make-command", {finding.code for finding in findings})

    def test_historical_correction_is_not_treated_as_current_state(self) -> None:
        text = (
            _valid_doc()
            + "\nIf an older issue says the Makefile or `make test` are unmerged, "
            "treat that as a historical snapshot and follow current repository files.\n"
        )
        findings = inspect_document(
            name="fixture.md",
            text=text,
            make_targets=MAKE_TARGETS,
            pytest_root_is_configured=True,
        )
        self.assertNotIn(
            "unmerged-make-command",
            {finding.code for finding in findings},
        )
        self.assertNotIn(
            "makefile-not-current",
            {finding.code for finding in findings},
        )


if __name__ == "__main__":
    unittest.main()
