#!/usr/bin/env python3
"""Bind the reusable node runtime acceptance harness to the current frozen target.

The base harness is evaluator-owned test logic. This tiny target adapter makes the
candidate SHA and exact-head CI evidence explicit without weakening or editing the
harness logic after each justified re-freeze.
"""

from __future__ import annotations

import node_runtime_acceptance as acceptance

acceptance.FROZEN_CANDIDATE_SHA = "cbd40c43497ae4feb3a4a5e410dc78766b6cb19c"
acceptance.NODE_CI_RUN = 33185704607
acceptance.PHASE0_CI_RUN = 33185704688

if __name__ == "__main__":
    raise SystemExit(acceptance.main())
