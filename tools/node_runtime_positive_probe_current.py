#!/usr/bin/env python3
"""Run the existing diagnostic positive probe against the corrected frozen head."""

from __future__ import annotations

import node_runtime_positive_probe as probe

probe.FROZEN = "520ad2c9aa5825476de4957da4702d6823f4edb3"

if __name__ == "__main__":
    raise SystemExit(probe.main())
