"""Every committed example is pinned to the contract it demonstrates.

``examples/`` is the surface a newcomer copies from, but coverage of it was
partial and implicit: 23 of the 40 committed examples are named by no test, and
the four WorkUnit composability examples are referenced by no test, no script,
and not even a workflow path filter. Nothing would notice if they drifted away
from ``schemas/``.

This module makes the pairing explicit and enforced. Three tables classify every
example, and a completeness test makes the classification exhaustive, so a new
example cannot be added without deciding which contract it demonstrates.

The tables were built by validating each example against all 33 schemas rather
than by assuming a naming convention; every entry below records a measured
result.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

# The randomness-lab test job installs a minimal dependency set without
# jsonschema, so importing it at module scope makes that job fail to even
# collect this file. Guarded the way tests/test_ace_lineage_schema.py does.
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if HAS_JSONSCHEMA:
    import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = "examples"
SCHEMAS = REPO_ROOT / "schemas"

# Examples that MUST validate against the named schema.
#
# Note that three of these have "invalid" in their name: their invalidity is
# semantic or policy-level, not structural, so they are legitimately
# schema-valid. Asserting that keeps a future schema change from quietly
# turning a semantic fixture into a structural one.
VALID_AGAINST = {
    "examples/benchmarks/work-unit-decomposition-v0.1.json": "decomposition-benchmark-v0.1.schema.json",
    "examples/community/ace-lineage-valid.example.json": "ace-lineage-v0.1.schema.json",
    "examples/compute-offers/free-pool.example.json": "compute-offer-pool-v0.1.schema.json",
    "examples/domain-packs/software-engineering-v0.1.domain-pack.json": "domain-pack.schema.json",
    "examples/experiments/phase0-smoke.manifest.json": "experiment-manifest-v0.1.schema.json",
    # Invalid by graph semantics (a cycle), not by structure.
    "examples/idkgraph.invalid-cycle.json": "idkgraph.schema.json",
    "examples/idkgraph.repository-mapping.example.json": "idkgraph.schema.json",
    "examples/idkgraph.valid.json": "idkgraph.schema.json",
    "examples/projects/idkmesh-research-replication.project.json": "project-manifest.schema.json",
    "examples/projects/idkmesh-self-improvement.project.json": "project-manifest.schema.json",
    "examples/resources/free-resource-registry-v0.1.json": "resource-offer-registry-v0.1.schema.json",
    # Invalid by provenance policy, not by structure.
    "examples/results/invalid-mismatched-provenance.verification-result.json": "verification-result-v0.1.schema.json",
    # Invalid by independence policy, not by structure.
    "examples/results/invalid-non-independent.verification-result.json": "verification-result-v0.1.schema.json",
    "examples/results/phase0-smoke.result-manifest.json": "result-manifest-v0.1.schema.json",
    "examples/results/phase0-smoke.verification-result.json": "verification-result-v0.1.schema.json",
    "examples/routing-replay.example.json": "routing-replay-v0.schema.json",
    "examples/verifier/bad/result-manifest.json": "result-manifest-v0.1.schema.json",
    "examples/verifier/good/result-manifest.json": "result-manifest-v0.1.schema.json",
    "examples/verifier/patch/forbidden/result-manifest.json": "result-manifest-v0.1.schema.json",
    "examples/verifier/patch/good/result-manifest.json": "result-manifest-v0.1.schema.json",
    "examples/verifier/patch/wrong-semantic/result-manifest.json": "result-manifest-v0.1.schema.json",
    "examples/work-units/composability/coding.work-unit.json": "work-unit-v0.2.schema.json",
    "examples/work-units/composability/research.work-unit.json": "work-unit-v0.2.schema.json",
    "examples/work-units/composability/review.work-unit.json": "work-unit-v0.2.schema.json",
    "examples/work-units/composability/testing.work-unit.json": "work-unit-v0.2.schema.json",
    "examples/work-units/local-verifier-smoke.work-unit.json": "work-unit-v0.2.schema.json",
    "examples/work-units/patch-verifier-smoke.work-unit.json": "work-unit-v0.2.schema.json",
    "examples/work-units/phase0-smoke.work-unit.json": "work-unit-v0.2.schema.json",
}

# Examples that MUST be rejected by the named schema. These exist to prove a
# validator says no; if a schema is ever loosened until one of them passes, the
# test that consumes it still goes green while asserting nothing. That silent
# failure is what this table prevents.
INVALID_AGAINST = {
    "examples/community/ace-lineage-invalid-missing-verification.example.json": (
        "ace-lineage-v0.1.schema.json",
        "omits the required 'verification' property",
    ),
    "examples/results/invalid-self-acceptance.result-manifest.json": (
        "result-manifest-v0.1.schema.json",
        "carries an 'accepted' property a worker may not set for itself",
    ),
    "examples/work-units/invalid-missing-security.work-unit.json": (
        "work-unit-v0.2.schema.json",
        "omits the required 'security' property",
    ),
}

# Examples with no JSON Schema contract in schemas/. Validated in code by their
# consumer, or not a schema-bearing artifact at all. Listed so that "no schema"
# is a recorded decision rather than an oversight.
NO_SCHEMA_CONTRACT = {
    "examples/community/ace-activation-gate-current.example.json": "ACE activation gate state; no schema published",
    "examples/community/ace-generation-shadow.example.json": "ACE generation shadow record; no schema published",
    "examples/idkgraph-p1-review-session.example.json": "review-session record; validated by tests/test_idkgraph_review_session.py",
    "examples/orchestration/two-attempt-evaluator-plan-good-vs-bad.json": "orchestration run input; consumed by experiments/two_attempt_orchestrator.py",
    "examples/orchestration/two-attempt-good-vs-bad.json": "orchestration run input; consumed by experiments/run_evidence_report.py",
    "examples/orchestration/two-attempt-worker-failure.json": "orchestration run input; consumed by experiments/run_evidence_report.py",
    "examples/resources/task-public-code-analysis-v0.1.json": "task resource descriptor; no schema published",
    "examples/verifier/bad/candidate-root/candidate.json": "candidate answer payload under a candidate root, not a contract artifact",
    "examples/verifier/good/candidate-root/candidate.json": "candidate answer payload under a candidate root, not a contract artifact",
}


def tracked_examples() -> set[str]:
    """Tracked JSON under examples/. Tracked-only, so stray local files cannot fail the gate."""

    output = subprocess.run(
        ["git", "ls-files", "-z", "--", f"{EXAMPLES}/*.json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {entry for entry in output.split("\0") if entry}


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def errors_for(example: str, schema_name: str) -> list[str]:
    document = json.loads((REPO_ROOT / example).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(load_schema(schema_name))
    return [
        f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda e: list(e.path))
    ]


@unittest.skipUnless(HAS_JSONSCHEMA, "example contract coverage requires jsonschema")
class ExampleContractCoverageTests(unittest.TestCase):
    def test_positive_examples_validate_against_their_schema(self) -> None:
        for example, schema_name in sorted(VALID_AGAINST.items()):
            with self.subTest(example=example):
                self.assertEqual([], errors_for(example, schema_name))

    def test_negative_examples_are_rejected_by_their_schema(self) -> None:
        for example, (schema_name, reason) in sorted(INVALID_AGAINST.items()):
            with self.subTest(example=example):
                self.assertNotEqual(
                    [],
                    errors_for(example, schema_name),
                    f"{example} is meant to be rejected ({reason}) but now validates, "
                    f"so any test relying on it proves nothing.",
                )

    def test_every_committed_example_is_classified(self) -> None:
        classified = set(VALID_AGAINST) | set(INVALID_AGAINST) | set(NO_SCHEMA_CONTRACT)
        tracked = tracked_examples()
        self.assertEqual(
            set(),
            tracked - classified,
            "New example is not classified; add it to one of the tables in this module.",
        )
        self.assertEqual(
            set(),
            classified - tracked,
            "Table names an example that is no longer tracked.",
        )

    def test_tables_are_disjoint(self) -> None:
        self.assertEqual(set(), set(VALID_AGAINST) & set(INVALID_AGAINST))
        self.assertEqual(set(), set(VALID_AGAINST) & set(NO_SCHEMA_CONTRACT))
        self.assertEqual(set(), set(INVALID_AGAINST) & set(NO_SCHEMA_CONTRACT))

    def test_every_named_schema_exists(self) -> None:
        named = set(VALID_AGAINST.values()) | {pair[0] for pair in INVALID_AGAINST.values()}
        for schema_name in sorted(named):
            with self.subTest(schema=schema_name):
                self.assertTrue((SCHEMAS / schema_name).is_file(), schema_name)

    def test_scan_is_not_vacuous(self) -> None:
        # 40 examples were tracked at 31b8f18; the floor guards against an
        # enumeration that silently returns nothing.
        self.assertGreaterEqual(len(tracked_examples()), 35)


if __name__ == "__main__":
    unittest.main()
