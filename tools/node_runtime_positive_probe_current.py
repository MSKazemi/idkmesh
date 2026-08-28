#!/usr/bin/env python3
"""Run the existing diagnostic positive probe against the corrected frozen head."""

from __future__ import annotations

import node_runtime_positive_probe as probe

probe.FROZEN = "cbd40c43497ae4feb3a4a5e410dc78766b6cb19c"

if __name__ == "__main__":
    raise SystemExit(probe.main())
