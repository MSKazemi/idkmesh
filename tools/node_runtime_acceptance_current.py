#!/usr/bin/env python3
"""Bind the existing independent node acceptance suite to the corrected frozen head.

The original evaluator remains unchanged as historical evidence for the rejected
d638a2f candidate. This wrapper changes only frozen identity/CI constants and
then executes the same acceptance logic.
"""

from __future__ import annotations

import node_runtime_acceptance as acceptance

acceptance.FROZEN_CANDIDATE_SHA = "cbd40c43497ae4feb3a4a5e410dc78766b6cb19c"
acceptance.NODE_CI_RUN = 33185704607
acceptance.PHASE0_CI_RUN = 33185704688

if __name__ == "__main__":
    raise SystemExit(acceptance.main())
