#!/usr/bin/env python3
"""Bind the real node -> verifier E2E harness to the current frozen candidate."""

from __future__ import annotations

import node_verifier_e2e as e2e

e2e.CANDIDATE_SHA = "520ad2c9aa5825476de4957da4702d6823f4edb3"

if __name__ == "__main__":
    raise SystemExit(e2e.main())
