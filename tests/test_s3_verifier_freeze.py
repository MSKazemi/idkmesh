"""Tests for the S3 verifier external-validity freeze toolkit.

The fixtures are synthetic calibration/pre-freeze inputs only. No confirmatory
verdict or third-party patch is executed.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import s3_verifier_freeze as s3  # noqa: E402


def _rows(repositories: int = 8):
    rows = []
    for repo in range(repositories):
        for task in range(2):
            task_id = f"r{repo}-t{task}"
            rows.append(
                s3.CalibrationRow(
                    f"repo-{repo}",
                    task_id,
                    "official-pass",
                    10.0,
                )
            )
            rows.append(
                s3.CalibrationRow(
                    f"repo-{repo}",
                    task_id,
                    "official-fail",
                    -7.0,
                )
            )
    return rows


class CalibrationInputTests(unittest.TestCase):
    def test_loader_rejects_confirmatory_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "stage": "confirmatory",
                        "repository_id": "r",
                        "task_id": "t",
                        "class_label": "official-pass",
                        "delta_logscore": 0.1,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(s3.S3FreezeError):
                s3.load_calibration_jsonl(path)

    def test_loader_rejects_task_id_collision_across_repositories(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.jsonl"
            lines = [
                {
                    "stage": "calibration",
                    "repository_id": "repo-a",
                    "task_id": "same-task",
                    "class_label": "official-pass",
                    "delta_logscore": 0.1,
                },
                {
                    "stage": "calibration",
                    "repository_id": "repo-b",
                    "task_id": "same-task",
                    "class_label": "official-fail",
                    "delta_logscore": -0.1,
                },
            ]
            path.write_text(
                "\n".join(json.dumps(row) for row in lines) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(s3.S3FreezeError):
                s3.load_calibration_jsonl(path)


class PowerPlanTests(unittest.TestCase):
    def test_development_power_plan_is_deterministic_and_self_addressed(self):
        kwargs = dict(
            calibration_sha256="a" * 64,
            eligible_task_count=50,
            eligible_repository_count=8,
            eligible_pass_items=50,
            eligible_fail_items=50,
            simulations=6,
            delta0=0.5,
            target_power=0.5,
        )
        first = s3.build_power_plan(_rows(), **kwargs)
        second = s3.build_power_plan(_rows(), **kwargs)

        self.assertEqual(first, second)
        self.assertFalse(first["canonical"])
        self.assertEqual(first["decision"]["status"], "powered")
        self.assertEqual(first["decision"]["selected_task_count"], 50)
        self.assertTrue(s3.verify_self_digest(first))

    def test_infeasible_design_is_recorded_not_rescued(self):
        plan = s3.build_power_plan(
            _rows(repositories=7),
            calibration_sha256="b" * 64,
            eligible_task_count=100,
            eligible_repository_count=7,
            eligible_pass_items=50,
            eligible_fail_items=50,
            simulations=2,
        )
        self.assertEqual(plan["decision"]["status"], "infeasible")
        self.assertIn(
            "calibration_has_fewer_than_8_repositories",
            plan["decision"]["reasons"],
        )
        self.assertTrue(s3.verify_self_digest(plan))

    def test_repository_count_caps_simulated_independent_clusters(self):
        cohort = s3._simulate_cohort(
            s3._center(_rows()),
            task_count=50,
            eligible_repository_count=8,
            delta0=0.2,
            rng=s3.SplitMix64(7),
        )
        self.assertEqual(len({row.repository_id for row in cohort}), 8)
        self.assertEqual(len({(row.repository_id, row.task_id) for row in cohort}), 50)

    def test_cluster_jackknife_detects_a_large_positive_shift(self):
        cohort = s3._simulate_cohort(
            s3._center(_rows()),
            task_count=50,
            eligible_repository_count=8,
            delta0=0.5,
            rng=s3.SplitMix64(9),
        )
        self.assertGreater(
            s3._cluster_jackknife_lower(cohort, "repository"),
            0.0,
        )
        self.assertGreater(
            s3._cluster_jackknife_lower(cohort, "task"),
            0.0,
        )

    def test_canonical_flag_requires_every_frozen_default(self):
        plan = s3.build_power_plan(
            _rows(repositories=7),
            calibration_sha256="c" * 64,
            eligible_task_count=100,
            eligible_repository_count=7,
            eligible_pass_items=50,
            eligible_fail_items=50,
        )
        self.assertTrue(plan["canonical"])


class FreezeManifestTests(unittest.TestCase):
    def _root_and_spec(self, directory: str, experiment_id: str = "X7"):
        root = Path(directory)
        protocol = root / "protocol.md"
        protocol.write_text("frozen protocol\n", encoding="utf-8")

        calibration_path = root / "calibration_statistics.json"
        calibration_path.write_text(
            json.dumps(
                {
                    "schema_version": "fixture",
                    "role": "calibration_statistics",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        calibration_digest = s3.file_sha256(calibration_path)

        roles = list(s3.REQUIRED_ARTIFACT_ROLES)
        if experiment_id == "X7":
            roles.append("prompt_bundle")
        artifacts = []
        for role in roles:
            if role in {"analysis_code", "power_planning_code"}:
                path = root / f"{role}.py"
                path.write_text("VALUE = 1\n", encoding="utf-8")
            elif role == "power_plan":
                path = root / "power_plan.json"
                power_plan = s3.with_self_digest(
                    {
                        "schema_version": s3.SCHEMA_POWER,
                        "canonical": True,
                        "design": {
                            "seed": s3.SEED,
                            "smallest_effect_logscore_nats": s3.DELTA0,
                            "smallest_effect_geometric_likelihood_ratio": 1.10,
                            "target_power": s3.TARGET_POWER,
                            "simulated_cohorts": s3.SIMULATIONS,
                            "power_interval_method": s3.POWER_INTERVAL_METHOD,
                            "final_confirmatory_bootstrap_replicates_per_level": (
                                s3.FINAL_BOOTSTRAP_REPLICATES
                            ),
                            "power_decision": (
                                "both repository- and task-cluster jackknife/cluster-t "
                                "95% lower bounds are > 0"
                            ),
                            "final_confirmatory_decision": (
                                "both repository- and task-cluster 10,000-resample percentile "
                                "95% intervals have lower bound > 0"
                            ),
                            "class_estimand": (
                                "macro-average of official-pass and official-fail mean "
                                "delta_logscore"
                            ),
                            "centering": (
                                "subtract calibration mean within each class before injecting "
                                "the smallest effect"
                            ),
                        },
                        "calibration_sha256": calibration_digest,
                        "calibration": {},
                        "eligible_universe": {},
                        "candidates": [],
                        "decision": {
                            "status": "powered",
                            "selected_task_count": 50,
                            "target_power": s3.TARGET_POWER,
                        },
                    }
                )
                path.write_text(
                    json.dumps(power_plan, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            elif role == "calibration_statistics":
                path = calibration_path
            else:
                path = root / f"{role}.json"
                path.write_text(
                    json.dumps(
                        {
                            "schema_version": "fixture",
                            "role": role,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
            artifacts.append({"role": role, "path": path.name})

        models = []
        if experiment_id == "X7":
            for idx in range(3):
                models.append(
                    {
                        "lineage": f"lineage-{idx}",
                        "checkpoint": f"checkpoint-{idx}",
                        "digest": f"{idx + 1:064x}",
                        "release_date": "2026-01-01",
                        "training_cutoff": None,
                        "benchmark_contamination": "unknown",
                        "benchmark_specific_finetuning": False,
                    }
                )

        spec = {
            "schema_version": s3.SCHEMA_FREEZE_INPUT,
            "experiment_id": experiment_id,
            "repository_commit": "d" * 40,
            "protocol_document": protocol.name,
            "artifacts": artifacts,
            "upstream": {
                "name": "example-benchmark",
                "commit": "upstream-pinned-revision",
                "artifacts": [
                    {
                        "name": "inventory",
                        "sha256": "e" * 64,
                    }
                ],
            },
            "models": models,
            "seeds": {
                "bootstrap": s3.SEED,
                "permutation": s3.SEED,
                "stage_assignment": 77,
            },
            "execution_boundary": {
                "untrusted_patch_execution": False,
                "sandbox_required": False,
                "sandbox_issue": 804,
            },
            "container_image_digest": None,
        }
        return root, spec

    def test_manifest_is_deterministic_and_contains_no_outcome_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory)
            first = s3.build_freeze_manifest(spec, root)
            second = s3.build_freeze_manifest(spec, root)

            self.assertEqual(first, second)
            self.assertTrue(s3.verify_self_digest(first))
            self.assertFalse(
                first["claims"]["contains_confirmatory_outcomes"]
            )
            self.assertFalse(first["claims"]["executes_untrusted_code"])

    def test_manifest_digest_changes_when_a_bound_file_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory, experiment_id="X6")
            first = s3.build_freeze_manifest(spec, root)
            (root / "analysis_code.py").write_text(
                "VALUE = 2\n",
                encoding="utf-8",
            )
            second = s3.build_freeze_manifest(spec, root)
            self.assertNotEqual(
                first["self_sha256"],
                second["self_sha256"],
            )

    def test_x7_requires_prompt_bundle_and_three_lineages(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory)
            spec["artifacts"] = [
                item
                for item in spec["artifacts"]
                if item["role"] != "prompt_bundle"
            ]
            with self.assertRaises(s3.S3FreezeError):
                s3.build_freeze_manifest(spec, root)

    def test_benchmark_specific_finetuning_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory)
            spec["models"][0]["benchmark_specific_finetuning"] = True
            with self.assertRaises(s3.S3FreezeError):
                s3.build_freeze_manifest(spec, root)

    def test_calibration_digest_must_match_power_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory, experiment_id="X6")
            calibration_path = root / "calibration_statistics.json"
            calibration_path.write_text(
                json.dumps({"changed": True}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(s3.S3FreezeError):
                s3.build_freeze_manifest(spec, root)

    def test_noncanonical_power_plan_cannot_be_frozen(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory, experiment_id="X6")
            power_path = root / "power_plan.json"
            plan = json.loads(power_path.read_text(encoding="utf-8"))
            plan["canonical"] = False
            plan = s3.with_self_digest(plan)
            power_path.write_text(
                json.dumps(plan, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(s3.S3FreezeError):
                s3.build_freeze_manifest(spec, root)

    def test_outcome_key_cannot_hide_in_candidate_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory, experiment_id="X6")
            candidate_path = root / "candidate_inventory.json"
            candidate_path.write_text(
                json.dumps(
                    {
                        "schema_version": "fixture",
                        "verdicts": [True, False],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(s3.S3FreezeError):
                s3.build_freeze_manifest(spec, root)

    def test_json_overflow_number_is_a_controlled_validation_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overflow.json"
            path.write_text('{"field":1e9999}\n', encoding="utf-8")
            with self.assertRaisesRegex(s3.S3FreezeError, "non-finite"):
                s3.load_json(path)

    def test_missing_power_effect_cannot_pass_even_with_fresh_self_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory, experiment_id="X6")
            power_path = root / "power_plan.json"
            power = json.loads(power_path.read_text(encoding="utf-8"))
            del power["design"]["smallest_effect_logscore_nats"]
            power_path.write_text(
                json.dumps(s3.with_self_digest(power)) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(s3.S3FreezeError, "smallest effect"):
                s3.build_freeze_manifest(spec, root)

    def test_non_numeric_power_effect_is_rejected(self):
        for invalid in (None, True, "not-a-number", [], {}, 10 ** 500):
            with self.subTest(invalid=invalid):
                with tempfile.TemporaryDirectory() as directory:
                    root, spec = self._root_and_spec(directory, experiment_id="X6")
                    power_path = root / "power_plan.json"
                    power = json.loads(power_path.read_text(encoding="utf-8"))
                    power["design"]["smallest_effect_logscore_nats"] = invalid
                    power_path.write_text(
                        json.dumps(s3.with_self_digest(power)) + "\n",
                        encoding="utf-8",
                    )
                    with self.assertRaises(s3.S3FreezeError):
                        s3.build_freeze_manifest(spec, root)

    def test_canonical_power_metadata_drift_is_rejected(self):
        for name, changed in (
            ("power_decision", "wrong decision rule"),
            ("centering", "wrong centering rule"),
            ("smallest_effect_geometric_likelihood_ratio", 1.4),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root, spec = self._root_and_spec(directory, experiment_id="X6")
                path = root / "power_plan.json"
                power = json.loads(path.read_text(encoding="utf-8"))
                power["design"][name] = changed
                path.write_text(
                    json.dumps(s3.with_self_digest(power)) + "\n",
                    encoding="utf-8",
                )
                with self.assertRaises(s3.S3FreezeError):
                    s3.build_freeze_manifest(spec, root)

    def test_freeze_validation_rehashes_every_bound_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory, experiment_id="X6")
            frozen = s3.build_freeze_manifest(spec, root)
            s3.validate_freeze_manifest(frozen, root)
            (root / "analysis_code.py").write_text(
                "VALUE = 999\n", encoding="utf-8"
            )
            self.assertTrue(s3.verify_self_digest(frozen))
            with self.assertRaisesRegex(s3.S3FreezeError, "differs"):
                s3.validate_freeze_manifest(frozen, root)

    def test_fresh_self_digest_cannot_approve_tampered_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory, experiment_id="X6")
            frozen = s3.build_freeze_manifest(spec, root)
            frozen["claims"]["grants_acceptance_authority"] = True
            frozen = s3.with_self_digest(frozen)
            self.assertTrue(s3.verify_self_digest(frozen))
            with self.assertRaisesRegex(s3.S3FreezeError, "forbidden"):
                s3.validate_freeze_manifest(frozen, root)

    def test_fresh_digest_cannot_smuggle_an_unlisted_artifact_field(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory, experiment_id="X6")
            frozen = s3.build_freeze_manifest(spec, root)
            frozen["artifacts"][0]["verdicts"] = [True, False]
            frozen = s3.with_self_digest(frozen)
            with self.assertRaisesRegex(s3.S3FreezeError, "malformed"):
                s3.validate_freeze_manifest(frozen, root)

    def test_local_symlink_ancestor_cannot_alias_freeze_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory, experiment_id="X6")
            inside = root / "real"
            inside.mkdir()
            source = root / "analysis_code.py"
            source.rename(inside / source.name)
            (root / "alias").symlink_to(inside, target_is_directory=True)
            for item in spec["artifacts"]:
                if item["role"] == "analysis_code":
                    item["path"] = "alias/analysis_code.py"
            with self.assertRaisesRegex(s3.S3FreezeError, "symlink"):
                s3.build_freeze_manifest(spec, root)

    def test_cli_requires_root_for_freeze_manifest_but_not_power_plan(self):
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory, experiment_id="X6")
            freeze = root / "freeze.json"
            freeze.write_text(
                json.dumps(s3.build_freeze_manifest(spec, root)) + "\n",
                encoding="utf-8",
            )
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    s3.main(["validate", str(freeze)])
            self.assertEqual(exc.exception.code, 2)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(
                    s3.main(["validate", str(freeze), "--root", str(root)]),
                    0,
                )
            result = json.loads(output.getvalue())
            self.assertEqual(
                result["verification_scope"],
                "bound_artifacts_and_self_digest",
            )
            self.assertTrue(result["artifact_bindings_verified"])
            self.assertFalse(result["authorizes_confirmatory_execution"])

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(
                    s3.main(["validate", str(root / "power_plan.json")]),
                    0,
                )
            result = json.loads(output.getvalue())
            self.assertEqual(
                result["verification_scope"], "canonical_power_plan_structure"
            )
            self.assertFalse(result["artifact_bindings_verified"])
            self.assertFalse(result["authorizes_confirmatory_execution"])

    def test_unknown_artifact_role_cannot_smuggle_a_verdict_matrix(self):
        with tempfile.TemporaryDirectory() as directory:
            root, spec = self._root_and_spec(directory, experiment_id="X6")
            path = root / "verdicts.jsonl"
            path.write_text("{}\n", encoding="utf-8")
            spec["artifacts"].append(
                {
                    "role": "confirmatory_verdict_matrix",
                    "path": path.name,
                }
            )
            with self.assertRaises(s3.S3FreezeError):
                s3.build_freeze_manifest(spec, root)


if __name__ == "__main__":
    unittest.main()
