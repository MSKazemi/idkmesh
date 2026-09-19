#!/usr/bin/env python3
"""Separate correlation from blind spot in the E036 adversarial matrix.

The paper's Sec. 7.2 contrasts the `independent` panel (rho=0, blind spot=0)
against `measured` (rho=0.4513, blind spot=0.0556) and attributes the resulting
catastrophe gap to *correlation*. Two factors move at once, so the attribution is
not licensed. This script runs the two missing single-factor cells at the same
adversary setting, using the repository's own E036 machinery unmodified:

    correlated_only  rho=0.4513, blind spot=0.0
    blindspot_only   rho=0.0,    blind spot=0.0556

Nothing under sim/ or experiments/ is edited; the extra panels are registered on
the module's PANELS dict at run time.

    PYTHONPATH=. python3 paper/deconfound_panel.py --seeds 100 --jobs 4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sim import e036_adversarial_contributors as e036  # noqa: E402
from sim import matched_budget_emergence as mbe  # noqa: E402

# The two single-factor panels, built from the same measured_panel() the
# committed panels use so nothing else differs.
e036.PANELS["correlated_only"] = mbe.measured_panel(correlation=0.4513, blind_spot=0.0)
e036.PANELS["blindspot_only"] = mbe.measured_panel(correlation=0.0, blind_spot=0.0556)

ORDER = ("independent", "correlated_only", "blindspot_only", "measured")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--agents", type=int, default=64)
    ap.add_argument("--generations", type=int, default=50)
    ap.add_argument("--change-at", type=int, default=25)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--fraction", type=float, default=0.2)
    ap.add_argument("--effort", type=int, default=8)
    ap.add_argument("--output", default="paper/figures/deconfound-panel.json")
    args = ap.parse_args()

    report = e036.matrix(
        seeds=args.seeds,
        seed_start=1,
        agents=args.agents,
        generations=args.generations,
        change_at=args.change_at,
        bins=8,
        panels=ORDER,
        fractions=(args.fraction,),
        efforts=(args.effort,),
        jobs=args.jobs,
    )

    rows = {}
    for cell in report["cells"]:
        rows[cell["panel"]] = cell["catastrophic_seeds"]

    print(f"\nadversary: fraction={args.fraction} effort=k{args.effort}  "
          f"seeds={args.seeds}\n")
    print(f"{'panel':>16}  {'rho':>7} {'blind':>7} | " +
          "  ".join(f"{a:>9}" for a in ("qd", "majority", "random", "scalar", "planner")))
    for name in ORDER:
        cfg = e036.PANELS[name]
        d = cfg.as_dict()
        cat = rows.get(name, {})
        print(f"{name:>16}  {d.get('correlation', 0.0):>7} "
              f"{d.get('blind_spot', 0.0):>7} | " +
              "  ".join(f"{cat.get(a, '-'):>9}" for a in
                        ("qd", "majority", "random", "scalar", "planner")))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"adversary": {"fraction": args.fraction, "effort": args.effort,
                       "seeds": args.seeds},
         "panels": {n: e036.PANELS[n].as_dict() for n in ORDER},
         "catastrophic_seeds": rows}, indent=2, sort_keys=True) + "\n")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
