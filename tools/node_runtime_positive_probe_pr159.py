#!/usr/bin/env python3
"""Run the historical diagnostic positive probe against PR #159's exact head."""

from __future__ import annotations

import node_runtime_positive_probe as probe

probe.FROZEN = "61cafa86f7e0e86343d73182862e3cead1080ab9"

if __name__ == "__main__":
    raise SystemExit(probe.main())
