"""Trailing newlines must not slip past an anchored schema pattern.

Python's ``re`` matches ``$`` before a trailing newline, so before issue
#963 every ``^...$`` pattern in ``schemas/`` accepted the intended value
followed by a newline -- values the JSON Schema specification (ECMA-262
regex semantics) never accepted, and that downstream exact-match checks on
identity fields (SHAs, digests, ids) reject. The catalog now spells every
end anchor as ``$`` plus the ADR-0025 guard, which rejects exactly the
strings Python's ``$`` used to let through and nothing else.

This module proves that for *every* pattern occurrence in ``schemas/``,
via both stdlib ``re`` (what jsonschema compiles) and jsonschema itself,
and fails closed when a new pattern arrives without a recorded sample or
without the guard.

Class-based on purpose: module-level ``def test_*`` functions here would
change the figures ``tests/test_documented_test_counts.py`` guards.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import schema_compat_check as sc

# jsonschema is absent from the randomness-lab job's minimal dependency set
# (see tests/test_schema_validity.py); guarded the same way so that job
# still collects this file.
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    from jsonschema import Draft202012Validator

SCHEMA_DIR = ROOT / "schemas"
ANCHOR_SUFFIX = sc.ANCHOR_SUFFIX

# Patterns that deliberately match a prefix and carry no end anchor, so the
# Python "$" leniency cannot occur and hardening would change their meaning.
# A new entry needs a reason, not just a pattern.
PREFIX_PATTERNS = {
    "^https://": "URL field matched by scheme prefix; no end anchor exists",
    "^https://github\\.com/": (
        "GitHub URL matched by host prefix; no end anchor exists"
    ),
}

# One sample value per anchored pattern *before* hardening (the trailing
# guard is appended to every schema occurrence). A pattern added to schemas/
# without a sample here fails test_every_pattern_has_a_sample, so its
# trailing-newline behavior is reviewed rather than assumed.
BASE_SAMPLES = {
    "^sha256:[0-9a-f]{64}$": "sha256:" + "a" * 64,
    "^sha256:[a-f0-9]{64}$": "sha256:" + "d" * 64,
    "^[0-9a-f]{64}$": "b" * 64,
    "^[0-9a-f]{40}$": "f" * 40,
    "^[a-f0-9]{40}$": "c" * 40,
    "^[a-fA-F0-9]{64}$": "A" * 64,
    "^[0-9a-fA-F]{7,64}$": "abc1234",
    "^(?:[0-9a-f]{40}|[0-9a-f]{64})$": "0" * 40,
    "^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$": "e" * 40,
    "^(?:[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64}|[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255})$": "refs/heads/main",
    "^[a-z0-9][a-z0-9._/-]{2,127}$": "work.unit/one",
    "^[a-z0-9][a-z0-9._-]{2,127}$": "id-001",
    "^[a-z0-9][a-z0-9._-]{1,63}$": "id-1",
    "^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255}$": "idkmesh.example/v1",
    "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$": "work-unit.1",
    "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$": "pkg/name:v1",
    "^[A-Za-z0-9][A-Za-z0-9._-]*$": "Slug",
    "^[A-Za-z0-9._/-]+$": "path/to-id",
    "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$": "owner/repo",
    "^[A-Za-z0-9][A-Za-z0-9._:/-]*$": "idkmesh:api/v1",
    "^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$": "docs/path/to-file.txt",
    "^[a-z][a-z0-9_.-]*$": "event.type-1",
    "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$": "gh_delivery:123.abc",
    "Z$": "2026-01-02T03:04:05Z",
    "^https://github\\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[1-9][0-9]*$": (
        "https://github.com/MSKazemi/idkmesh/pull/42"
    ),
    "^[a-z][a-z0-9_]{2,63}$": "abc_def",
    "^[a-z][a-z0-9._-]{0,63}$": "alpha.v1",
    "^[^/\\s]+/[^/\\s]+$": "owner/repo",
    "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$)).+$": "path/to.txt",
    "^v[0-9]+$": "v1",
    "^evt-[0-9]{12}$": "evt-012345678901",
    "^audit-[0-9]{12}$": "audit-012345678901",
    "^ci-plan-[a-f0-9]{12}-[a-f0-9]{12}$": "ci-plan-0123456789ab-cdef01234567",
    "^ci-receipt-[a-f0-9]{12}-[a-f0-9]{12}$": (
        "ci-receipt-0123456789ab-cdef01234567"
    ),
    "^ci-evaluation-[a-f0-9]{20}$": "ci-evaluation-0123456789abcdef0123",
    "^adaptive-plan-[a-z0-9][a-z0-9._-]*-[a-f0-9]{12}$": (
        "adaptive-plan-a-abc012def345"
    ),
    "^adaptive-outcome-[a-f0-9]{12}-[a-f0-9]{12}$": (
        "adaptive-outcome-0123456789ab-cdef01234567"
    ),
    "^adaptive-cohort-[a-f0-9]{12}$": "adaptive-cohort-0123456789ab",
    "^[0-9]+\\.[0-9]+\\.[0-9]+$": "1.2.3",
    "^[0-9]+\\.[0-9]+$": "1.2",
    "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\\.[0-9]+)?Z$": (
        "2026-01-02T03:04:05Z"
    ),
    "^idkmesh\\.adapter\\.[a-z0-9._/-]+/v[0-9]+\\.[0-9]+$": (
        "idkmesh.adapter.local/v1.0"
    ),
}

# Patterns that deliberately anchor only the end. ``Z$`` checks the UTC
# designator on a value whose leading bound comes from ``"format":
# "date-time"``, so leading content is the format checker's business and
# only the trailing newline leniency is in scope. These are hardened like
# every other end anchor but exempted from the leading-newline test.
SUFFIX_PATTERNS = {
    "Z$": (
        "utcTimestamp checks only the trailing UTC \"Z\" designator; "
        "\"format\": \"date-time\" bounds the leading side"
    ),
}

# Patterns that appear only under ``"not"``: a value is invalid when it
# matches. Python's ``$`` leniency makes such a pattern match *more*
# strings, which rejects more values -- the safe direction -- so the
# ADR-0025 guard is deliberately not applied here (hardening would let
# ``value + "\\n"`` past the exclusion). A new entry needs a reason.
EXCLUSION_PATTERNS = {
    "(^|/)\\.{1,2}(/|$)": (
        "repoPath dot-segment rejection under \"not\"; the leniency errs "
        "toward rejection, so the guard must stay off"
    ),
}
EXCLUSION_SAMPLES = {"(^|/)\\.{1,2}(/|$)": "src/../secret"}

PREFIX_SAMPLES = {
    "^https://": "https://example.test/offers/1",
    "^https://github\\.com/": "https://github.com/MSKazemi/idkmesh",
}


def pattern_occurrences() -> list[tuple[str, str]]:
    """Every ``pattern`` value (and patternProperties key) across schemas/."""
    found: list[tuple[str, str]] = []
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))

        def walk(node: object) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "pattern" and isinstance(value, str):
                        found.append((path.name, value))
                    elif key == "patternProperties" and isinstance(value, dict):
                        found.extend((path.name, key2) for key2 in value)
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(doc)
    return found


def anchored_occurrences() -> list[tuple[str, str, str]]:
    """(schema name, hardened pattern, sample) for every anchored pattern."""
    rows: list[tuple[str, str, str]] = []
    for name, pattern in pattern_occurrences():
        if pattern in PREFIX_PATTERNS or pattern in EXCLUSION_PATTERNS:
            continue
        base = pattern[: -len(ANCHOR_SUFFIX)]
        rows.append((name, pattern, BASE_SAMPLES[base]))
    return rows


class PatternCatalogTests(unittest.TestCase):
    """Catalog shape: every pattern hardened or recorded, and sampled."""

    def test_every_pattern_is_hardened_or_a_recorded_prefix(self) -> None:
        for name, pattern in pattern_occurrences():
            with self.subTest(schema=name, pattern=pattern):
                if pattern in PREFIX_PATTERNS:
                    self.assertTrue(PREFIX_PATTERNS[pattern].strip())
                    continue
                if pattern in EXCLUSION_PATTERNS:
                    self.assertTrue(EXCLUSION_PATTERNS[pattern].strip())
                    continue
                self.assertTrue(
                    pattern.endswith("$" + ANCHOR_SUFFIX),
                    f"{name}: {pattern!r} lacks the ADR-0025 end-anchor guard; "
                    "hardening it, or recording it in PREFIX_PATTERNS with a "
                    "reason, is required by issue #963",
                )

    def test_every_pattern_has_a_sample(self) -> None:
        for name, pattern in pattern_occurrences():
            with self.subTest(schema=name, pattern=pattern):
                if pattern in PREFIX_PATTERNS:
                    self.assertIn(pattern, PREFIX_SAMPLES)
                    continue
                if pattern in EXCLUSION_PATTERNS:
                    self.assertIn(pattern, EXCLUSION_SAMPLES)
                    continue
                base = pattern[: -len(ANCHOR_SUFFIX)]
                self.assertIn(
                    base,
                    BASE_SAMPLES,
                    f"{name}: {pattern!r} has no recorded sample",
                )

    def test_no_stale_samples(self) -> None:
        bases = {
            pattern[: -len(ANCHOR_SUFFIX)]
            for _, pattern in pattern_occurrences()
            if pattern not in PREFIX_PATTERNS and pattern not in EXCLUSION_PATTERNS
        }
        prefixes = {
            pattern
            for _, pattern in pattern_occurrences()
            if pattern in PREFIX_PATTERNS
        }
        exclusions = {
            pattern
            for _, pattern in pattern_occurrences()
            if pattern in EXCLUSION_PATTERNS
        }
        self.assertEqual(set(BASE_SAMPLES), bases, "stale or missing base samples")
        self.assertEqual(
            set(PREFIX_SAMPLES), prefixes, "stale or missing prefix samples"
        )
        self.assertEqual(
            set(EXCLUSION_SAMPLES), exclusions, "stale or missing exclusion samples"
        )


class TrailingNewlineRejectionTests(unittest.TestCase):
    """The acceptance: value + newline rejected for every anchored pattern."""

    def test_trailing_newline_is_rejected_by_re_for_every_pattern(self) -> None:
        for name, pattern, sample in anchored_occurrences():
            with self.subTest(schema=name, pattern=pattern):
                self.assertIsNotNone(re.search(pattern, sample), sample)
                self.assertIsNone(re.search(pattern, sample + "\n"))
                self.assertIsNone(re.search(pattern, sample + "\n\n"))

    def test_leading_newline_is_rejected_by_re_for_every_pattern(self) -> None:
        for name, pattern, sample in anchored_occurrences():
            if pattern[: -len(ANCHOR_SUFFIX)] in SUFFIX_PATTERNS:
                # Unanchored at the start by design; see SuffixPatternTests.
                continue

            with self.subTest(schema=name, pattern=pattern):
                self.assertIsNone(re.search(pattern, "\n" + sample))

    @unittest.skipUnless(HAS_JSONSCHEMA, "requires jsonschema")
    def test_trailing_newline_is_rejected_by_jsonschema_for_every_pattern(
        self,
    ) -> None:
        for name, pattern, sample in anchored_occurrences():
            with self.subTest(schema=name, pattern=pattern):
                validator = Draft202012Validator(
                    {"type": "string", "pattern": pattern}
                )
                self.assertTrue(validator.is_valid(sample))
                self.assertFalse(validator.is_valid(sample + "\n"))

    def test_the_guard_is_load_bearing(self) -> None:
        # Without the guard, Python's "$" accepts the trailing newline for
        # every one of these bodies -- that is the bug. Pinned so nobody
        # "simplifies" the suffix away as redundant.
        for name, pattern, sample in anchored_occurrences():
            with self.subTest(schema=name, pattern=pattern):
                base = pattern[: -len(ANCHOR_SUFFIX)]
                self.assertIsNotNone(re.search(base, sample + "\n"))


class PrefixPatternTests(unittest.TestCase):
    def test_prefix_patterns_stay_unanchored(self) -> None:
        for pattern, reason in PREFIX_PATTERNS.items():
            with self.subTest(pattern=pattern):
                self.assertFalse(pattern.endswith("$"))
                self.assertTrue(reason.strip())
                self.assertIsNotNone(
                    re.search(pattern, PREFIX_SAMPLES[pattern])
                )


class SuffixPatternTests(unittest.TestCase):
    def test_suffix_patterns_are_hardened_but_not_leading_anchored(self) -> None:
        # Registry keys are the base form; the catalog must carry the
        # hardened form, and the trailing-newline rejection must hold while
        # leading content stays this pattern's non-business.
        for base, reason in SUFFIX_PATTERNS.items():
            with self.subTest(pattern=base):
                self.assertTrue(reason.strip())
                self.assertFalse(base.startswith("^"))
                self.assertTrue(base.endswith("$"))
                hardened = base + ANCHOR_SUFFIX
                self.assertIn(hardened, {p for _, p in pattern_occurrences()})
                sample = BASE_SAMPLES[base]
                self.assertIsNotNone(re.search(hardened, sample))
                self.assertIsNone(re.search(hardened, sample + "\n"))
                self.assertIsNotNone(re.search(hardened, "\n" + sample))


class ExclusionPatternTests(unittest.TestCase):
    def test_exclusion_patterns_match_the_violation_not_the_clean_value(self) -> None:
        for pattern, reason in EXCLUSION_PATTERNS.items():
            with self.subTest(pattern=pattern):
                self.assertTrue(reason.strip())
                self.assertFalse(pattern.endswith("$" + ANCHOR_SUFFIX))
                self.assertIsNotNone(
                    re.search(pattern, EXCLUSION_SAMPLES[pattern])
                )
                self.assertIsNone(re.search(pattern, "src/lib/module.py"))

    def test_exclusion_leniency_errs_toward_rejection(self) -> None:
        # The guard must stay off: Python's "$" leniency can only make a
        # "not"-nested pattern match more strings, rejecting more values.
        for pattern in EXCLUSION_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertIsNotNone(
                    re.search(pattern, EXCLUSION_SAMPLES[pattern] + "\n")
                )


if __name__ == "__main__":
    unittest.main()
