import json
from pathlib import Path
import tempfile
import unittest

from randomness_lab.r2 import (
    R2Outage,
    R2RunConfig,
    R2Task,
    R2Trace,
    R2TraceConfig,
    R2Worker,
    generate_r2_trace,
    load_r2_trace,
    r2_trace_digest,
    run_r2_benchmark,
    run_r2_policy,
    save_r2_trace,
)


class R2SchedulingTests(unittest.TestCase):
    def test_generated_trace_is_seed_reproducible_and_round_trips(self):
        config = R2TraceConfig(
            worker_count=20,
            ticks=30,
            base_arrivals_per_tick=2,
            churn_fraction=0.2,
            seed=17,
        )
        first = generate_r2_trace(config)
        second = generate_r2_trace(config)
        self.assertEqual(first, second)
        self.assertEqual(r2_trace_digest(first), r2_trace_digest(second))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            save_r2_trace(first, path)
            loaded = load_r2_trace(path)
            json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(first, loaded)
        self.assertEqual(r2_trace_digest(first), r2_trace_digest(loaded))

    def test_all_policies_replay_the_exact_same_trace(self):
        trace = generate_r2_trace(
            R2TraceConfig(
                worker_count=12,
                ticks=20,
                base_arrivals_per_tick=2,
                churn_fraction=0.25,
                seed=9,
            )
        )
        report = run_r2_benchmark(
            trace,
            R2RunConfig(
                availability_observation_lag=2,
                load_observation_lag=2,
                drain_ticks=50,
                policy_seed=33,
            ),
        )
        digest = report["trace"]["trace_digest"]
        for policy_result in report["policies"].values():
            self.assertEqual(policy_result["trace_digest"], digest)

    def test_capability_aware_power_two_avoids_oblivious_mismatches(self):
        workers = (
            R2Worker("gpu-1", 1, ("gpu",), "zone-a"),
            R2Worker("py-1", 1, ("python",), "zone-a"),
            R2Worker("py-2", 1, ("python",), "zone-b"),
            R2Worker("py-3", 1, ("python",), "zone-c"),
        )
        tasks = tuple(
            R2Task(f"task-{index}", 0, 1, "gpu", "zone-a")
            for index in range(20)
        )
        trace = R2Trace(seed=1, ticks=5, workers=workers, tasks=tasks, outages=())
        config = R2RunConfig(
            availability_observation_lag=0,
            load_observation_lag=0,
            drain_ticks=40,
            policy_seed=4,
        )
        oblivious = run_r2_policy(trace, "one-random", config)
        aware = run_r2_policy(trace, "capability-power-two", config)
        oracle = run_r2_policy(trace, "global-least-loaded", config)

        self.assertGreater(oblivious["metrics"]["failed_capability_mismatch"], 0)
        self.assertEqual(aware["metrics"]["failed_capability_mismatch"], 0)
        self.assertEqual(oracle["metrics"]["failed_capability_mismatch"], 0)

    def test_stale_availability_produces_unreachable_assignment(self):
        trace = R2Trace(
            seed=1,
            ticks=2,
            workers=(R2Worker("worker-1", 1, ("gpu",), "zone-a"),),
            tasks=(R2Task("task-1", 1, 1, "gpu", "zone-a"),),
            outages=(R2Outage(0, 1, 3),),
        )
        result = run_r2_policy(
            trace,
            "capability-power-two",
            R2RunConfig(
                availability_observation_lag=2,
                load_observation_lag=0,
                drain_ticks=5,
                policy_seed=1,
            ),
        )
        self.assertGreater(result["metrics"]["failed_unreachable"], 0)
        self.assertEqual(result["metrics"]["tasks_completed"], 1)

    def test_global_oracle_exposes_higher_metadata_cost(self):
        workers = tuple(
            R2Worker(f"worker-{index}", 1, ("python",), "zone-a")
            for index in range(10)
        )
        tasks = tuple(
            R2Task(f"task-{index}", 0, 1, "python", "zone-a")
            for index in range(10)
        )
        trace = R2Trace(seed=2, ticks=2, workers=workers, tasks=tasks, outages=())
        config = R2RunConfig(
            availability_observation_lag=0,
            load_observation_lag=0,
            drain_ticks=5,
            policy_seed=7,
        )
        local = run_r2_policy(trace, "capability-power-two", config)
        oracle = run_r2_policy(trace, "global-least-loaded", config)
        self.assertGreater(
            oracle["metrics"]["mean_metadata_probes_per_routing_attempt"],
            local["metrics"]["mean_metadata_probes_per_routing_attempt"],
        )

    def test_local_capability_oblivious_policy_can_lose_badly_to_oracle(self):
        workers = (
            R2Worker("rare-gpu", 2, ("gpu",), "zone-a"),
        ) + tuple(
            R2Worker(f"python-{index}", 2, ("python",), "zone-b")
            for index in range(1, 20)
        )
        tasks = tuple(
            R2Task(f"gpu-task-{index}", 0, 2, "gpu", "zone-a")
            for index in range(30)
        )
        trace = R2Trace(seed=3, ticks=3, workers=workers, tasks=tasks, outages=())
        config = R2RunConfig(
            availability_observation_lag=0,
            load_observation_lag=0,
            drain_ticks=35,
            policy_seed=11,
        )
        local = run_r2_policy(trace, "power-two", config)
        oracle = run_r2_policy(trace, "global-least-loaded", config)
        self.assertGreater(local["metrics"]["failed_capability_mismatch"], 0)
        self.assertEqual(oracle["metrics"]["failed_capability_mismatch"], 0)
        self.assertGreaterEqual(
            oracle["metrics"]["completion_rate"],
            local["metrics"]["completion_rate"],
        )

    def test_churn_requeues_lost_work_and_reports_recovery(self):
        trace = R2Trace(
            seed=4,
            ticks=4,
            workers=(
                R2Worker("worker-a", 1, ("python",), "zone-a"),
                R2Worker("worker-b", 1, ("python",), "zone-a"),
            ),
            tasks=(R2Task("long-task", 0, 5, "python", "zone-a"),),
            outages=(R2Outage(0, 2, 4),),
        )
        result = run_r2_policy(
            trace,
            "global-least-loaded",
            R2RunConfig(
                availability_observation_lag=0,
                load_observation_lag=0,
                drain_ticks=20,
                policy_seed=1,
                restart_work_on_churn=True,
            ),
        )
        metrics = result["metrics"]
        self.assertGreater(metrics["churn_requeues"], 0)
        self.assertGreater(metrics["lost_work_units_due_churn"], 0)
        self.assertGreater(metrics["churn_recovery_events"], 0)
        self.assertEqual(metrics["unrecovered_churn_events"], 0)
        self.assertEqual(metrics["tasks_completed"], 1)


if __name__ == "__main__":
    unittest.main()
