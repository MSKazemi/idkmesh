import unittest

from randomness_lab.r3 import (
    BASELINE_GENOME,
    HELDOUT_FAMILIES,
    OBJECTIVES,
    TRAIN_FAMILIES,
    OrchestrationGenome,
    R3Config,
    SyntheticTaskFamily,
    dominates,
    family_split_digest,
    nondominated_front,
    render_r3_report,
    run_r3_experiment,
    validate_family_split,
)


class R3EvolutionTests(unittest.TestCase):
    def _small_config(self):
        return R3Config(
            population_size=8,
            generations=3,
            trials_per_family=12,
            seed=17,
            mutation_rate=0.5,
            crossover_rate=0.7,
            exploration_floor=0.2,
            archive_size=12,
            archive_novelty_threshold=0.05,
        )

    def test_r3_is_seed_reproducible(self):
        config = self._small_config()
        first = run_r3_experiment(config)
        second = run_r3_experiment(config)
        self.assertEqual(first, second)

    def test_train_and_heldout_split_is_disjoint_and_digest_stable(self):
        validate_family_split(TRAIN_FAMILIES, HELDOUT_FAMILIES)
        first = family_split_digest(TRAIN_FAMILIES, HELDOUT_FAMILIES)
        second = family_split_digest(TRAIN_FAMILIES, HELDOUT_FAMILIES)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("sha256:"))

        leaked = SyntheticTaskFamily(
            name=TRAIN_FAMILIES[0].name,
            difficulty=0.5,
            ideal_decomposition_depth=2,
            diversity_value=0.5,
            verification_need=0.5,
            correlation_pressure=0.5,
            security_pressure=0.5,
            latency_pressure=0.5,
        )
        with self.assertRaises(ValueError):
            validate_family_split(TRAIN_FAMILIES, (leaked,))

    def test_heldout_is_not_used_inside_evolution_history(self):
        result = run_r3_experiment(self._small_config())
        heldout_names = {family.name for family in HELDOUT_FAMILIES}
        self.assertFalse(result["split"]["heldout_used_for_evolutionary_selection"])
        self.assertTrue(result["split"]["heldout_burned_after_final_evaluation"])
        for generation in result["evolution_history"]:
            self.assertEqual(generation["heldout_family_names"], [])
            evaluated_names = {
                family["family"]
                for evaluation in generation["evaluations"]
                for family in evaluation["families"]
            }
            self.assertTrue(evaluated_names.isdisjoint(heldout_names))

    def test_training_distribution_changes_across_generations(self):
        result = run_r3_experiment(self._small_config())
        distributions = [
            generation["family_distribution"]
            for generation in result["evolution_history"]
        ]
        self.assertGreater(len({str(sorted(item.items())) for item in distributions}), 1)

    def test_fixed_baseline_and_raw_failure_metrics_are_retained(self):
        result = run_r3_experiment(self._small_config())
        self.assertEqual(result["fixed_baseline"]["genome"], BASELINE_GENOME.__dict__)
        metrics = result["fixed_baseline"]["heldout"]["metrics"]
        for metric in (
            "verified_success_rate",
            "false_acceptance_rate",
            "security_failure_rate",
            "regression_rate",
            "error_correlation",
            "compute_per_task",
            "latency_per_task",
            "human_attention_per_task",
            "complexity",
        ):
            self.assertIn(metric, metrics)

    def test_promotion_is_never_autonomous(self):
        result = run_r3_experiment(self._small_config())
        promotion = result["promotion_evidence"]
        self.assertFalse(promotion["autonomous_promotion"])
        self.assertEqual(promotion["status"], "human_review_required")
        self.assertTrue(promotion["champion_selected_before_heldout"])
        self.assertFalse(promotion["heldout_used_for_evolutionary_selection"])
        self.assertIn(
            promotion["decision"],
            {
                "consider_for_separate human-reviewed experiment",
                "do not promote from this evidence",
            },
        )

    def test_final_train_front_is_actually_nondominated(self):
        result = run_r3_experiment(self._small_config())
        evaluations = result["final_train_reference"]
        by_id = {evaluation["genome_id"]: evaluation for evaluation in evaluations}
        front = [by_id[genome_id] for genome_id in result["final_train_pareto_front_ids"]]
        expected = nondominated_front(evaluations)
        self.assertEqual(
            {item["genome_id"] for item in front},
            {item["genome_id"] for item in expected},
        )
        for left in front:
            for right in front:
                if left is right:
                    continue
                self.assertFalse(dominates(left, right))

    def test_objectives_are_multiobjective_not_output_volume(self):
        self.assertNotIn("output_count", OBJECTIVES)
        self.assertNotIn("activity", OBJECTIVES)
        self.assertTrue(OBJECTIVES["verified_success_rate"])
        self.assertFalse(OBJECTIVES["security_failure_rate"])
        self.assertFalse(OBJECTIVES["compute_per_task"])
        self.assertFalse(OBJECTIVES["complexity"])

    def test_report_contains_human_review_and_heldout_evidence(self):
        result = run_r3_experiment(self._small_config())
        report = render_r3_report(result)
        self.assertIn("Human review required", report)
        self.assertIn("Held-out comparison", report)
        self.assertIn("Pre-heldout champion", report)
        self.assertIn("cannot promote", report)

    def test_genome_bounds_reject_invalid_policy(self):
        with self.assertRaises(ValueError):
            OrchestrationGenome(
                worker_count=0,
                diversity_mix=0.5,
                decomposition_depth=2,
                replication_factor=1,
                verifier_depth=2,
                exploration_temperature=0.2,
                timeout_budget=5,
                escalation_threshold=0.5,
            )


if __name__ == "__main__":
    unittest.main()
