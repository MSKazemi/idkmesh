#!/usr/bin/env python3
"""Bind the proven independent node acceptance suite to PR #159's exact head.

The acceptance mechanics are reused unchanged from historical PR #108. This
wrapper changes only the frozen candidate/PR/CI identity for the current-main
replacement. Historical #91 evidence remains provenance and is not transferred
as exact-head acceptance.
"""

from __future__ import annotations

import node_runtime_acceptance as acceptance

acceptance.FROZEN_CANDIDATE_SHA = "61cafa86f7e0e86343d73182862e3cead1080ab9"
acceptance.NODE_PR = 159
acceptance.NODE_CI_RUN = 33193136252
acceptance.PHASE0_CI_RUN = 33193136271

if __name__ == "__main__":
    raise SystemExit(acceptance.main())
