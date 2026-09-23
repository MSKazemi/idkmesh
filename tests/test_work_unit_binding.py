import copy
import unittest

from experiments.provenance_integrity import canonical_digest as phase0_canonical_digest
from idkmesh.work_unit_binding import (
    WorkUnitBindingError,
    bind_work_unit_source,
    canonical_digest,
    validate_work_unit_source_binding,
)


SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER_SHA = "1123456789abcdef0123456789abcdef01234567"


def _work_unit(*, declared_revision=None):
    provenance = {
        "created_by": "test",
        "creator_type": "system",
        "source": "fixture",
    }
    if declared_revision is not None:
        provenance["source_revision"] = declared_revision
    return {
        "schema_version": "0.2",
        "id": "test/work-unit",
        "version": 2,
        "objective": "Bounded test work",
        "provenance": provenance,
    }


class WorkUnitSourceBindingTests(unittest.TestCase):
    def test_digest_matches_existing_phase0_convention(self):
        work_unit = _work_unit()
        self.assertEqual(
            canonical_digest(work_unit),
            phase0_canonical_digest(work_unit),
        )

    def test_trusted_revision_binds_work_unit_without_declared_revision(self):
        work_unit = _work_unit()
        binding = bind_work_unit_source(
            work_unit,
            source_revision=SHA.upper(),
        )
        self.assertEqual(
            binding.to_dict(),
            {
                "work_unit_id": "test/work-unit",
                "work_unit_version": 2,
                "work_unit_digest": phase0_canonical_digest(work_unit),
                "source_revision": SHA,
            },
        )
        validate_work_unit_source_binding(
            work_unit,
            binding,
            source_revision=SHA,
        )

    def test_declared_revision_must_match_trusted_revision(self):
        matching = _work_unit(declared_revision=SHA.upper())
        bind_work_unit_source(matching, source_revision=SHA)

        mismatched = _work_unit(declared_revision=OTHER_SHA)
        with self.assertRaisesRegex(
            WorkUnitBindingError,
            "does not match WorkUnit provenance",
        ):
            bind_work_unit_source(mismatched, source_revision=SHA)

    def test_source_revision_must_be_immutable_git_object_id(self):
        for revision in ("main", "", "a" * 39, "g" * 40):
            with self.subTest(revision=revision):
                with self.assertRaises(WorkUnitBindingError):
                    bind_work_unit_source(
                        _work_unit(),
                        source_revision=revision,
                    )

    def test_mutating_work_unit_after_binding_fails_closed(self):
        work_unit = _work_unit()
        binding = bind_work_unit_source(work_unit, source_revision=SHA)
        changed = copy.deepcopy(work_unit)
        changed["objective"] = "Changed after routing"

        with self.assertRaisesRegex(
            WorkUnitBindingError,
            "content changed",
        ):
            validate_work_unit_source_binding(changed, binding)

    def test_wrong_observed_source_revision_fails_closed(self):
        work_unit = _work_unit()
        binding = bind_work_unit_source(work_unit, source_revision=SHA)
        with self.assertRaisesRegex(
            WorkUnitBindingError,
            "does not match retained binding",
        ):
            validate_work_unit_source_binding(
                work_unit,
                binding,
                source_revision=OTHER_SHA,
            )

    def test_identity_change_fails_closed(self):
        work_unit = _work_unit()
        binding = bind_work_unit_source(work_unit, source_revision=SHA)

        wrong_id = copy.deepcopy(work_unit)
        wrong_id["id"] = "test/other-work-unit"
        with self.assertRaisesRegex(WorkUnitBindingError, "different WorkUnit id"):
            validate_work_unit_source_binding(wrong_id, binding)

        wrong_version = copy.deepcopy(work_unit)
        wrong_version["version"] = 3
        with self.assertRaisesRegex(
            WorkUnitBindingError,
            "different WorkUnit version",
        ):
            validate_work_unit_source_binding(wrong_version, binding)

    def test_binding_object_carries_no_acceptance_authority(self):
        binding = bind_work_unit_source(_work_unit(), source_revision=SHA)
        encoded = binding.to_dict()
        forbidden = {
            "accepted",
            "verified",
            "candidate_ready",
            "merge_authorized",
            "integration_authorized",
        }
        self.assertTrue(forbidden.isdisjoint(encoded))

    def test_malformed_work_unit_fails_closed(self):
        for work_unit in (
            [],
            {"id": "", "version": 1, "provenance": {}},
            {"id": "ok/id", "version": True, "provenance": {}},
            {"id": "ok/id", "version": 1, "provenance": None},
        ):
            with self.subTest(work_unit=work_unit):
                with self.assertRaises(WorkUnitBindingError):
                    bind_work_unit_source(
                        work_unit,
                        source_revision=SHA,
                    )


if __name__ == "__main__":
    unittest.main()
