"""E026 Result 3: falsely accepted candidates do not survive in the QD archive.

The claim that E024's landscape has no defect-propagation channel is the
load-bearing one in E026, so it is pinned here rather than left in prose.
"""

from __future__ import annotations

import unittest

import sim.emergence_sim as sim
from sim.e026_archive_contamination import audit_qd_archive
from sim.matched_budget_emergence import measured_panel

REFERENCE = dict(agents=50, generations=50, change_at=25, bins=8)


class ArchiveContaminationTests(unittest.TestCase):
    def test_perfect_panel_accepts_nothing_non_viable(self):
        report = audit_qd_archive(7, verification=sim.VerificationConfig(), **REFERENCE)
        self.assertEqual(report["accepted_but_non_viable"], 0)
        self.assertEqual(report["non_viable_in_archive"], 0)
        self.assertEqual(report["verification_accepts"], 2228)

    def test_measured_panel_waves_defects_through_but_none_survive(self):
        report = audit_qd_archive(7, verification=measured_panel(), **REFERENCE)
        self.assertEqual(report["accepted_but_non_viable"], 49)
        self.assertEqual(report["non_viable_in_archive"], 0)

    def test_stress_panel_waves_far_more_through_and_still_none_survive(self):
        report = audit_qd_archive(
            7,
            verification=measured_panel(accuracy=0.55, correlation=0.9, blind_spot=0.4),
            **REFERENCE,
        )
        # These are the numbers E026 publishes for seed 7.
        self.assertEqual(report["accepted_but_non_viable"], 157)
        self.assertEqual(report["non_viable_in_archive"], 0)
        self.assertEqual(report["archive_size"], 64)

    def test_the_replay_consumes_the_benchmark_budget(self):
        report = audit_qd_archive(7, verification=measured_panel(), **REFERENCE)
        self.assertEqual(
            report["verification_attempts"], REFERENCE["agents"] * REFERENCE["generations"]
        )

    def test_worse_panels_wave_more_defects_through(self):
        accepted = [
            audit_qd_archive(7, verification=panel, **REFERENCE)["accepted_but_non_viable"]
            for panel in (
                sim.VerificationConfig(),
                measured_panel(),
                measured_panel(accuracy=0.55, correlation=0.9, blind_spot=0.4),
            )
        ]
        self.assertEqual(accepted, sorted(accepted))
        self.assertEqual(accepted[0], 0)
        self.assertGreater(accepted[-1], accepted[0])


if __name__ == "__main__":
    unittest.main()
