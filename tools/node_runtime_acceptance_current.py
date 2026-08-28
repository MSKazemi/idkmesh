#!/usr/bin/env python3
"""Bind the existing independent node acceptance suite to the corrected frozen head.

The original evaluator remains unchanged as historical evidence for the rejected
d638a2f candidate. This wrapper changes only frozen identity/CI constants and
then executes the same acceptance logic.
"""

from __future__ import annotations

import node_runtime_acceptance as acceptance

acceptance.FROZEN_CANDIDATE_SHA = "520ad2c9aa5825476de4957da4702d6823f4edb3"
acceptance.NODE_CI_RUN = 33185901079
acceptance.PHASE0_CI_RUN = 33185901058

if __name__ == "__main__":
    raise SystemExit(acceptance.main())
